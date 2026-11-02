"""Pruebas de aceptación: un caso por cada punto de "Validación y Verificación".

Cada prueba comprueba el efecto en las tablas leyéndolas directamente con boto3, sin
pasar por el sistema bajo prueba.
"""

import json
import socket
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.acceptance.conftest import Backend, Programs, free_port
from tpfi.common.protocol import MessageReader, encode_request, parse_json_body

pytestmark = pytest.mark.acceptance

SERVER = "singletonproxyobserver.py"
SINGLETON = "singletonclient.py"
OBSERVER = "observerclient.py"

FULL_TUPLE = {
    "cp": "3260",
    "CUIT": "30-70925411-8",
    "domicilio": "25 de Mayo 385-1P",
    "idreq": "473",
    "idSeq": "1146",
    "localidad": "Concepción del Uruguay",
    "provincia": "Entre Rios",
    "sede": "FCyT",
    "seqID": "23",
    "telefono": "03442 43-1442",
    "web": "http://www.uader.edu.ar",
}


def _wait_for(condition: Callable[[], bool], seconds: float = 25.0) -> None:
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert condition()


def _actions(backend: Backend, client_uuid: str) -> list[str]:
    return sorted(str(row["action"]) for row in backend.audit_rows(client_uuid))


class TestCaminoFeliz:
    """Camino feliz de cada acción, con su registro en CorporateLog."""

    def test_set_crea_registro_con_blancos_y_audita(
        self, programs: Programs, backend: Backend, client_uuid: str
    ) -> None:
        port = free_port()
        programs.start_server(port)
        key = backend.new_key()

        result = programs.request(port, {"UUID": client_uuid, "ID": key, "ACTION": "set", "sede": "FCyT"})

        assert result.code == 0
        assert result.json["sede"] == "FCyT"
        assert result.json["cp"] == ""
        assert backend.row(key) == result.json
        rows = backend.audit_rows(client_uuid)
        assert [(row["action"], row["requestedId"]) for row in rows] == [("set", key)]
        assert rows[0]["sessionid"]
        assert rows[0]["timestamp"]

    def test_set_conserva_los_campos_no_informados(
        self, programs: Programs, backend: Backend, client_uuid: str
    ) -> None:
        port = free_port()
        programs.start_server(port)
        key = backend.new_key()
        programs.request(port, {"UUID": client_uuid, "ID": key, "ACTION": "set", **FULL_TUPLE})

        result = programs.request(port, {"UUID": client_uuid, "ID": key, "ACTION": "set", "telefono": "111"})

        assert result.code == 0
        row = backend.row(key)
        assert row is not None
        assert row == {"id": key, **FULL_TUPLE, "telefono": "111"}

    def test_get_devuelve_el_registro_y_audita(self, programs: Programs, backend: Backend, client_uuid: str) -> None:
        port = free_port()
        programs.start_server(port)
        key = backend.new_key()
        backend.data.put_item(Item={"id": key, **FULL_TUPLE})

        result = programs.request(port, {"UUID": client_uuid, "ID": key, "ACTION": "get"})

        assert result.code == 0
        assert result.json == {"id": key, **FULL_TUPLE}
        assert _actions(backend, client_uuid) == ["get"]

    def test_get_escribe_en_el_archivo_de_salida(
        self, programs: Programs, backend: Backend, client_uuid: str, tmp_path: Path
    ) -> None:
        port = free_port()
        programs.start_server(port)
        key = backend.new_key()
        backend.data.put_item(Item={"id": key, **FULL_TUPLE})
        output = tmp_path / "output.json"

        result = programs.request(port, {"UUID": client_uuid, "ID": key, "ACTION": "get"}, f"-o={output}")

        assert result.code == 0
        assert result.stdout == ""
        assert json.loads(output.read_text(encoding="utf-8"))["id"] == key

    def test_list_devuelve_todos_los_registros_y_audita(
        self, programs: Programs, backend: Backend, client_uuid: str
    ) -> None:
        port = free_port()
        programs.start_server(port)
        keys = [backend.new_key(), backend.new_key()]
        for key in keys:
            backend.data.put_item(Item={"id": key, **FULL_TUPLE})

        result = programs.request(port, {"UUID": client_uuid, "ACTION": "list"})

        assert result.code == 0
        assert isinstance(result.json, list)
        assert set(keys) <= {record["id"] for record in result.json}
        assert _actions(backend, client_uuid) == ["list"]

    def test_subscribe_recibe_cada_cambio_y_audita(
        self, programs: Programs, backend: Backend, client_uuid: str, tmp_path: Path
    ) -> None:
        port = free_port()
        programs.start_server(port)
        output = tmp_path / "avisos.json"
        programs.start(OBSERVER, f"-p={port}", f"-o={output}", log_name="observador.log")
        second = programs.start(OBSERVER, f"-p={port}", log_name="observador2.log")
        _wait_for(lambda: programs.log_text("observador.log").count("Suscripto") == 1)
        _wait_for(lambda: programs.log_text("observador2.log").count("Suscripto") == 1)

        key = backend.new_key()
        for value in ("uno", "dos"):
            assert programs.request(port, {"UUID": client_uuid, "ID": key, "ACTION": "set", "sede": value}).code == 0

        def received_both() -> bool:
            return output.exists() and len(json.loads(output.read_text(encoding="utf-8"))) == 2

        _wait_for(received_both)
        assert [item["DATA"]["sede"] for item in json.loads(output.read_text(encoding="utf-8"))] == ["uno", "dos"]
        _wait_for(lambda: programs.log_text("observador2.log").count('"ACTION": "change"') == 2)
        assert second.poll() is None
        assert '"ACTION": "change"' in programs.log_text("observador.log")

    def test_subscribe_queda_en_la_pista_de_auditoria(
        self, programs: Programs, backend: Backend, client_uuid: str
    ) -> None:
        port = free_port()
        programs.start_server(port)
        with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
            connection.sendall(encode_request({"UUID": client_uuid, "ACTION": "subscribe"}, "localhost"))
            message = MessageReader(connection).read()
            assert message is not None
            assert parse_json_body(message.body) == {"STATUS": "subscribed"}
        assert _actions(backend, client_uuid) == ["subscribe"]


