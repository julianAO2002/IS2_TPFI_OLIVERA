"""Interfaz del servicio corporativo y su implementación real."""

from abc import ABC, abstractmethod
from typing import Any

from tpfi.common.errors import RecordNotFoundError
from tpfi.persistence.corporate_data import CorporateDataTable


class CorporateService(ABC):
    """Operaciones disponibles sobre los datos corporativos.

    Es la interfaz común del patrón Proxy: quien la usa no distingue entre el proxy y
    el servicio real.
    """

    @abstractmethod
    def get_record(self, record_id: str) -> dict[str, Any]:
        """Devuelve un registro."""

    @abstractmethod
    def set_record(self, record_id: str, fields: dict[str, str]) -> dict[str, Any]:
        """Modifica o crea un registro y devuelve cómo quedó."""

    @abstractmethod
    def list_records(self) -> list[dict[str, Any]]:
        """Devuelve todos los registros."""


class RealCorporateService(CorporateService):
    """Sujeto real del patrón Proxy: solo sabe hablar con la tabla."""

    def __init__(self, table: CorporateDataTable) -> None:
        """Recibe la instancia Singleton de la tabla."""
        self._table = table

    def get_record(self, record_id: str) -> dict[str, Any]:
        """Devuelve un registro o informa que no existe."""
        record = self._table.get(record_id)
        if record is None:
            raise RecordNotFoundError(f"No existe el registro {record_id}.")
        return record

    def set_record(self, record_id: str, fields: dict[str, str]) -> dict[str, Any]:
        """Modifica o crea un registro."""
        return self._table.upsert(record_id, fields)

    def list_records(self) -> list[dict[str, Any]]:
        """Devuelve todos los registros."""
        return self._table.list_all()
