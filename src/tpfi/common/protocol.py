"""Protocolo de comunicación entre clientes y servidor.

Todos los mensajes viajan por un socket TCP con el formato de un mensaje HTTP:
una línea inicial, cabeceras y un cuerpo JSON.

    POST /tpfi HTTP/1.1
    Content-Type: application/json
    Content-Length: 44

    {"UUID": "123", "ID": "abc", "ACTION": "get"}

¿Por qué hace falta `Content-Length`? TCP entrega un flujo de bytes, no mensajes:
dos envíos pueden llegar juntos y uno solo puede llegar partido. La cabecera le dice
al receptor exactamente dónde termina cada mensaje.
"""

import json
import socket
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from tpfi.common.errors import IncompleteMessageError, ProtocolError, ValidationError

#: Puerto por defecto de todos los programas.
DEFAULT_PORT = 8080
#: Host por defecto de los clientes.
DEFAULT_HOST = "localhost"
#: Tamaño máximo de las cabeceras: evita agotar la memoria con un mensaje sin fin.
MAX_HEADER_BYTES = 64 * 1024
#: Tamaño máximo del cuerpo. Un ítem de DynamoDB no puede superar los 400 KB, pero
#: una respuesta "list" contiene todos los ítems de la tabla.
MAX_BODY_BYTES = 16 * 1024 * 1024

#: Confirmación que recibe un cliente observador al suscribirse.
SUBSCRIBED_ACK = {"STATUS": "subscribed"}

ACTIONS: tuple[str, ...] = ("get", "set", "list", "subscribe")
#: Acciones que acepta singletonclient; "subscribe" le corresponde a observerclient.
CLIENT_ACTIONS: tuple[str, ...] = ("get", "set", "list")
#: Campos del tuple CorporateData (Tabla 1 del enunciado).
TUPLE_FIELDS = frozenset(
    {
        "id",
        "cp",
        "CUIT",
        "domicilio",
        "idreq",
        "idSeq",
        "localidad",
        "provincia",
        "sede",
        "seqID",
        "telefono",
        "web",
    }
)

_REASONS = {
    200: "OK",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    500: "Internal Server Error",
    502: "Bad Gateway",
}
_ENVELOPE_KEYS = frozenset({"UUID", "ID", "ACTION"})


@dataclass(frozen=True)
class Request:
    """Pedido de un cliente, ya validado."""

    client_uuid: str
    action: str
    record_id: str | None = None
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Message:
    """Mensaje crudo leído del socket."""

    start_line: str
    body: bytes

    @property
    def status(self) -> int:
        """Devuelve el código de estado de una respuesta, o 0 si la línea no lo trae."""
        parts = self.start_line.split()
        return int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0


def _require_text(payload: dict[str, Any], key: str) -> str:
    """Devuelve `payload[key]` si es un texto no vacío; si no, rechaza el pedido."""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"Falta el dato obligatorio {key} o no es un texto válido.")
    return value


def _normalize_fields(record_id: str, payload: dict[str, Any]) -> dict[str, str]:
    """Extrae y valida los campos del tuple incluidos en un pedido "set"."""
    fields = {key: value for key, value in payload.items() if key not in _ENVELOPE_KEYS}

    # El tuple puede repetir la clave como "id"; si difiere de "ID", el pedido es ambiguo.
    tuple_id = fields.pop("id", record_id)
    if tuple_id != record_id:
        raise ValidationError(f'El campo "id" ({tuple_id}) no coincide con ID ({record_id}).')

    unknown = sorted(set(fields) - TUPLE_FIELDS)
    if unknown:
        # Ignorarlos en silencio escondería errores de tipeo, como "telfono".
        raise ValidationError(f"Campos desconocidos para CorporateData: {', '.join(unknown)}.")
    if not fields:
        raise ValidationError('La acción "set" requiere al menos un campo del tuple CorporateData.')

    normalized: dict[str, str] = {}
    for name, value in fields.items():
        # bool es subclase de int en Python: hay que excluirlo de forma explícita.
        if isinstance(value, bool) or not isinstance(value, str | int | float):
            raise ValidationError(f"El campo {name} debe ser un texto o un número.")
        # Todos los valores del tuple de ejemplo son textos.
        normalized[name] = str(value)
    return normalized


