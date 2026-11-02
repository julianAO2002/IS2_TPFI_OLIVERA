"""Pruebas del protocolo: validación de pedidos y formato de los mensajes."""

import json
import socket
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tpfi.common.errors import ProtocolError, ValidationError
from tpfi.common.protocol import (
    MAX_BODY_BYTES,
    MessageReader,
    build_notification,
    encode_request,
    encode_response,
    parse_json_body,
    validate_request,
)


def _pair() -> tuple[socket.socket, socket.socket]:
    """Devuelve dos sockets conectados entre sí para simular una conexión."""
    return socket.socketpair()


class TestValidateRequest:
    """Reglas de datos mínimos por acción."""

    def test_get_valido(self) -> None:
        request = validate_request({"UUID": "cpu", "ID": "reg", "ACTION": "get"})
        assert (request.client_uuid, request.record_id, request.action) == ("cpu", "reg", "get")

    def test_list_valido_sin_id(self) -> None:
        request = validate_request({"UUID": "cpu", "ACTION": "list"})
        assert request.record_id is None

    def test_subscribe_valido(self) -> None:
        assert validate_request({"UUID": "cpu", "ACTION": "subscribe"}).action == "subscribe"

    def test_set_separa_los_campos_del_tuple(self) -> None:
        request = validate_request({"UUID": "cpu", "ID": "reg", "ACTION": "set", "sede": "FCyT", "cp": 3260})
        assert request.fields == {"sede": "FCyT", "cp": "3260"}

    def test_set_acepta_id_en_minuscula_si_coincide(self) -> None:
        request = validate_request({"UUID": "cpu", "ID": "reg", "ACTION": "set", "id": "reg", "sede": "x"})
        assert request.fields == {"sede": "x"}

    @pytest.mark.parametrize(
        ("payload", "fragmento"),
        [
            (["no es objeto"], "objeto JSON"),
            ({"ID": "r", "ACTION": "get"}, "UUID"),
            ({"UUID": "", "ID": "r", "ACTION": "get"}, "UUID"),
            ({"UUID": 5, "ID": "r", "ACTION": "get"}, "UUID"),
            ({"UUID": "c", "ID": "r"}, "ACTION"),
            ({"UUID": "c", "ID": "r", "ACTION": "borrar"}, "ACTION"),
            ({"UUID": "c", "ACTION": "get"}, "ID"),
            ({"UUID": "c", "ID": "  ", "ACTION": "get"}, "ID"),
            ({"UUID": "c", "ACTION": "set", "sede": "x"}, "ID"),
            ({"UUID": "c", "ID": "r", "ACTION": "set"}, "al menos un campo"),
            ({"UUID": "c", "ID": "r", "ACTION": "list"}, "no se debe indicar"),
            ({"UUID": "c", "ID": "r", "ACTION": "subscribe"}, "no se debe indicar"),
            ({"UUID": "c", "ID": "r", "ACTION": "get", "sede": "x"}, "no corresponden"),
            ({"UUID": "c", "ID": "r", "ACTION": "set", "telfono": "1"}, "desconocidos"),
            ({"UUID": "c", "ID": "r", "ACTION": "set", "id": "otro", "sede": "x"}, "no coincide"),
            ({"UUID": "c", "ID": "r", "ACTION": "set", "sede": None}, "sede"),
            ({"UUID": "c", "ID": "r", "ACTION": "set", "sede": True}, "sede"),
            ({"UUID": "c", "ID": "r", "ACTION": "set", "sede": ["x"]}, "sede"),
        ],
    )
    def test_rechaza_pedidos_incompletos_o_invalidos(self, payload: Any, fragmento: str) -> None:
        with pytest.raises(ValidationError, match=fragmento):
            validate_request(payload)

    def test_el_cliente_puede_restringir_las_acciones(self) -> None:
        with pytest.raises(ValidationError, match="ACTION"):
            validate_request({"UUID": "c", "ACTION": "subscribe"}, allowed_actions=("get", "set", "list"))


