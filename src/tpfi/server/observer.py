"""Patrón Observer para la gestión de suscripciones.

**Problema:** cuando cambia un dato hay que avisar a una cantidad variable de
clientes, sin que el código que modifica datos tenga que conocerlos.

**Solución:** el sujeto (`SubscriptionManager`) guarda una lista de observadores y les
avisa a todos a través de una interfaz común (`Observer`). Se pueden sumar y quitar
observadores en cualquier momento sin tocar el código que produce los cambios.
"""

import logging
import queue
import socket
import threading
from abc import ABC, abstractmethod
from typing import Any

from tpfi.common.protocol import encode_response

logger = logging.getLogger(__name__)

#: Avisos que pueden esperar envío por cliente antes de considerarlo caído.
MAX_PENDING_NOTIFICATIONS = 100


class Observer(ABC):
    """Interfaz de quien quiere enterarse de los cambios."""

    @abstractmethod
    def update(self, notification: dict[str, Any]) -> None:
        """Recibe un aviso. Lanza `OSError` si ya no puede recibir más."""

    @abstractmethod
    def close(self) -> None:
        """Libera los recursos del observador."""


class Subject(ABC):
    """Interfaz de quien produce los avisos."""

    @abstractmethod
    def attach(self, observer: Observer) -> None:
        """Agrega un observador."""

    @abstractmethod
    def detach(self, observer: Observer) -> None:
        """Quita un observador."""

    @abstractmethod
    def notify(self, notification: dict[str, Any]) -> None:
        """Avisa a todos los observadores."""


class SocketObserver(Observer):
    """Observador concreto: reenvía cada aviso por el socket del cliente.

    Escribir en un socket puede bloquear si el cliente dejó de leer. Por eso `update`
    solo deja el aviso en una cola, y un hilo propio de este observador lo envía. Así
    un suscripto trabado no demora al cliente que hizo el "set" ni a los otros
    suscriptos, y cada uno recibe los avisos en orden.
    """

    def __init__(self, connection: socket.socket, client_uuid: str) -> None:
        """Guarda el socket que quedó abierto al suscribirse y arranca su hilo de envío."""
        self.client_uuid = client_uuid
        self._connection = connection
        # La cola tiene límite: si no, un cliente trabado consumiría memoria sin fin.
        self._pending: queue.Queue[dict[str, Any] | None] = queue.Queue(MAX_PENDING_NOTIFICATIONS)
        threading.Thread(target=self._send_pending, daemon=True).start()

    def update(self, notification: dict[str, Any]) -> None:
        """Encola el aviso; si el cliente acumuló demasiados, se lo considera caído."""
        try:
            self._pending.put_nowait(notification)
        except queue.Full as error:
            raise OSError(f"Se llenó la cola de avisos del cliente {self.client_uuid}.") from error

    def _send_pending(self) -> None:
        """Envía los avisos en orden hasta que se cierre el observador o falle la red."""
        while (notification := self._pending.get()) is not None:
            try:
                self._connection.sendall(encode_response(200, notification))
            except OSError as error:
                logger.debug("Falló el envío al cliente %s: %s", self.client_uuid, error)
                # Cortar el socket despierta al hilo de la conexión, que quita la suscripción.
                self._shutdown()
                return

    def _shutdown(self) -> None:
        """Corta el socket en ambos sentidos; no falla si ya estaba cerrado."""
        try:
            self._connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            logger.debug("El socket del cliente %s ya estaba cerrado", self.client_uuid)

    def stop_sending(self) -> None:
        """Termina el hilo de envío, dejando el socket abierto."""
        try:
            self._pending.put_nowait(None)
        except queue.Full:
            # Con la cola llena el hilo no está esperando: el corte del socket lo detiene.
            logger.debug("Cola llena al cerrar el observador de %s", self.client_uuid)

    def close(self) -> None:
        """Termina el hilo de envío y cierra el socket."""
        self.stop_sending()
        self._shutdown()
        self._connection.close()


class SubscriptionManager(Subject):
    """Sujeto concreto: lleva la lista de suscriptos."""

    def __init__(self) -> None:
        """Arranca sin suscriptos."""
        self._observers: list[Observer] = []
        self._lock = threading.Lock()

    def attach(self, observer: Observer) -> None:
        """Registra un suscripto."""
        with self._lock:
            self._observers.append(observer)
        logger.debug("Suscripción registrada; total: %d", self.count())

    def detach(self, observer: Observer) -> None:
        """Quita un suscripto. Si ya no estaba, no hace nada."""
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def notify(self, notification: dict[str, Any]) -> None:
        """Avisa a todos los suscriptos.

        Se recorre una copia de la lista para no retener el lock mientras se escribe en
        la red: un cliente lento no debe impedir que otros se suscriban. Un suscripto
        caído se quita de la lista y no afecta a los demás.
        """
        with self._lock:
            observers = list(self._observers)
        for observer in observers:
            try:
                observer.update(notification)
            except OSError as error:
                logger.debug("Se quita un suscripto que no responde: %s", error)
                self.detach(observer)
                observer.close()

    def count(self) -> int:
        """Devuelve la cantidad de suscriptos."""
        with self._lock:
            return len(self._observers)

    def close_all(self) -> None:
        """Cierra todas las suscripciones. Se usa al apagar el servidor."""
        with self._lock:
            observers, self._observers = self._observers, []
        for observer in observers:
            observer.close()
