"""Pruebas de la capa de persistencia y del patrón Singleton."""

import threading
from typing import Any
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import BotoCoreError, ClientError

from tpfi.common.errors import StorageError
from tpfi.common.protocol import TUPLE_FIELDS
from tpfi.persistence.corporate_data import CorporateDataTable
from tpfi.persistence.corporate_log import AuditEntry, CorporateLogTable
from tpfi.persistence.singleton import SingletonMeta

pytestmark = pytest.mark.usefixtures("aws_tables")


class TestSingletonPattern:
    """Verifica que las clases realmente se comportan como Singleton."""

    @pytest.mark.parametrize("table_class", [CorporateDataTable, CorporateLogTable])
    def test_dos_construcciones_devuelven_el_mismo_objeto(
        self, table_class: type[CorporateDataTable] | type[CorporateLogTable]
    ) -> None:
        assert table_class() is table_class()

    def test_cada_tabla_tiene_su_propia_instancia(self) -> None:
        assert CorporateDataTable() is not CorporateLogTable()  # type: ignore[comparison-overlap]

    def test_usan_la_metaclase_singleton(self) -> None:
        assert type(CorporateDataTable) is SingletonMeta
        assert type(CorporateLogTable) is SingletonMeta

    def test_la_construccion_es_segura_entre_hilos(self) -> None:
        # Muchos hilos arrancan a la vez: todos deben recibir la misma instancia.
        barrier = threading.Barrier(16)
        instances: list[CorporateDataTable] = []

        def build() -> None:
            barrier.wait()
            instances.append(CorporateDataTable())

        threads = [threading.Thread(target=build) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len({id(instance) for instance in instances}) == 1

    def test_el_constructor_corre_una_sola_vez(self) -> None:
        with patch("tpfi.persistence.corporate_data.open_table") as open_table:
            CorporateDataTable()
            CorporateDataTable()
        assert open_table.call_count == 1


class TestCorporateData:
    """Operaciones sobre la tabla de datos."""

    def test_get_devuelve_none_si_no_existe(self) -> None:
        assert CorporateDataTable().get("inexistente") is None

    def test_set_crea_registro_con_campos_no_informados_en_blanco(self) -> None:
        record = CorporateDataTable().upsert("nuevo", {"sede": "FCyT"})
        assert record["id"] == "nuevo"
        assert record["sede"] == "FCyT"
        for field in TUPLE_FIELDS - {"id", "sede"}:
            assert record[field] == ""

    def test_set_no_modifica_los_campos_no_informados(self) -> None:
        table = CorporateDataTable()
        table.upsert("r", {"sede": "FCyT", "cp": "3260"})
        record = table.upsert("r", {"cp": "3100"})
        assert (record["sede"], record["cp"]) == ("FCyT", "3100")
        assert table.get("r") == record

    def test_set_no_agrega_campos_a_filas_ya_existentes(self) -> None:
        # La tabla es compartida: hay filas viejas que no tienen todos los campos.
        boto3.resource("dynamodb").Table("CorporateData").put_item(Item={"id": "vieja", "nombre": "x"})
        record = CorporateDataTable().upsert("vieja", {"sede": "s"})
        assert record == {"id": "vieja", "nombre": "x", "sede": "s"}

    def test_set_concurrente_sobre_clave_nueva_no_pierde_datos(self) -> None:
        # Simula a otro proceso creando la fila entre el update y el put.
        table = CorporateDataTable()
        original_put = table._table.put_item

        def put_after_rival(**kwargs: object) -> object:
            boto3.resource("dynamodb").Table("CorporateData").put_item(Item={"id": "r", "cp": "1"})
            return original_put(**kwargs)  # type: ignore[arg-type]

        with patch.object(table._table, "put_item", side_effect=put_after_rival):
            record = table.upsert("r", {"sede": "s"})
        assert record == {"id": "r", "cp": "1", "sede": "s"}

    def test_list_devuelve_todo_ordenado(self) -> None:
        table = CorporateDataTable()
        table.upsert("b", {"sede": "2"})
        table.upsert("a", {"sede": "1"})
        assert [record["id"] for record in table.list_all()] == ["a", "b"]

    def test_list_sigue_la_paginacion_de_dynamodb(self) -> None:
        # Un scan devuelve hasta 1 MB por vez: hay que pedir las páginas restantes.
        table = CorporateDataTable()
        pages = [{"Items": [{"id": "a"}], "LastEvaluatedKey": {"id": "a"}}, {"Items": [{"id": "b"}]}]
        with patch.object(table._table, "scan", side_effect=pages) as scan:
            assert [record["id"] for record in table.list_all()] == ["a", "b"]
        assert scan.call_args_list[1].kwargs == {"ExclusiveStartKey": {"id": "a"}}

    def test_check_available_pasa_con_la_tabla_creada(self) -> None:
        CorporateDataTable().check_available()

    @pytest.mark.parametrize(
        "error",
        [ClientError({"Error": {"Code": "Boom", "Message": "x"}}, "Op"), BotoCoreError()],
    )
    def test_los_errores_de_aws_se_traducen(self, error: Exception) -> None:
        table = CorporateDataTable()
        with patch.object(table._table, "get_item", side_effect=error), pytest.raises(StorageError):
            table.get("x")


class TestCorporateLog:
    """Pista de auditoría."""

    def _rows(self) -> list[dict[str, Any]]:
        return list(boto3.resource("dynamodb").Table("CorporateLog").scan()["Items"])

    def test_registra_uuid_sesion_accion_id_y_timestamp(self) -> None:
        CorporateLogTable().record(AuditEntry(client_uuid="cpu", session_id="ses", action="get", record_id="reg"))
        row = self._rows()[0]
        assert (row["CPUid"], row["sessionid"], row["action"], row["requestedId"]) == ("cpu", "ses", "get", "reg")
        assert row["timestamp"]
        assert row["id"]

    def test_registra_datos_de_la_cpu_del_servidor(self) -> None:
        CorporateLogTable().record(AuditEntry(client_uuid="cpu", session_id="ses", action="list"))
        row = self._rows()[0]
        assert {"serverCPU", "os", "platform", "release", "node", "machine"} <= set(row)

    def test_sin_id_solicitado_no_guarda_ese_atributo(self) -> None:
        CorporateLogTable().record(AuditEntry(client_uuid="cpu", session_id="ses", action="list"))
        assert "requestedId" not in self._rows()[0]

    def test_cada_registro_tiene_clave_unica(self) -> None:
        log = CorporateLogTable()
        entry = AuditEntry(client_uuid="cpu", session_id="ses", action="list")
        log.record(entry)
        log.record(entry)
        assert len(self._rows()) == 2

    def test_los_errores_de_aws_se_traducen(self) -> None:
        log = CorporateLogTable()
        error = ClientError({"Error": {"Code": "Boom", "Message": "x"}}, "PutItem")
        with patch.object(log._table, "put_item", side_effect=error), pytest.raises(StorageError):
            log.record(AuditEntry(client_uuid="cpu", session_id="ses", action="list"))
