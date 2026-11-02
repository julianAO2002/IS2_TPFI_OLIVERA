"""Acceso a la tabla CorporateData bajo el patrón Singleton."""

import logging
import threading
from typing import Any

from botocore.exceptions import ClientError

from tpfi.common.protocol import TUPLE_FIELDS
from tpfi.persistence.dynamodb import open_table, translate_aws_errors
from tpfi.persistence.singleton import SingletonMeta

logger = logging.getLogger(__name__)

TABLE_NAME = "CorporateData"
_CONDITION_FAILED = "ConditionalCheckFailedException"


def _condition_failed(error: ClientError) -> bool:
    """Indica si DynamoDB rechazó la escritura porque no se cumplió su condición."""
    return error.response.get("Error", {}).get("Code") == _CONDITION_FAILED


class CorporateDataTable(metaclass=SingletonMeta):
    """Única puerta de entrada a la tabla CorporateData."""

    def __init__(self) -> None:
        """Abre la tabla. Por ser Singleton, se ejecuta una sola vez."""
        self._table = open_table(TABLE_NAME)
        # Los objetos "resource" de boto3 no son seguros entre hilos, y esta instancia
        # es compartida: el lock garantiza un solo acceso por vez.
        self._lock = threading.Lock()

    def check_available(self) -> None:
        """Verifica que la tabla exista y que las credenciales sirvan."""
        with self._lock, translate_aws_errors("verificar CorporateData"):
            self._table.load()

    def get(self, record_id: str) -> dict[str, Any] | None:
        """Devuelve un registro, o None si no existe."""
        with self._lock, translate_aws_errors("leer CorporateData"):
            return self._table.get_item(Key={"id": record_id}).get("Item")

    def list_all(self) -> list[dict[str, Any]]:
        """Devuelve todos los registros de la tabla, ordenados por id."""
        items: list[dict[str, Any]] = []
        arguments: dict[str, Any] = {}
        with self._lock, translate_aws_errors("listar CorporateData"):
            # Un scan devuelve hasta 1 MB por vez: LastEvaluatedKey avisa que hay más.
            while True:
                page = self._table.scan(**arguments)
                items.extend(page["Items"])
                if "LastEvaluatedKey" not in page:
                    break
                arguments["ExclusiveStartKey"] = page["LastEvaluatedKey"]
        return sorted(items, key=lambda item: str(item["id"]))

    def upsert(self, record_id: str, fields: dict[str, str]) -> dict[str, Any]:
        """Actualiza un registro o lo crea si la clave no existe.

        - Si existe, solo cambian los campos informados.
        - Si no existe, los campos no informados quedan en blanco.

        Leer y después escribir permitiría que dos clientes se pisen. Por eso cada
        escritura lleva una condición que DynamoDB evalúa de forma atómica. Hace falta
        porque otros procesos también escriben en esta tabla.
        """
        with self._lock, translate_aws_errors("escribir CorporateData"):
            try:
                return self._update_existing(record_id, fields)
            except ClientError as error:
                if not _condition_failed(error):
                    raise
            try:
                return self._create(record_id, fields)
            except ClientError as error:
                if not _condition_failed(error):
                    raise
            # Otro proceso creó la fila entre los dos intentos: ahora sí existe.
            logger.debug("Registro %s creado por otro proceso; se actualiza", record_id)
            return self._update_existing(record_id, fields)

    def _update_existing(self, record_id: str, fields: dict[str, str]) -> dict[str, Any]:
        """Modifica los campos informados de una fila que debe existir."""
        # Se usan alias (#f0, :v0) para que ningún campo choque con una palabra
        # reservada de DynamoDB.
        names = {"#pk": "id", **{f"#f{index}": name for index, name in enumerate(fields)}}
        values = {f":v{index}": value for index, value in enumerate(fields.values())}
        assignments = ", ".join(f"#f{index} = :v{index}" for index in range(len(fields)))
        response = self._table.update_item(
            Key={"id": record_id},
            UpdateExpression=f"SET {assignments}",
            ConditionExpression="attribute_exists(#pk)",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return response["Attributes"]

    def _create(self, record_id: str, fields: dict[str, str]) -> dict[str, Any]:
        """Crea una fila nueva con los campos no informados en blanco."""
        item: dict[str, Any] = {name: "" for name in TUPLE_FIELDS}
        item.update(fields)
        item["id"] = record_id
        self._table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(#pk)",
            ExpressionAttributeNames={"#pk": "id"},
        )
        return item
