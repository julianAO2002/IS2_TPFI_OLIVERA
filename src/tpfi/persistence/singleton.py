"""Patrón Singleton implementado con una metaclase.

**Problema:** cada conexión del servidor se atiende en un hilo distinto. Sin control,
cada hilo crearía su propio acceso a DynamoDB.

**Solución:** una clase Singleton garantiza una única instancia para todo el programa.

¿Por qué una metaclase? En Python, escribir `Clase()` ejecuta `__call__` de la
metaclase, antes de `__new__` y `__init__`. Interceptar ese punto permite devolver
la instancia ya creada, y las clases que la usan no necesitan código adicional.
"""

import threading
from typing import Any, ClassVar


class SingletonMeta(type):
    """Metaclase que garantiza una única instancia por clase, aun entre hilos."""

    _instances: ClassVar[dict[type, Any]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Devuelve la instancia existente o la crea si es la primera vez."""
        # Sin el lock, dos hilos podrían ver a la vez que no hay instancia y crear dos.
        with SingletonMeta._lock:
            if cls not in SingletonMeta._instances:
                SingletonMeta._instances[cls] = super().__call__(*args, **kwargs)
            return SingletonMeta._instances[cls]

    @classmethod
    def clear_instances(mcs) -> None:
        """Olvida todas las instancias. Solo debe usarse para aislar pruebas."""
        with mcs._lock:
            mcs._instances.clear()
