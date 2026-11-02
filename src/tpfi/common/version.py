"""Número de versión y de build del proyecto.

Los valores viven en los archivos `VERSION` y `BUILD` de la raíz del repositorio,
así hay una sola fuente de verdad que el código y las personas pueden leer.
"""

from pathlib import Path

# Este archivo está en src/tpfi/common: la raíz del repositorio queda tres niveles arriba.
_ROOT = Path(__file__).resolve().parents[3]


def _read(filename: str) -> str:
    """Devuelve el contenido de un archivo de la raíz, o "desconocido" si no existe."""
    try:
        return (_ROOT / filename).read_text(encoding="utf-8").strip()
    except OSError:
        # Ocurre si el paquete se instaló sin el repositorio (por ejemplo, como wheel).
        return "desconocido"


__version__ = _read("VERSION")
__build__ = _read("BUILD")
