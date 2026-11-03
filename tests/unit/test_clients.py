"""Pruebas de los programas cliente contra un servidor real en un hilo."""

import json
import logging
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from tpfi.clients import observer_client, singleton_client
from tpfi.clients.observer_client import ObserverClient
from tpfi.clients.singleton_client import SingletonClient
from tpfi.common.errors import ServerUnavailableError, TpfiError, ValidationError
from tpfi.common.protocol import MessageReader, encode_response
from tpfi.server.app import SingletonProxyObserverServer


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _start(port: int = 0) -> tuple[SingletonProxyObserverServer, threading.Thread]:
    instance = SingletonProxyObserverServer(port=port)
    instance.bind()
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    return instance, thread


@pytest.fixture
def server(aws_tables: None) -> Iterator[SingletonProxyObserverServer]:
    instance, thread = _start()
    yield instance
    instance.stop()
    thread.join(timeout=5)


def _write(path: Path, payload: Any) -> str:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _wait_until(condition: Any, seconds: float = 8.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert condition()


@pytest.mark.parametrize("program", [singleton_client, observer_client])
@pytest.mark.parametrize("host", ["-s=", "-s=   ", "-s=a..b", "-s=" + "x" * 300])
def test_host_invalido_termina_con_codigo_2(program: Any, host: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        program.main(["-i=a.json", host] if program is singleton_client else [host])
    assert exit_info.value.code == 2
    assert "Error en los argumentos" in capsys.readouterr().err


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "servidor.uader.edu.ar"])
def test_host_valido(host: str) -> None:
    assert observer_client.parse_arguments([f"-s={host}"]).server == host


