"""Acceso a la tabla CorporateLog (pista de auditoría) bajo el patrón Singleton."""

import platform
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tpfi.persistence.dynamodb import open_table, translate_aws_errors
from tpfi.persistence.singleton import SingletonMeta

TABLE_NAME = "CorporateLog"


@dataclass(frozen=True)
class AuditEntry:
    """Datos de una acción que debe quedar registrada."""

    client_uuid: str
    session_id: str
    action: str
    record_id: str | None = None


def _cpu_info() -> dict[str, str]:
    """Devuelve los datos de la CPU donde corre el servidor."""
    return {
        # getnode() es el identificador único de la CPU que pide el enunciado.
        "serverCPU": str(uuid.getnode()),
        "os": platform.system(),
        "platform": platform.platform(),
        "release": platform.release(),
        "node": platform.node(),
        "machine": platform.machine(),
    }


class CorporateLogTable(metaclass=SingletonMeta):
    """Única puerta de entrada a la tabla CorporateLog."""

    def __init__(self) -> None:
        """Abre la tabla. Por ser Singleton, se ejecuta una sola vez."""
        self._table = open_table(TABLE_NAME)
        # Igual que en CorporateData: el recurso de boto3 no es seguro entre hilos.
        self._lock = threading.Lock()

    def check_available(self) -> None:
        """Verifica que la tabla exista y que las credenciales sirvan."""
        with self._lock, translate_aws_errors("verificar CorporateLog"):
            self._table.load()

    def record(self, entry: AuditEntry) -> str:
        """Agrega una fila a la pista de auditoría y devuelve su clave."""
        row: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "CPUid": entry.client_uuid,
            "sessionid": entry.session_id,
            "action": entry.action,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **_cpu_info(),
        }
        # DynamoDB no admite valores None: si no hay ID, el atributo se omite.
        if entry.record_id is not None:
            row["requestedId"] = entry.record_id
        with self._lock, translate_aws_errors("registrar en CorporateLog"):
            self._table.put_item(Item=row)
        return str(row["id"])
