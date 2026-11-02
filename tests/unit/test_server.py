"""Pruebas del servidor TCP, ejecutado dentro de la misma prueba en un hilo."""

import logging
import socket
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any
from unittest.mock import patch

import pytest

from tpfi.common.errors import StorageError
from tpfi.common.protocol import MessageReader, encode_request, encode_response, parse_json_body
from tpfi.persistence.corporate_data import CorporateDataTable
from tpfi.persistence.corporate_log import CorporateLogTable
from tpfi.server import app
from tpfi.server.app import SingletonProxyObserverServer, parse_arguments

Send = Callable[[Any], tuple[int, Any]]


def _status(start_line: str) -> int:
    return int(start_line.split()[1])


def _exchange(port: int, raw: bytes) -> tuple[int, Any]:
    with socket.create_connection(("localhost", port), timeout=5) as connection:
        connection.sendall(raw)
        message = MessageReader(connection).read()
        assert message is not None
        # El servidor cierra la conexión después de responder.
        assert connection.recv(1) == b""
    return _status(message.start_line), parse_json_body(message.body)


@pytest.fixture
def server(aws_tables: None) -> Iterator[SingletonProxyObserverServer]:
    instance = SingletonProxyObserverServer(port=0)
    instance.bind()
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield instance
    instance.stop()
    thread.join(timeout=5)
    assert not thread.is_alive()


@pytest.fixture
def send(server: SingletonProxyObserverServer) -> Send:
    def _send(payload: Any) -> tuple[int, Any]:
        return _exchange(server.port, encode_request(payload, host="localhost"))

    return _send


def _audit_actions() -> list[str]:
    table = CorporateLogTable()._table
    return sorted(str(row["action"]) for row in table.scan()["Items"])


def _subscribe(port: int) -> tuple[socket.socket, MessageReader]:
    connection = socket.create_connection(("localhost", port), timeout=5)
    connection.sendall(encode_request({"UUID": "obs", "ACTION": "subscribe"}, host="localhost"))
    reader = MessageReader(connection)
    ack = reader.read()
    assert ack is not None
    assert parse_json_body(ack.body) == {"STATUS": "subscribed"}
    return connection, reader


class TestAcciones:
    """Camino feliz y errores de cada acción."""

    def test_set_y_get(self, send: Send) -> None:
        status, record = send({"UUID": "c", "ID": "r", "ACTION": "set", "sede": "FCyT"})
        assert status == 200
        assert record["sede"] == "FCyT"
        assert send({"UUID": "c", "ID": "r", "ACTION": "get"}) == (200, record)

    def test_list_devuelve_un_arreglo(self, send: Send) -> None:
        send({"UUID": "c", "ID": "r", "ACTION": "set", "sede": "x"})
        status, records = send({"UUID": "c", "ACTION": "list"})
        assert status == 200
        assert [record["id"] for record in records] == ["r"]

    def test_cada_accion_queda_auditada(self, send: Send) -> None:
        send({"UUID": "c", "ID": "r", "ACTION": "set", "sede": "x"})
        send({"UUID": "c", "ID": "r", "ACTION": "get"})
        send({"UUID": "c", "ACTION": "list"})
        assert _audit_actions() == ["get", "list", "set"]

    def test_get_inexistente_devuelve_error_y_queda_auditado(self, send: Send) -> None:
        status, body = send({"UUID": "c", "ID": "nada", "ACTION": "get"})
        assert status == 404
        assert "nada" in body["Error"]
        assert _audit_actions() == ["get"]

    def test_pedido_incompleto_no_impacta_en_las_tablas(self, send: Send) -> None:
        status, body = send({"UUID": "c", "ACTION": "get"})
        assert status == 400
        assert "ID" in body["Error"]
        assert _audit_actions() == []

    def test_json_invalido(self, server: SingletonProxyObserverServer) -> None:
        raw = b"POST /tpfi HTTP/1.1\r\nContent-Length: 3\r\n\r\n{x}"
        status, body = _exchange(server.port, raw)
        assert status == 400
        assert "JSON" in body["Error"]

    def test_metodo_distinto_de_post(self, server: SingletonProxyObserverServer) -> None:
        status, body = _exchange(server.port, b"PUT /tpfi HTTP/1.1\r\nContent-Length: 2\r\n\r\n{}")
        assert status == 405
        assert "POST" in body["Error"]

    def test_falla_de_base_de_datos_devuelve_error(self, send: Send) -> None:
        with patch.object(CorporateDataTable, "get", side_effect=StorageError("sin base")):
            status, body = send({"UUID": "c", "ID": "r", "ACTION": "get"})
        assert (status, body) == (502, {"Error": "sin base"})

    def test_error_inesperado_no_detiene_el_servidor(self, send: Send) -> None:
        with patch.object(CorporateDataTable, "get", side_effect=RuntimeError("defecto")):
            status, body = send({"UUID": "c", "ID": "r", "ACTION": "get"})
        assert status == 500
        assert "defecto" not in body["Error"]
        assert send({"UUID": "c", "ACTION": "list"})[0] == 200

    def test_cliente_que_se_conecta_y_no_envia_nada(self, server: SingletonProxyObserverServer, send: Send) -> None:
        socket.create_connection(("localhost", server.port), timeout=5).close()
        assert send({"UUID": "c", "ACTION": "list"})[0] == 200

    def test_atiende_clientes_en_paralelo(self, send: Send) -> None:
        results: list[int] = []

        def worker(index: int) -> None:
            results.append(send({"UUID": "c", "ID": f"r{index}", "ACTION": "set", "sede": "x"})[0])

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert results == [200] * 8