class TestSingletonClient:
    """Programa singletonclient."""

    def test_set_y_get_por_salida_estandar(
        self, server: SingletonProxyObserverServer, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        port = f"-p={server.port}"
        request = _write(tmp_path / "in.json", {"UUID": "c", "ID": "r", "ACTION": "set", "sede": "FCyT"})
        assert singleton_client.main([f"-i={request}", port]) == 0
        capsys.readouterr()
        request = _write(tmp_path / "in.json", {"UUID": "c", "ID": "r", "ACTION": "get"})
        assert singleton_client.main([f"-i={request}", port]) == 0
        assert json.loads(capsys.readouterr().out)["sede"] == "FCyT"

    def test_o_graba_en_archivo_y_no_usa_la_salida_estandar(
        self, server: SingletonProxyObserverServer, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        request = _write(tmp_path / "in.json", {"UUID": "c", "ACTION": "list"})
        output = tmp_path / "out.json"
        assert singleton_client.main([f"-i={request}", f"-o={output}", f"-p={server.port}"]) == 0
        assert json.loads(output.read_text(encoding="utf-8")) == []
        assert capsys.readouterr().out == ""

    def test_error_del_servidor_se_muestra_y_termina_con_1(
        self, server: SingletonProxyObserverServer, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        request = _write(tmp_path / "in.json", {"UUID": "c", "ID": "nada", "ACTION": "get"})
        assert singleton_client.main([f"-i={request}", f"-p={server.port}"]) == 1
        assert "Error" in json.loads(capsys.readouterr().out)

    def test_servidor_caido(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        request = _write(tmp_path / "in.json", {"UUID": "c", "ACTION": "list"})
        assert singleton_client.main([f"-i={request}", f"-p={_free_port()}"]) == 1
        assert "No se pudo conectar" in json.loads(capsys.readouterr().out)["Error"]

    def test_servidor_que_corta_sin_responder(self, tmp_path: Path) -> None:
        with socket.create_server(("127.0.0.1", 0)) as listener:
            port = listener.getsockname()[1]

            def accept_and_close() -> None:
                connection, _ = listener.accept()
                connection.recv(4096)
                connection.close()

            threading.Thread(target=accept_and_close, daemon=True).start()
            with pytest.raises(ServerUnavailableError, match="sin responder"):
                SingletonClient("localhost", port).send({"UUID": "c", "ACTION": "list"})

    @pytest.mark.parametrize(
        "contenido",
        ["{no es json", '["lista"]', '{"ID": "r", "ACTION": "get"}', '{"UUID": "c", "ACTION": "subscribe"}'],
    )
    def test_entrada_invalida_no_llega_a_conectarse(
        self, tmp_path: Path, contenido: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "in.json"
        path.write_text(contenido, encoding="utf-8")
        with patch("socket.create_connection") as connect:
            assert singleton_client.main([f"-i={path}"]) == 1
        connect.assert_not_called()
        assert "Error" in json.loads(capsys.readouterr().out)

    def test_acepta_entrada_utf8_con_bom(self, tmp_path: Path) -> None:
        # PowerShell agrega esa marca al guardar en UTF-8.
        path = tmp_path / "in.json"
        path.write_bytes(b"\xef\xbb\xbf" + b'{"UUID": "c", "ACTION": "list"}')
        assert SingletonClient.load_request(path) == {"UUID": "c", "ACTION": "list"}

    def test_archivo_de_entrada_inexistente(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="No se pudo leer"):
            SingletonClient.load_request(tmp_path / "no_existe.json")

    def test_salida_imposible_de_escribir(self, server: SingletonProxyObserverServer, tmp_path: Path) -> None:
        request = _write(tmp_path / "in.json", {"UUID": "c", "ACTION": "list"})
        assert singleton_client.main([f"-i={request}", f"-o={tmp_path}", f"-p={server.port}"]) == 1

    @pytest.mark.parametrize(
        "argv", [[], ["-i"], ["-i=a.json", "-p=abc"], ["-i=a.json", "--otro"], ["-i=a.json", "extra"]]
    )
    def test_argumentos_malformados(self, argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exit_info:
            singleton_client.main(argv)
        assert exit_info.value.code == 2
        assert "Error" in capsys.readouterr().err


class TestObserverClient:
    """Programa observerclient."""

    def _run(self, client: ObserverClient) -> threading.Thread:
        thread = threading.Thread(target=client.run, daemon=True)
        thread.start()
        return thread

    def _change(self, port: int, value: str) -> None:
        client = SingletonClient("localhost", port)
        status, _ = client.send({"UUID": "c", "ID": "r", "ACTION": "set", "cp": value})
        assert status == 200

    def test_recibe_varios_avisos_sin_cerrar_la_conexion(
        self, server: SingletonProxyObserverServer, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        output = tmp_path / "out.json"
        client = ObserverClient("localhost", server.port, output_path=output, retry_seconds=0.05)
        thread = self._run(client)
        _wait_until(lambda: server.subscriptions.count() == 1)
        self._change(server.port, "1")
        _wait_until(lambda: len(client.received) == 1)
        self._change(server.port, "2")
        _wait_until(lambda: len(client.received) == 2)
        client.stop()
        thread.join(timeout=5)
        assert not thread.is_alive()

        saved = json.loads(output.read_text(encoding="utf-8"))
        assert [item["DATA"]["cp"] for item in saved] == ["1", "2"]
        assert '"ACTION": "change"' in capsys.readouterr().out

    def test_reintenta_hasta_que_aparece_el_servidor(self, aws_tables: None) -> None:
        port = _free_port()
        client = ObserverClient("localhost", port, retry_seconds=0.05)
        thread = self._run(client)
        time.sleep(0.2)
        server, server_thread = _start(port)
        try:
            _wait_until(lambda: server.subscriptions.count() == 1)
            self._change(port, "1")
            _wait_until(lambda: len(client.received) == 1)
        finally:
            client.stop()
            thread.join(timeout=5)
            server.stop()
            server_thread.join(timeout=5)

    def test_se_vuelve_a_suscribir_si_se_corta_el_socket(self, aws_tables: None) -> None:
        port = _free_port()
        first, first_thread = _start(port)
        client = ObserverClient("localhost", port, retry_seconds=0.05)
        thread = self._run(client)
        _wait_until(lambda: first.subscriptions.count() == 1)
        first.stop()
        first_thread.join(timeout=5)

        second, second_thread = _start(port)
        try:
            _wait_until(lambda: second.subscriptions.count() == 1)
            self._change(port, "2")
            _wait_until(lambda: len(client.received) == 1)
        finally:
            client.stop()
            thread.join(timeout=5)
            second.stop()
            second_thread.join(timeout=5)

    def test_error_que_no_es_del_socket_termina_el_programa(self, tmp_path: Path) -> None:
        # Un directorio no se puede escribir como archivo: no es un corte de red.
        client = ObserverClient("localhost", 1, output_path=tmp_path, retry_seconds=0.01)
        with pytest.raises(TpfiError, match="No se pudo escribir"):
            client.deliver({"ACTION": "change"})

    def test_respuesta_de_error_del_servidor_provoca_reintento(self, tmp_path: Path) -> None:
        with socket.create_server(("127.0.0.1", 0)) as listener:
            port = listener.getsockname()[1]
            attempts: list[int] = []

            def reject_twice() -> None:
                for attempt in (1, 2):
                    connection, _ = listener.accept()
                    MessageReader(connection).read()
                    connection.sendall(encode_response(502, {"Error": "sin base"}))
                    connection.close()
                    attempts.append(attempt)

            threading.Thread(target=reject_twice, daemon=True).start()
            client = ObserverClient("127.0.0.1", port, retry_seconds=0.01)
            thread = self._run(client)
            _wait_until(lambda: len(attempts) == 2)
            client.stop()
            thread.join(timeout=5)
            assert not thread.is_alive()

    def test_un_corte_a_mitad_de_mensaje_provoca_reintento(self) -> None:
        with socket.create_server(("127.0.0.1", 0)) as listener:
            port = listener.getsockname()[1]
            attempts: list[int] = []

            def cut_mid_message() -> None:
                for attempt in (1, 2):
                    connection, _ = listener.accept()
                    connection.recv(4096)
                    connection.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 50\r\n\r\n{")
                    connection.close()
                    attempts.append(attempt)

            threading.Thread(target=cut_mid_message, daemon=True).start()
            client = ObserverClient("127.0.0.1", port, retry_seconds=0.01)
            thread = self._run(client)
            _wait_until(lambda: len(attempts) == 2)
            client.stop()
            thread.join(timeout=5)
            assert not thread.is_alive()

    def test_v_muestra_trazas_en_la_operacion_normal(
        self, server: SingletonProxyObserverServer, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.DEBUG, logger="tpfi.clients.observer_client")
        client = ObserverClient("localhost", server.port, retry_seconds=0.05)
        thread = self._run(client)
        _wait_until(lambda: server.subscriptions.count() == 1)
        self._change(server.port, "1")
        _wait_until(lambda: len(client.received) == 1)
        client.stop()
        thread.join(timeout=5)
        assert "Enviando suscripción" in caplog.text
        assert "Suscripción confirmada" in caplog.text
        assert "Aviso recibido" in caplog.text

    def test_usa_el_identificador_de_la_cpu(self) -> None:
        with patch("uuid.getnode", return_value=123):
            assert ObserverClient("h", 1).client_uuid == "123"

    def test_main_termina_bien_con_cancelacion_manual(self) -> None:
        with patch.object(ObserverClient, "run", side_effect=KeyboardInterrupt):
            assert observer_client.main([]) == 0

    def test_main_termina_con_error_si_falla_la_salida(self) -> None:
        with patch.object(ObserverClient, "run", side_effect=TpfiError("falla")):
            assert observer_client.main([]) == 1

    def test_argumentos_por_defecto(self) -> None:
        arguments = observer_client.parse_arguments([])
        assert (arguments.server, arguments.port, arguments.retry, arguments.output) == ("localhost", 8080, 30.0, None)

    def test_argumentos_explicitos(self) -> None:
        arguments = observer_client.parse_arguments(["-s=host", "-p=9000", "-o=salida.json", "-r=5", "-v"])
        assert (arguments.server, arguments.port, arguments.retry) == ("host", 9000, 5.0)
        assert arguments.verbose
        assert arguments.output == Path("salida.json")

    @pytest.mark.parametrize("argv", [["-p=x"], ["-p=0"], ["-r=0"], ["-r=-1"], ["-r=nan"], ["-r=x"], ["--otro"], ["z"]])
    def test_argumentos_malformados(self, argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exit_info:
            observer_client.main(argv)
        assert exit_info.value.code == 2
        assert "Error" in capsys.readouterr().err