def validate_request(payload: Any, allowed_actions: tuple[str, ...] = ACTIONS) -> Request:
    """Comprueba que un pedido tenga los datos mínimos de su acción.

    La usan el cliente, para fallar antes de conectarse, y el servidor, que nunca
    debe confiar en lo que recibe por la red.
    """
    if not isinstance(payload, dict):
        raise ValidationError("El pedido debe ser un objeto JSON.")

    client_uuid = _require_text(payload, "UUID")
    action = payload.get("ACTION")
    if action not in allowed_actions:
        raise ValidationError(f"ACTION debe ser uno de: {', '.join(allowed_actions)}.")

    if action in ("list", "subscribe"):
        if "ID" in payload:
            raise ValidationError(f'En la acción "{action}" no se debe indicar ID.')
        _reject_extra_keys(payload)
        return Request(client_uuid=client_uuid, action=action)

    record_id = _require_text(payload, "ID")
    if action == "get":
        _reject_extra_keys(payload)
        return Request(client_uuid=client_uuid, action=action, record_id=record_id)
    return Request(
        client_uuid=client_uuid, action=action, record_id=record_id, fields=_normalize_fields(record_id, payload)
    )


def _reject_extra_keys(payload: dict[str, Any]) -> None:
    """Rechaza datos que la acción pedida no usaría."""
    extra = sorted(set(payload) - _ENVELOPE_KEYS)
    if extra:
        raise ValidationError(f"Estos datos no corresponden a la acción: {', '.join(extra)}.")


def build_notification(client_uuid: str, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
    """Arma el aviso de cambio que reciben los suscriptores (Ilustración 1)."""
    return {"UUID": client_uuid, "ID": record_id, "ACTION": "change", "DATA": record}


def _json_default(value: object) -> int | float:
    """Convierte los `Decimal` que devuelve DynamoDB a números de JSON."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Tipo no serializable en JSON: {type(value).__name__}")


def dump_json(payload: Any, *, indent: int | None = None) -> str:
    """Convierte un objeto a texto JSON conservando los acentos."""
    return json.dumps(payload, ensure_ascii=False, default=_json_default, indent=indent)


def _frame(start_line: str, payload: Any, extra_headers: str = "") -> bytes:
    """Agrega línea inicial y cabeceras a un cuerpo JSON."""
    body = dump_json(payload).encode("utf-8")
    head = f"{start_line}\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\n{extra_headers}\r\n"
    return head.encode("ascii") + body


def encode_request(payload: Any, host: str) -> bytes:
    """Codifica un pedido POST."""
    return _frame("POST /tpfi HTTP/1.1", payload, f"Host: {host}\r\n")


def encode_response(status: int, payload: Any) -> bytes:
    """Codifica una respuesta con su código de estado."""
    return _frame(f"HTTP/1.1 {status} {_REASONS[status]}", payload)


def parse_json_body(body: bytes) -> Any:
    """Convierte el cuerpo de un mensaje a un objeto de Python."""
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProtocolError("El mensaje recibido no es un JSON válido.") from error


class MessageReader:
    """Lee mensajes de un socket, uno por vez.

    Es una clase, y no una función, porque debe recordar los bytes de más: una
    lectura puede traer el principio del mensaje siguiente.
    """

    def __init__(self, connection: socket.socket) -> None:
        """Guarda el socket del que se va a leer."""
        self._connection = connection
        self._buffer = b""

    def _fill(self) -> bool:
        """Lee más bytes; devuelve False si el otro extremo cerró la conexión."""
        chunk = self._connection.recv(65536)
        self._buffer += chunk
        return bool(chunk)

    def read(self) -> Message | None:
        """Devuelve el próximo mensaje, o None si la conexión cerró entre mensajes.

        Los bytes se quitan del buffer recién cuando el mensaje está completo. Así, si
        `recv` lanza un timeout en el medio, se puede volver a llamar sin perder nada.
        """
        while b"\r\n\r\n" not in self._buffer:
            if len(self._buffer) > MAX_HEADER_BYTES:
                raise ProtocolError("Cabecera demasiado grande.")
            if not self._fill():
                if self._buffer:
                    raise IncompleteMessageError("Mensaje incompleto: la conexión se cerró antes de tiempo.")
                return None

        head, _, rest = self._buffer.partition(b"\r\n\r\n")
        start_line, length = self._parse_head(head)
        while len(rest) < length:
            if not self._fill():
                raise IncompleteMessageError("Mensaje incompleto: la conexión se cerró antes de tiempo.")
            _, _, rest = self._buffer.partition(b"\r\n\r\n")

        self._buffer = rest[length:]
        return Message(start_line=start_line, body=rest[:length])

    @staticmethod
    def _parse_head(head: bytes) -> tuple[str, int]:
        """Devuelve la línea inicial y el valor de Content-Length."""
        start_line, *header_lines = head.decode("latin-1").split("\r\n")
        for line in header_lines:
            name, _, value = line.partition(":")
            if name.strip().lower() == "content-length":
                value = value.strip()
                if not value.isdigit() or int(value) > MAX_BODY_BYTES:
                    raise ProtocolError("Content-Length inválido.")
                return start_line, int(value)
        raise ProtocolError("Falta la cabecera Content-Length.")
