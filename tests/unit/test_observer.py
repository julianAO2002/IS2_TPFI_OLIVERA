"""Pruebas del patrón Observer."""

import socket
import threading
from typing import Any
from unittest.mock import MagicMock

from tpfi.common.protocol import MessageReader, parse_json_body
from tpfi.server.observer import Observer, SocketObserver, Subject, SubscriptionManager


class RecordingObserver(Observer):
    """Observador de prueba que guarda lo que recibe."""

    def __init__(self, fails: bool = False) -> None:
        self.received: list[dict[str, Any]] = []
        self.closed = False
        self._fails = fails

    def update(self, notification: dict[str, Any]) -> None:
        if self._fails:
            raise OSError("socket cerrado")
        self.received.append(notification)

    def close(self) -> None:
        self.closed = True


class TestObserverPattern:
    """Verifica la estructura y el comportamiento del patrón."""

    def test_el_gestor_es_un_sujeto_y_el_socket_un_observador(self) -> None:
        assert issubclass(SubscriptionManager, Subject)
        assert issubclass(SocketObserver, Observer)

    def test_notifica_a_todos_los_suscriptos(self) -> None:
        manager = SubscriptionManager()
        observers = [RecordingObserver() for _ in range(3)]
        for observer in observers:
            manager.attach(observer)
        manager.notify({"ACTION": "change"})
        assert all(observer.received == [{"ACTION": "change"}] for observer in observers)

    def test_admite_varias_suscripciones_del_mismo_uuid(self) -> None:
        # El enunciado pide tantos sockets como suscripciones se reciban.
        manager = SubscriptionManager()
        manager.attach(RecordingObserver())
        manager.attach(RecordingObserver())
        assert manager.count() == 2

    def test_un_observador_desuscripto_no_recibe_avisos(self) -> None:
        manager = SubscriptionManager()
        observer = RecordingObserver()
        manager.attach(observer)
        manager.detach(observer)
        manager.notify({"ACTION": "change"})
        assert observer.received == []

    def test_detach_de_un_observador_ausente_no_falla(self) -> None:
        SubscriptionManager().detach(RecordingObserver())

    def test_un_observador_caido_se_quita_y_no_afecta_a_los_demas(self) -> None:
        manager = SubscriptionManager()
        broken, healthy = RecordingObserver(fails=True), RecordingObserver()
        manager.attach(broken)
        manager.attach(healthy)
        manager.notify({"ACTION": "change"})
        assert healthy.received == [{"ACTION": "change"}]
        assert broken.closed
        assert manager.count() == 1

    def test_close_all_cierra_y_vacia(self) -> None:
        manager = SubscriptionManager()
        observer = RecordingObserver()
        manager.attach(observer)
        manager.close_all()
        assert observer.closed
        assert manager.count() == 0

    def test_suscribirse_durante_una_notificacion_no_bloquea(self) -> None:
        # Si notify retuviera el lock, un observador lento frenaría a los demás.
        manager = SubscriptionManager()

        class Reentrant(RecordingObserver):
            def update(self, notification: dict[str, Any]) -> None:
                manager.attach(RecordingObserver())

        manager.attach(Reentrant())
        worker = threading.Thread(target=manager.notify, args=({},))
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive()
        assert manager.count() == 2


class TestSocketObserver:
    """El observador concreto envía cada aviso por su socket."""

    def test_envia_la_notificacion_como_mensaje(self) -> None:
        left, right = socket.socketpair()
        with left, right:
            SocketObserver(left, "cpu").update({"ACTION": "change"})
            message = MessageReader(right).read()
        assert message is not None
        assert parse_json_body(message.body) == {"ACTION": "change"}

    def test_conoce_el_uuid_del_cliente(self) -> None:
        assert SocketObserver(MagicMock(), "cpu").client_uuid == "cpu"

    def test_close_cierra_el_socket_y_tolera_errores(self) -> None:
        connection = MagicMock()
        connection.shutdown.side_effect = OSError("ya estaba cerrado")
        SocketObserver(connection, "cpu").close()
        connection.close.assert_called_once()
