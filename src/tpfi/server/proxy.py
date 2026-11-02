"""Patrón Proxy para la gestión de actualizaciones.

**Problema:** cada operación debe quedar auditada y cada cambio debe avisarse a los
suscriptos. Si esas reglas estuvieran mezcladas con el acceso a datos, sería fácil
olvidarlas al agregar una operación.

**Solución:** el proxy implementa la misma interfaz que el servicio real y se ubica
delante de él. Quien lo usa no nota la diferencia, pero toda llamada pasa primero por
el proxy, que agrega el comportamiento y recién después delega.

El orden importa: se audita antes de operar. Si la auditoría falla, la operación no
se ejecuta, y así no puede existir un cambio sin registro.
"""

import logging
from typing import Any

from tpfi.common.protocol import build_notification
from tpfi.persistence.corporate_log import AuditEntry, CorporateLogTable
from tpfi.server.observer import Observer, Subject
from tpfi.server.service import CorporateService

logger = logging.getLogger(__name__)


class CorporateServiceProxy(CorporateService):
    """Agrega auditoría y notificaciones al servicio real.

    Se crea un proxy por conexión, porque cada uno conoce al cliente y a la sesión.
    """

    def __init__(
        self,
        real: CorporateService,
        log: CorporateLogTable,
        subscriptions: Subject,
        client_uuid: str,
        session_id: str,
    ) -> None:
        """Recibe sus colaboradores en lugar de crearlos, lo que facilita probarlo."""
        self._real = real
        self._log = log
        self._subscriptions = subscriptions
        self._client_uuid = client_uuid
        self._session_id = session_id

    def _audit(self, action: str, record_id: str | None = None) -> None:
        """Registra la acción en CorporateLog."""
        logger.debug("Auditoría: cliente=%s sesión=%s acción=%s", self._client_uuid, self._session_id, action)
        self._log.record(
            AuditEntry(client_uuid=self._client_uuid, session_id=self._session_id, action=action, record_id=record_id)
        )

    def get_record(self, record_id: str) -> dict[str, Any]:
        """Audita y devuelve un registro."""
        self._audit("get", record_id)
        return self._real.get_record(record_id)

    def list_records(self) -> list[dict[str, Any]]:
        """Audita y devuelve todos los registros."""
        self._audit("list")
        return self._real.list_records()

    def set_record(self, record_id: str, fields: dict[str, str]) -> dict[str, Any]:
        """Audita, modifica el registro y avisa a los suscriptos."""
        self._audit("set", record_id)
        record = self._real.set_record(record_id, fields)
        self._subscriptions.notify(build_notification(self._client_uuid, record_id, record))
        return record

    def subscribe(self, observer: Observer) -> None:
        """Audita y registra un nuevo suscripto."""
        self._audit("subscribe")
        self._subscriptions.attach(observer)
