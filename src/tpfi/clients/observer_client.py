"""Programa ObserverClient: se suscribe y muestra cada cambio de CorporateData.

    python observerclient.py {-s=hostname} {-p=port} {-o=output.json}{-v}

Mantiene el socket abierto para recibir múltiples avisos. Si la conexión se corta,
reintenta cada 30 segundos (parametrizable con `-r`) y al reconectarse vuelve a
suscribirse. Solo termina por cancelación manual o por un error que no sea de red.
"""

import argparse
import logging
import socket
import sys
import threading
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tpfi.common.cli import ArgumentParser, configure_logging, host_name, port_number, positive_seconds
from tpfi.common.errors import OutputError, TpfiError
from tpfi.common.protocol import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    SUBSCRIBED_ACK,
    MessageReader,
    dump_json,
    encode_request,
    parse_json_body,
)

logger = logging.getLogger(__name__)

DEFAULT_RETRY_SECONDS = 30.0
CONNECT_TIMEOUT_SECONDS = 10.0
#: Cada cuánto se interrumpe la espera para revisar si hay que terminar. En Windows,
#: un recv sin plazo no deja que Ctrl+C actúe hasta que llegan datos.
POLL_SECONDS = 0.5


class ObserverClient:
    """Cliente suscriptor con reconexión automática."""

    def __init__(
        self,
        host: str,
        port: int,
        output_path: Path | None = None,
        retry_seconds: float = DEFAULT_RETRY_SECONDS,
    ) -> None:
        """Prepara el cliente; `getnode` identifica la CPU desde la que se ejecuta."""
        self.client_uuid = str(uuid.getnode())
        self.received: list[Any] = []
        self._host = host
        self._port = port
        self._output_path = output_path
        self._retry_seconds = retry_seconds
        self._stopping = threading.Event()

    def run(self) -> None:
        """Escucha avisos hasta que se cancele el programa."""
        while not self._stopping.is_set():
            try:
                self._listen()
            except OSError as error:
                # Solo los cortes de red son OSError acá: deliver los convierte en OutputError.
                logger.debug("Conexión perdida: %s", error)
            if not self._stopping.is_set():
                print(
                    f"Sin conexión con {self._host}:{self._port}; próximo intento en {self._retry_seconds:g} s.",
                    file=sys.stderr,
                    flush=True,
                )
                # A diferencia de sleep, wait puede interrumpirse desde stop().
                self._stopping.wait(self._retry_seconds)

    def stop(self) -> None:
        """Pide terminar el ciclo de `run`."""
        self._stopping.set()

    def _listen(self) -> None:
        """Se conecta, se suscribe y procesa avisos hasta que se corte la conexión."""
        request = {"UUID": self.client_uuid, "ACTION": "subscribe"}
        with socket.create_connection((self._host, self._port), timeout=CONNECT_TIMEOUT_SECONDS) as connection:
            logger.debug("Enviando suscripción a %s:%d: %s", self._host, self._port, request)
            connection.sendall(encode_request(request, self._host))
            connection.settimeout(POLL_SECONDS)
            reader = MessageReader(connection)
            while not self._stopping.is_set():
                try:
                    message = reader.read()
                except TimeoutError:
                    continue  # No llegó nada todavía: se vuelve a esperar.
                if message is None:
                    return
                body = parse_json_body(message.body)
                if message.status != 200:
                    print(f"El servidor rechazó la suscripción: {body}", file=sys.stderr, flush=True)
                    return
                if body == SUBSCRIBED_ACK:
                    logger.debug("Suscripción confirmada por el servidor")
                    print(f"Suscripto a {self._host}:{self._port}.", file=sys.stderr, flush=True)
                else:
                    logger.debug("Aviso recibido: %s", message.start_line)
                    self.deliver(body)

    def deliver(self, notification: Any) -> None:
        """Muestra un aviso por la salida estándar y lo agrega al archivo de salida.

        El archivo se reescribe completo como un arreglo, para que siempre contenga un
        JSON válido aunque haya varios avisos.
        """
        self.received.append(notification)
        print(dump_json(notification, indent=2), flush=True)
        if self._output_path is not None:
            try:
                self._output_path.write_text(dump_json(self.received, indent=2) + "\n", encoding="utf-8")
            except OSError as error:
                raise OutputError(f"No se pudo escribir {self._output_path}: {error}") from error


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos de línea de comandos."""
    parser = ArgumentParser("Se suscribe a los cambios de CorporateData.")
    parser.add_argument(
        "-s", "--server", type=host_name, default=DEFAULT_HOST, help="host del servidor (por defecto localhost)"
    )
    parser.add_argument("-p", "--port", type=port_number, default=DEFAULT_PORT, help="puerto (por defecto 8080)")
    parser.add_argument("-o", "--output", type=Path, help="archivo JSON donde acumular los avisos")
    parser.add_argument(
        "-r", "--retry", type=positive_seconds, default=DEFAULT_RETRY_SECONDS, help="segundos entre reintentos"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="activa los mensajes de debug")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del programa; devuelve el código de salida."""
    arguments = parse_arguments(argv)
    configure_logging(arguments.verbose)
    client = ObserverClient(arguments.server, arguments.port, arguments.output, arguments.retry)
    try:
        client.run()
    except KeyboardInterrupt:
        print("Cliente detenido por cancelación manual.", file=sys.stderr, flush=True)
    except TpfiError as error:
        print(f"Error: {error}", file=sys.stderr, flush=True)
        return 1
    return 0
