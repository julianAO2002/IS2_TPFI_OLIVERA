"""Fixtures compartidas por todas las pruebas.

Las pruebas unitarias nunca tocan AWS: `moto` intercepta las llamadas de boto3 y
responde con un DynamoDB simulado en memoria.
"""

from collections.abc import Iterator

import boto3
import pytest
from moto import mock_aws

from tpfi.persistence.singleton import SingletonMeta


@pytest.fixture
def aws_tables(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Crea las dos tablas del TP en un DynamoDB simulado."""
    # Credenciales falsas: si algo escapara de moto, AWS lo rechazaría.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("AWS_ENDPOINT_URL", raising=False)
    monkeypatch.delenv("AWS_PROFILE", raising=False)

    with mock_aws():
        dynamodb = boto3.resource("dynamodb")
        for name in ("CorporateData", "CorporateLog"):
            dynamodb.create_table(
                TableName=name,
                KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
        # Cada prueba arranca sin instancias Singleton creadas por la prueba anterior.
        SingletonMeta.clear_instances()
        yield
        SingletonMeta.clear_instances()
