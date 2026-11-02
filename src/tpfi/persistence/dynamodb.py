"""Conexión con DynamoDB y traducción de sus errores.

Las credenciales nunca aparecen en el código: boto3 las toma del perfil configurado
con `aws configure` o de las variables de entorno.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from tpfi.common.errors import StorageError

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import Table

logger = logging.getLogger(__name__)

# Sin límites, una caída de red dejaría a un hilo del servidor esperando varios minutos.
_CONFIG = Config(connect_timeout=5, read_timeout=10, retries={"max_attempts": 3})


def open_table(name: str) -> "Table":
    """Devuelve el objeto boto3 de una tabla. No hace ninguna llamada de red."""
    try:
        return boto3.resource("dynamodb", config=_CONFIG).Table(name)
    except BotoCoreError as error:
        # Por ejemplo, cuando no hay una región configurada.
        logger.debug("No se pudo crear el recurso DynamoDB: %s", error)
        raise StorageError("La configuración de AWS es inválida.") from error


@contextmanager
def translate_aws_errors(operation: str) -> Iterator[None]:
    """Convierte los errores de AWS en `StorageError`.

    El detalle queda en el log de debug; al cliente le llega un mensaje genérico para
    no exponer datos internos de la infraestructura.
    """
    try:
        yield
    except (ClientError, BotoCoreError) as error:
        logger.debug("Error de AWS en %s: %s", operation, error)
        raise StorageError(f"No se pudo completar la operación en la base de datos: {operation}.") from error