class TestSuscripciones:
    """Flujo completo del observador por socket."""

    def test_el_set_llega_a_todos_los_suscriptos_y_al_solicitante(
        self, server: SingletonProxyObserverServer, send: Send
    ) -> None:
        first, first_reader = _subscribe(server.port)
        second, second_reader = _subscribe(server.port)
        with first, second:
            _, record = send({"UUID": "c", "ID": "r", "ACTION": "set", "sede": "x"})
            for reader in (first_reader, second_reader):
                message = reader.read()
                assert message is not None
                assert parse_json_body(message.body) == {"UUID": "c", "ID": "r", "ACTION": "change", "DATA": record}
        assert "subscribe" in _audit_actions()

    def test_la_conexion_del_suscripto_sigue_abierta_para_varios_avisos(
        self, server: SingletonProxyObserverServer, send: Send
    ) -> None:
        connection, reader = _subscribe(server.port)
        with connection:
            for value in ("1", "2"):
                send({"UUID": "c", "ID": "r", "ACTION": "set", "cp": value})
                message = reader.read()
                assert message is not None
                assert parse_json_body(message.body)["DATA"]["cp"] == value

    def test_el_suscripto_que_se_desconecta_se_quita(self, server: SingletonProxyObserverServer) -> None:
        connection, _ = _subscribe(server.port)
        assert server.subscriptions.count() == 1
        connection.close()
        deadline = time.monotonic() + 5
        while server.subscriptions.count() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.subscriptions.count() == 0

    def test_subscribe_con_falla_de_auditoria_no_registra(self, server: SingletonProxyObserverServer) -> None:
        with patch.object(CorporateLogTable, "record", side_effect=StorageError("sin log")):
            raw = encode_request({"UUID": "c", "ACTION": "subscribe"}, host="h")
            assert _exchange(server.port, raw)[0] == 502
        assert server.subscriptions.count() == 0

    def test_stop_cierra_a_los_suscriptos(self, aws_tables: None) -> None:
        instance = SingletonProxyObserverServer(port=0)
        instance.bind()
        thread = threading.Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        connection, reader = _subscribe(instance.port)
        with connection:
            instance.stop()
            thread.join(timeout=5)
            assert reader.read() is None


class TestArranque:
    """Puerto ocupado, argumentos y verificaciones iniciales."""

    def test_el_segundo_servidor_en_el_mismo_puerto_falla(self, aws_tables: None) -> None:
        first = SingletonProxyObserverServer(port=0)
        first.bind()
        try:
            with pytest.raises(OSError):
                SingletonProxyObserverServer(port=first.port).bind()
        finally:
            first.stop()

    def test_argumentos_por_defecto(self) -> None:
        arguments = parse_arguments([])
        assert (arguments.port, arguments.verbose) == (8080, False)

    def test_argumentos_explicitos(self) -> None:
        arguments = parse_arguments(["-p=9000", "-v"])
        assert (arguments.port, arguments.verbose) == (9000, True)

    @pytest.mark.parametrize("argv", [["-p=abc"], ["-p=70000"], ["-p=0"], ["--desconocido"], ["extra"]])
    def test_argumentos_malformados(self, argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exit_info:
            parse_arguments(argv)
        assert exit_info.value.code == 2
        assert "Error" in capsys.readouterr().err

    def test_main_con_puerto_ocupado_devuelve_error(self, aws_tables: None, capsys: pytest.CaptureFixture[str]) -> None:
        first = SingletonProxyObserverServer(port=0)
        first.bind()
        try:
            assert app.main([f"-p={first.port}"]) == 1
        finally:
            first.stop()
        assert "ya está en uso" in capsys.readouterr().err

    def test_main_sin_acceso_a_las_tablas_devuelve_error(self, aws_tables: None) -> None:
        with patch.object(CorporateDataTable, "check_available", side_effect=StorageError("sin tabla")):
            with patch.object(SingletonProxyObserverServer, "serve_forever") as serve:
                assert app.main(["-p=18099"]) == 1
        serve.assert_not_called()

    def test_main_termina_bien_con_cancelacion_manual(self, aws_tables: None) -> None:
        with patch.object(SingletonProxyObserverServer, "serve_forever", side_effect=KeyboardInterrupt):
            assert app.main(["-p=18098"]) == 0

    def test_v_activa_el_debug_por_salida_estandar(self, aws_tables: None, capsys: pytest.CaptureFixture[str]) -> None:
        with patch.object(SingletonProxyObserverServer, "serve_forever", side_effect=KeyboardInterrupt):
            assert app.main(["-p=18097", "-v"]) == 0
        logging.getLogger("tpfi").debug("mensaje de prueba")
        assert "mensaje de prueba" in capsys.readouterr().out
        logging.getLogger().handlers.clear()


def test_encode_response_es_compatible_con_el_lector() -> None:
    left, right = socket.socketpair()
    with left, right:
        left.sendall(encode_response(404, {"Error": "x"}))
        message = MessageReader(right).read()
    assert message is not None
    assert _status(message.start_line) == 404
