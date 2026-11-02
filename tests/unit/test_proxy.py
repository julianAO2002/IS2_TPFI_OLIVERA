"""Pruebas del patrón Proxy."""

from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest

from tpfi.common.errors import RecordNotFoundError, StorageError
from tpfi.persistence.corporate_data import CorporateDataTable
from tpfi.persistence.corporate_log import AuditEntry, CorporateLogTable
from tpfi.server.observer import Observer, SubscriptionManager
from tpfi.server.proxy import CorporateServiceProxy
from tpfi.server.service import CorporateService, RealCorporateService


class Spy(Observer):
    """Observador que guarda las notificaciones recibidas."""

    def __init__(self) -> None:
        self.received: list[dict[str, Any]] = []

    def update(self, notification: dict[str, Any]) -> None:
        self.received.append(notification)

    def close(self) -> None:
        """No hay nada que cerrar."""


def _proxy(real: Any = None, log: Any = None, subject: Any = None) -> CorporateServiceProxy:
    return CorporateServiceProxy(
        real=MagicMock(spec=CorporateService) if real is None else real,
        log=MagicMock() if log is None else log,
        subscriptions=SubscriptionManager() if subject is None else subject,
        client_uuid="cpu",
        session_id="ses",
    )


class TestProxyPattern:
    """Verifica la estructura del patrón y el orden de las operaciones."""

    def test_proxy_y_servicio_real_comparten_la_interfaz(self) -> None:
        assert issubclass(CorporateServiceProxy, CorporateService)
        assert issubclass(RealCorporateService, CorporateService)

    def test_el_proxy_delega_en_el_servicio_real(self) -> None:
        real = MagicMock(spec=CorporateService)
        real.get_record.return_value = {"id": "r"}
        assert _proxy(real=real).get_record("r") == {"id": "r"}
        real.get_record.assert_called_once_with("r")

    @pytest.mark.parametrize(
        ("operation", "arguments"),
        [("get_record", ("r",)), ("list_records", ()), ("set_record", ("r", {"sede": "x"}))],
    )
    def test_sin_auditoria_no_se_toca_el_servicio_real(self, operation: str, arguments: tuple[Any, ...]) -> None:
        # Regla del proxy: ninguna operación ocurre sin quedar registrada.
        real = MagicMock(spec=CorporateService)
        log = MagicMock()
        log.record.side_effect = StorageError("sin log")
        with pytest.raises(StorageError):
            getattr(_proxy(real=real, log=log), operation)(*arguments)
        assert real.mock_calls == []

    def test_get_audita_antes_de_leer(self) -> None:
        calls = MagicMock()
        real = calls.real
        real.get_record.return_value = {"id": "r"}
        _proxy(real=real, log=calls.log).get_record("r")
        assert [call[0] for call in calls.mock_calls] == ["log.record", "real.get_record"]

    def test_auditoria_con_los_datos_del_pedido(self) -> None:
        log = MagicMock()
        real = MagicMock(spec=CorporateService)
        _proxy(real=real, log=log).get_record("r")
        log.record.assert_called_once_with(AuditEntry(client_uuid="cpu", session_id="ses", action="get", record_id="r"))

    def test_set_notifica_a_los_suscriptos_con_el_registro_final(self) -> None:
        real = MagicMock(spec=CorporateService)
        real.set_record.return_value = {"id": "r", "sede": "x"}
        subscriptions = SubscriptionManager()
        spy = Spy()
        subscriptions.attach(spy)
        result = _proxy(real=real, subject=subscriptions).set_record("r", {"sede": "x"})
        assert result == {"id": "r", "sede": "x"}
        assert spy.received == [{"UUID": "cpu", "ID": "r", "ACTION": "change", "DATA": result}]

    def test_get_y_list_no_notifican(self) -> None:
        subscriptions = SubscriptionManager()
        spy = Spy()
        subscriptions.attach(spy)
        real = MagicMock(spec=CorporateService)
        proxy = _proxy(real=real, subject=subscriptions)
        proxy.get_record("r")
        proxy.list_records()
        assert spy.received == []

    def test_un_set_fallido_no_notifica(self) -> None:
        real = MagicMock(spec=CorporateService)
        real.set_record.side_effect = StorageError("falla")
        subscriptions = SubscriptionManager()
        spy = Spy()
        subscriptions.attach(spy)
        with pytest.raises(StorageError):
            _proxy(real=real, subject=subscriptions).set_record("r", {"sede": "x"})
        assert spy.received == []

    def test_subscribe_audita_y_registra_el_observador(self) -> None:
        log = MagicMock()
        subscriptions = SubscriptionManager()
        _proxy(log=log, subject=subscriptions).subscribe(Spy())
        assert subscriptions.count() == 1
        log.record.assert_called_once_with(AuditEntry(client_uuid="cpu", session_id="ses", action="subscribe"))

    def test_subscribe_sin_auditoria_no_registra_el_observador(self) -> None:
        log = MagicMock()
        log.record.side_effect = StorageError("sin log")
        subscriptions = SubscriptionManager()
        with pytest.raises(StorageError):
            _proxy(log=log, subject=subscriptions).subscribe(Spy())
        assert subscriptions.count() == 0


@pytest.mark.usefixtures("aws_tables")
class TestServicioReal:
    """El servicio real contra el DynamoDB simulado."""

    def test_get_de_registro_inexistente(self) -> None:
        with pytest.raises(RecordNotFoundError, match="nada"):
            RealCorporateService(CorporateDataTable()).get_record("nada")

    def test_set_get_y_list(self) -> None:
        service = RealCorporateService(CorporateDataTable())
        created = service.set_record("r", {"sede": "x"})
        assert service.get_record("r") == created
        assert service.list_records() == [created]

    def test_recorrido_completo_impacta_en_las_dos_tablas(self) -> None:
        proxy = CorporateServiceProxy(
            real=RealCorporateService(CorporateDataTable()),
            log=CorporateLogTable(),
            subscriptions=SubscriptionManager(),
            client_uuid="cpu",
            session_id="ses",
        )
        proxy.set_record("r", {"sede": "x"})
        dynamodb = boto3.resource("dynamodb")
        assert dynamodb.Table("CorporateData").get_item(Key={"id": "r"}).get("Item", {})["sede"] == "x"
        assert dynamodb.Table("CorporateLog").scan()["Items"][0]["action"] == "set"