class TestArgumentosMalformados:
    """Cada programa rechaza los argumentos malformados."""

    @pytest.mark.parametrize(
        ("script", "arguments"),
        [
            (SINGLETON, []),
            (SINGLETON, ["-i"]),
            (SINGLETON, ["-i=a.json", "-p=abc"]),
            (SINGLETON, ["-i=a.json", "--inventado"]),
            (OBSERVER, ["-p=abc"]),
            (OBSERVER, ["-r=0"]),
            (OBSERVER, ["sobrante"]),
            (SERVER, ["-p=abc"]),
            (SERVER, ["-p=70000"]),
            (SERVER, ["--inventado"]),
        ],
    )
    def test_termina_con_codigo_2(self, programs: Programs, script: str, arguments: list[str]) -> None:
        result = programs.run(script, *arguments)
        assert result.code == 2
        assert "Error en los argumentos" in result.stderr


class TestDatosMinimos:
    """Pedidos sin los datos mínimos: se rechazan y no tocan las tablas."""

    @pytest.mark.parametrize(
        ("payload", "dato"),
        [
            ({"ID": "x", "ACTION": "get"}, "UUID"),
            ({"UUID": "{client}", "ID": "x"}, "ACTION"),
            ({"UUID": "{client}", "ACTION": "get"}, "ID"),
            ({"UUID": "{client}", "ACTION": "set", "sede": "x"}, "ID"),
            ({"UUID": "{client}", "ID": "{key}", "ACTION": "set"}, "campo"),
            ({"UUID": "{client}", "ID": "x", "ACTION": "list"}, "ID"),
        ],
    )
    def test_el_cliente_lo_rechaza(
        self, programs: Programs, backend: Backend, client_uuid: str, payload: dict[str, str], dato: str
    ) -> None:
        port = free_port()
        key = backend.new_key()
        filled = {name: value.format(client=client_uuid, key=key) for name, value in payload.items()}

        # No hay servidor levantado: si el cliente intentara conectarse, el error sería otro.
        result = programs.request(port, filled)

        assert result.code == 1
        assert dato in result.json["Error"]
        assert backend.row(key) is None

    @pytest.mark.parametrize(
        ("payload", "dato"),
        [
            ({"ACTION": "subscribe"}, "UUID"),
            ({"UUID": "{client}", "ACTION": "get"}, "ID"),
            ({"UUID": "{client}", "ID": "{key}", "ACTION": "set"}, "campo"),
            ({"UUID": "{client}", "ID": "{key}", "ACTION": "borrar"}, "ACTION"),
        ],
    )
    def test_el_servidor_tampoco_confia_en_el_cliente(
        self, programs: Programs, backend: Backend, client_uuid: str, payload: dict[str, str], dato: str
    ) -> None:
        port = free_port()
        programs.start_server(port)
        key = backend.new_key()
        filled = {name: value.format(client=client_uuid, key=key) for name, value in payload.items()}

        with socket.create_connection(("127.0.0.1", port), timeout=10) as connection:
            connection.sendall(encode_request(filled, "localhost"))
            message = MessageReader(connection).read()

        assert message is not None
        assert message.status == 400
        assert dato in parse_json_body(message.body)["Error"]
        assert backend.row(key) is None
        assert backend.audit_rows(client_uuid) == []

    def test_registro_inexistente_devuelve_error_y_queda_auditado(
        self, programs: Programs, backend: Backend, client_uuid: str
    ) -> None:
        port = free_port()
        programs.start_server(port)
        key = backend.new_key()

        result = programs.request(port, {"UUID": client_uuid, "ID": key, "ACTION": "get"})

        assert result.code == 1
        assert "No existe" in result.json["Error"]
        assert _actions(backend, client_uuid) == ["get"]