class TestMessageReader:
    """Lectura de mensajes enmarcados con Content-Length sobre un flujo TCP."""

    def test_lee_un_pedido_completo(self) -> None:
        left, right = _pair()
        with left, right:
            left.sendall(encode_request({"UUID": "c", "ACTION": "list"}, host="localhost"))
            message = MessageReader(right).read()
        assert message is not None
        assert message.start_line.startswith("POST ")
        assert parse_json_body(message.body) == {"UUID": "c", "ACTION": "list"}

    def test_separa_mensajes_que_llegan_pegados(self) -> None:
        # TCP es un flujo de bytes: dos envíos pueden llegar en una sola lectura.
        left, right = _pair()
        with left, right:
            left.sendall(encode_response(200, {"n": 1}) + encode_response(200, {"n": 2}))
            reader = MessageReader(right)
            first, second = reader.read(), reader.read()
        assert first is not None and second is not None
        assert [parse_json_body(first.body), parse_json_body(second.body)] == [{"n": 1}, {"n": 2}]

    def test_devuelve_none_si_la_conexion_cierra_entre_mensajes(self) -> None:
        left, right = _pair()
        left.close()
        with right:
            assert MessageReader(right).read() is None

    def test_falla_si_la_conexion_cierra_a_mitad_de_mensaje(self) -> None:
        left, right = _pair()
        left.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 10\r\n\r\nabc")
        left.close()
        with right, pytest.raises(ProtocolError, match="incompleto"):
            MessageReader(right).read()

    def test_falla_si_falta_content_length(self) -> None:
        left, right = _pair()
        with left, right:
            left.sendall(b"POST / HTTP/1.1\r\n\r\n")
            with pytest.raises(ProtocolError, match="Content-Length"):
                MessageReader(right).read()

    @pytest.mark.parametrize("valor", [b"abc", b"-1", str(MAX_BODY_BYTES + 1).encode()])
    def test_rechaza_content_length_invalido(self, valor: bytes) -> None:
        left, right = _pair()
        with left, right:
            left.sendall(b"POST / HTTP/1.1\r\nContent-Length: " + valor + b"\r\n\r\n")
            with pytest.raises(ProtocolError, match="Content-Length"):
                MessageReader(right).read()

    def test_un_timeout_no_pierde_lo_que_ya_se_leyo(self) -> None:
        # El cliente observador lee con plazo: un corte a mitad de mensaje debe poder retomarse.
        left, right = _pair()
        with left, right:
            right.settimeout(0.05)
            raw = encode_response(200, {"n": 1})
            left.sendall(raw[:-3])
            reader = MessageReader(right)
            with pytest.raises(TimeoutError):
                reader.read()
            left.sendall(raw[-3:])
            message = reader.read()
        assert message is not None
        assert message.status == 200
        assert parse_json_body(message.body) == {"n": 1}

    def test_rechaza_cabecera_sin_fin(self) -> None:
        left, right = _pair()
        with left, right:
            left.sendall(b"x" * 70_000)
            with pytest.raises(ProtocolError, match="Cabecera"):
                MessageReader(right).read()


class TestJson:
    """Serialización de cuerpos JSON."""

    def test_parse_rechaza_json_invalido(self) -> None:
        with pytest.raises(ProtocolError, match="JSON"):
            parse_json_body(b"{no es json")

    def test_parse_rechaza_bytes_invalidos(self) -> None:
        with pytest.raises(ProtocolError, match="JSON"):
            parse_json_body(b"\xff\xfe")

    def test_respuesta_convierte_decimal_de_dynamodb(self) -> None:
        # DynamoDB devuelve los números como Decimal, que json no sabe escribir.
        raw = encode_response(200, {"entero": Decimal("473"), "real": Decimal("1.5")})
        assert b'"entero": 473' in raw
        assert b'"real": 1.5' in raw

    def test_respuesta_rechaza_tipos_no_serializables(self) -> None:
        with pytest.raises(TypeError):
            encode_response(200, {"x": object()})

    def test_respuesta_conserva_acentos(self) -> None:
        assert "Concepción".encode() in encode_response(200, {"localidad": "Concepción"})

    def test_notificacion_sigue_el_diagrama_de_secuencia(self) -> None:
        assert build_notification("cpu", "reg", {"sede": "x"}) == {
            "UUID": "cpu",
            "ID": "reg",
            "ACTION": "change",
            "DATA": {"sede": "x"},
        }


json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text(),
    lambda inner: st.lists(inner, max_size=3) | st.dictionaries(st.text(), inner, max_size=3),
    max_leaves=8,
)


@given(payload=st.dictionaries(st.text(), json_values, max_size=5))
def test_propiedad_lo_que_se_envia_es_lo_que_se_recibe(payload: dict[str, Any]) -> None:
    # Hipótesis de la prueba: para cualquier objeto JSON, codificar y leer es la identidad.
    left, right = _pair()
    with left, right:
        left.sendall(encode_request(payload, host="h"))
        message = MessageReader(right).read()
    assert message is not None
    assert json.loads(message.body) == payload
