"""Programa SingletonProxyObserverTPFI: servidor de aplicaciones.

Acepta conexiones TCP y atiende cada una en un hilo. Cada conexión transporta un
pedido JSON. Si el pedido es "subscribe", la conexión queda abierta para enviar los
avisos; en los demás casos se cierra después de responder.
"""

import argparse
import logging
import socket
import sys
import threading
import uuid
from collections.abc import Sequence
from typing import Any

from tpfi.common.cli import ArgumentParser, configure_logging, port_number
from tpfi.common.errors import TpfiError, ValidationError
from tpfi.common.protocol import (
    DEFAULT_PORT,
    SUBSCRIBED_ACK,
    Message,
    MessageReader,
    Request,
    encode_response,
    parse_json_body,
    validate_request,
)
from tpfi.common.version import __build__, __version__
from tpfi.persistence.corporate_data import CorporateDataTable
from tpfi.persistence.corporate_log import CorporateLogTable
from tpfi.server.observer import SocketObserver, SubscriptionManager
from tpfi.server.proxy import CorporateServiceProxy
from tpfi.server.service import RealCorporateService

logger = logging.getLogger(__name__)

#: Plazo para que el cliente envíe su pedido; evita hilos colgados para siempre.
READ_TIMEOUT_SECONDS = 10.0
#: Plazo para escribir en un suscripto; también marca cada cuánto se revisa su socket.
SUBSCRIBER_TIMEOUT_SECONDS = 5.0
#: Cada cuánto el bucle principal revisa si debe detenerse.
ACCEPT_POLL_SECONDS = 0.5