class TestServidorCaido:
    """Comportamiento de los clientes sin servidor."""

    def test_singletonclient_informa_el_error(self, programs: Programs, client_uuid: str) -> None:
        result = programs.request(free_port(), {"UUID": client_uuid, "ACTION": "list"})
        assert result.code == 1
        assert "No se pudo conectar" in result.json["Error"]

    def test_observerclient_reintenta_y_se_suscribe_cuando_vuelve(
        self, programs: Programs, backend: Backend, client_uuid: str
    ) -> None:
        port = free_port()
        observer = programs.start(OBSERVER, f"-p={port}", "-r=1", log_name="observador_reintento.log")
        _wait_for(lambda: "próximo intento" in programs.log_text("observador_reintento.log"))
        assert observer.poll() is None

        programs.start_server(port, log_name="servidor_reintento.log")
        _wait_for(lambda: "Suscripto" in programs.log_text("observador_reintento.log"))
        key = backend.new_key()
        assert programs.request(port, {"UUID": client_uuid, "ID": key, "ACTION": "set", "sede": "x"}).code == 0
        _wait_for(lambda: '"ACTION": "change"' in programs.log_text("observador_reintento.log"))

    def test_observerclient_se_recupera_si_el_servidor_se_cae(self, programs: Programs) -> None:
        port = free_port()
        server = programs.start_server(port, log_name="servidor_caida.log")
        programs.start(OBSERVER, f"-p={port}", "-r=1", log_name="observador_caida.log")
        _wait_for(lambda: programs.log_text("observador_caida.log").count("Suscripto") == 1)

        server.kill()
        server.wait(timeout=10)
        _wait_for(lambda: "próximo intento" in programs.log_text("observador_caida.log"))

        programs.start_server(port, log_name="servidor_caida2.log")
        _wait_for(lambda: programs.log_text("observador_caida.log").count("Suscripto") == 2)


class TestServidorDuplicado:
    """Intento de levantar dos veces el servidor de aplicaciones."""

    def test_el_segundo_falla_y_el_primero_sigue_atendiendo(self, programs: Programs, client_uuid: str) -> None:
        port = free_port()
        first = programs.start_server(port)

        second = programs.run(SERVER, f"-p={port}")

        assert second.code == 1
        assert "ya está en uso" in second.stderr
        assert first.poll() is None
        assert programs.request(port, {"UUID": client_uuid, "ACTION": "list"}).code == 0
