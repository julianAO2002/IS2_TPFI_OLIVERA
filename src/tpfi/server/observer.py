"""Patrón Observer para la gestión de suscripciones.

**Problema:** cuando cambia un dato hay que avisar a una cantidad variable de
clientes, sin que el código que modifica datos tenga que conocerlos.

**Solución:** el sujeto (`SubscriptionManager`) guarda una lista de observadores y les
avisa a todos a través de una interfaz común (`Observer`). Se pueden sumar y quitar
observadores en cualquier momento sin tocar el código que produce los cambios.
"""

import logging
import socket
import threading
from abc import ABC, abstractmethod
from typing import Any

from tpfi.common.protocol import encode_response

logger = logging.getLogger(__name__)


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
    """Observador concreto: reenvía cada aviso por el socket del cliente."""

    def __init__(self, connection: socket.socket, client_uuid: str) -> None:
        """Guarda el socket que quedó abierto al suscribirse."""
        self.client_uuid = client_uuid
        self._connection = connection
        # Dos cambios simultáneos no pueden mezclar sus bytes en un mismo socket.
        self._send_lock = threading.Lock()

    def update(self, notification: dict[str, Any]) -> None:
        """Envía el aviso como un mensaje JSON."""
        with self._send_lock:
            self._connection.sendall(encode_response(200, notification))

    def close(self) -> None:
        """Cierra el socket; no falla si ya estaba cerrado."""
        try:
            # shutdown despierta al hilo que está esperando datos en este socket.
            self._connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            logger.debug("El socket del cliente %s ya estaba cerrado", self.client_uuid)
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
