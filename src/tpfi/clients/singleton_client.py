"""Programa SingletonClient: consulta y modifica datos corporativos.

Lee un pedido JSON de un archivo, lo envía al servidor y muestra la respuesta:

    python singletonclient.py -i=input.json {-o=output.json}{-v}

El programa termina con 0 si la operación fue exitosa, con 1 si hubo un error de la
operación y con 2 si los argumentos están mal escritos.
"""

import argparse
import codecs
import logging
import socket
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tpfi.common.cli import ArgumentParser, configure_logging, host_name, port_number
from tpfi.common.errors import ServerUnavailableError, TpfiError, ValidationError
from tpfi.common.protocol import (
    CLIENT_ACTIONS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    MessageReader,
    dump_json,
    encode_request,
    parse_json_body,
    validate_request,
)

logger = logging.getLogger(__name__)

#: Plazo para recibir la respuesta. Un "list" sobre una tabla grande puede demorar.
RESPONSE_TIMEOUT_SECONDS = 30.0


class SingletonClient:
    """Cliente de pedido y respuesta: una conexión por pedido."""

    def __init__(self, host: str, port: int) -> None:
        """Guarda la dirección del servidor."""
        self._host = host
        self._port = port

    @staticmethod
    def load_request(path: Path) -> Any:
        """Lee el archivo JSON de entrada."""
        try:
            # PowerShell puede guardar el archivo con la marca BOM de UTF-8 al inicio.
            return parse_json_body(path.read_bytes().removeprefix(codecs.BOM_UTF8))
        except OSError as error:
            raise ValidationError(f"No se pudo leer el archivo de entrada {path}.") from error

    def send(self, payload: Any) -> tuple[int, Any]:
        """Envía un pedido y devuelve el código de estado y la respuesta."""
        address = f"{self._host}:{self._port}"
        try:
            with socket.create_connection((self._host, self._port), timeout=RESPONSE_TIMEOUT_SECONDS) as connection:
                logger.debug("Conectado a %s; enviando %s", address, payload)
                connection.sendall(encode_request(payload, self._host))
                message = MessageReader(connection).read()
        except OSError as error:
            logger.debug("Falla de red: %s", error)
            raise ServerUnavailableError(f"No se pudo conectar con el servidor {address}.") from error

        if message is None:
            raise ServerUnavailableError(f"El servidor {address} cerró la conexión sin responder.")
        logger.debug("Respuesta: %s", message.start_line)
        return message.status, parse_json_body(message.body)


def write_output(body: Any, path: Path | None) -> None:
    """Graba la respuesta en un archivo o, si no se indicó, la muestra por pantalla."""
    text = dump_json(body, indent=2)
    if path is None:
        print(text, flush=True)
    else:
        path.write_text(text + "\n", encoding="utf-8")


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos de línea de comandos."""
    parser = ArgumentParser("Consulta o modifica datos corporativos.")
    parser.add_argument("-i", "--input", type=Path, required=True, help="archivo JSON con el pedido")
    parser.add_argument("-o", "--output", type=Path, help="archivo de salida (por defecto, la salida estándar)")
    parser.add_argument(
        "-s", "--server", type=host_name, default=DEFAULT_HOST, help="host del servidor (por defecto localhost)"
    )
    parser.add_argument("-p", "--port", type=port_number, default=DEFAULT_PORT, help="puerto (por defecto 8080)")
    parser.add_argument("-v", "--verbose", action="store_true", help="activa los mensajes de debug")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del programa; devuelve el código de salida."""
    arguments = parse_arguments(argv)
    configure_logging(arguments.verbose)
    client = SingletonClient(arguments.server, arguments.port)

    try:
        payload = client.load_request(arguments.input)
        # Se valida acá para no molestar al servidor con un pedido que ya se sabe inválido.
        validate_request(payload, allowed_actions=CLIENT_ACTIONS)
        status, body = client.send(payload)
    except TpfiError as error:
        # Un error local se muestra con el mismo formato que un error del servidor.
        status, body = error.status, {"Error": str(error)}

    try:
        write_output(body, arguments.output)
    except OSError as error:
        print(f"Error: no se pudo escribir {arguments.output}: {error}", file=sys.stderr)
        return 1
    return 0 if status == 200 else 1