class SingletonProxyObserverServer:
    """Servidor TCP que conecta a los clientes con el proxy."""

    def __init__(self, port: int = DEFAULT_PORT) -> None:
        """Prepara el servidor sin abrir todavía el puerto."""
        self._requested_port = port
        self._listener: socket.socket | None = None
        self._stopping = threading.Event()
        self.subscriptions = SubscriptionManager()

    @property
    def port(self) -> int:
        """Devuelve el puerto en el que realmente se está escuchando."""
        if self._listener is None:
            return self._requested_port
        return int(self._listener.getsockname()[1])

    def bind(self) -> None:
        """Abre el puerto en todas las interfaces; lanza `OSError` si está ocupado.

        `create_server` resuelve una diferencia entre sistemas: en Linux activa
        SO_REUSEADDR para reiniciar rápido, pero no en Windows, donde esa opción
        permitiría que dos servidores compartan el puerto. Así, en ambos sistemas falla
        el intento de levantar el servidor dos veces.
        """
        dual_stack = socket.has_dualstack_ipv6()
        family = socket.AF_INET6 if dual_stack else socket.AF_INET
        self._listener = socket.create_server(("", self._requested_port), family=family, dualstack_ipv6=dual_stack)
        # Con un plazo, accept() se despierta periódicamente y puede atender Ctrl+C.
        self._listener.settimeout(ACCEPT_POLL_SECONDS)

    def serve_forever(self) -> None:
        """Acepta conexiones hasta que se pida detener el servidor."""
        if self._listener is None:
            raise RuntimeError("Hay que llamar a bind() antes de serve_forever().")
        while not self._stopping.is_set():
            try:
                connection, address = self._listener.accept()
            except TimeoutError:
                continue
            except OSError:
                # stop() cerró el socket: es la forma normal de terminar.
                if self._stopping.is_set():
                    break
                raise
            logger.debug("Conexión aceptada desde %s", address)
            threading.Thread(target=self._handle_connection, args=(connection,), daemon=True).start()

    def stop(self) -> None:
        """Deja de aceptar conexiones y cierra las suscripciones."""
        self._stopping.set()
        if self._listener is not None:
            self._listener.close()
        self.subscriptions.close_all()

    def _handle_connection(self, connection: socket.socket) -> None:
        """Atiende una conexión completa; ningún error debe detener al servidor."""
        # El identificador de sesión se genera con uuid4, como pide el enunciado.
        session_id = str(uuid.uuid4())
        try:
            connection.settimeout(READ_TIMEOUT_SECONDS)
            reader = MessageReader(connection)
            message = reader.read()
            if message is not None:
                self._handle_message(connection, message, session_id)
        except TpfiError as error:
            logger.debug("Pedido rechazado: %s", error)
            self._send_safely(connection, error.status, {"Error": str(error)})
        except OSError as error:
            logger.debug("Se perdió la conexión: %s", error)
        except Exception:
            # El detalle queda en el log; el cliente no recibe información interna.
            logger.exception("Error inesperado atendiendo un pedido")
            self._send_safely(connection, 500, {"Error": "Error interno del servidor."})
        finally:
            connection.close()

    def _handle_message(self, connection: socket.socket, message: Message, session_id: str) -> None:
        """Valida un mensaje, lo ejecuta y envía la respuesta."""
        if not message.start_line.startswith("POST "):
            connection.sendall(encode_response(405, {"Error": "Solo se acepta el método POST."}))
            return

        request = validate_request(parse_json_body(message.body))
        logger.debug("Pedido: acción=%s id=%s sesión=%s", request.action, request.record_id, session_id)
        proxy = self._build_proxy(request, session_id)
        if request.action == "subscribe":
            self._serve_subscriber(connection, proxy, request)
        else:
            connection.sendall(encode_response(200, self._execute(proxy, request)))

    def _build_proxy(self, request: Request, session_id: str) -> CorporateServiceProxy:
        """Arma el proxy de esta conexión sobre las instancias Singleton."""
        return CorporateServiceProxy(
            real=RealCorporateService(CorporateDataTable()),
            log=CorporateLogTable(),
            subscriptions=self.subscriptions,
            client_uuid=request.client_uuid,
            session_id=session_id,
        )

    @staticmethod
    def _execute(proxy: CorporateServiceProxy, request: Request) -> Any:
        """Ejecuta una acción "get", "set" o "list"."""
        if request.action == "list":
            return proxy.list_records()
        if request.record_id is None:
            # validate_request ya lo garantiza; se repite para el chequeo de tipos.
            raise ValidationError("Falta el dato obligatorio ID.")
        if request.action == "get":
            return proxy.get_record(request.record_id)
        return proxy.set_record(request.record_id, request.fields)

    def _serve_subscriber(self, connection: socket.socket, proxy: CorporateServiceProxy, request: Request) -> None:
        """Mantiene abierta la conexión de un suscripto hasta que se corte."""
        observer = SocketObserver(connection, request.client_uuid)
        connection.settimeout(SUBSCRIBER_TIMEOUT_SECONDS)
        proxy.subscribe(observer)
        try:
            observer.update(SUBSCRIBED_ACK)
            self._wait_until_closed(connection)
        finally:
            self.subscriptions.detach(observer)

    def _wait_until_closed(self, connection: socket.socket) -> None:
        """Bloquea hasta que el cliente cierre, para detectar desconexiones rápido."""
        while not self._stopping.is_set():
            try:
                if not connection.recv(4096):
                    return
            except TimeoutError:
                continue

    @staticmethod
    def _send_safely(connection: socket.socket, status: int, body: dict[str, str]) -> None:
        """Intenta informar un error; si el cliente ya no está, no hay a quién avisarle."""
        try:
            connection.sendall(encode_response(status, body))
        except OSError as error:
            logger.debug("No se pudo informar el error al cliente: %s", error)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Interpreta los argumentos: python singletonproxyobserver.py {-p=port}{-v}."""
    parser = ArgumentParser("Servidor de aplicaciones Singleton, Proxy y Observer.")
    parser.add_argument("-p", "--port", type=port_number, default=DEFAULT_PORT, help="puerto TCP (por defecto 8080)")
    parser.add_argument("-v", "--verbose", action="store_true", help="activa los mensajes de debug")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada del programa; devuelve el código de salida."""
    arguments = parse_arguments(argv)
    configure_logging(arguments.verbose)
    server = SingletonProxyObserverServer(arguments.port)

    # El puerto se abre primero: un segundo servidor debe fallar sin consultar a AWS.
    try:
        server.bind()
    except OSError as error:
        logger.debug("Detalle del error de bind: %s", error)
        print(f"Error: el puerto {arguments.port} ya está en uso o no está disponible.", file=sys.stderr)
        return 1

    try:
        CorporateDataTable().check_available()
        CorporateLogTable().check_available()
        print(f"Servidor TPFI {__version__} (build {__build__}) escuchando en *:{server.port}", flush=True)
        server.serve_forever()
    except TpfiError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Servidor detenido por cancelación manual.", flush=True)
    finally:
        server.stop()
    return 0
