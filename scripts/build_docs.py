"""Genera la documentación HTML del paquete tpfi con pdoc en docs/api."""

import os

# Se ejecuta solo pdoc, con argumentos fijos.
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "api"
#: Páginas que deben existir. Que pdoc termine bien no alcanza: un `__all__` restrictivo
#: hace que omita los módulos sin informar ningún error.
REQUIRED_PAGES = [
    "tpfi.html",
    "tpfi/persistence/singleton.html",
    "tpfi/persistence/corporate_data.html",
    "tpfi/persistence/corporate_log.html",
    "tpfi/server/proxy.html",
    "tpfi/server/observer.html",
    "tpfi/server/app.html",
    "tpfi/clients/singleton_client.html",
    "tpfi/clients/observer_client.html",
]


def main() -> int:
    """Ejecuta pdoc sobre el paquete y comprueba que documentó todos los módulos."""
    command = [sys.executable, "-m", "pdoc", "tpfi", "--output-directory", str(OUTPUT)]
    # pdoc tiene que poder importar el paquete, que vive dentro de src/.
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    result = subprocess.run(command, check=False, env=environment).returncode  # nosec B603
    if result != 0:
        return result

    missing = [page for page in REQUIRED_PAGES if not (OUTPUT / page).is_file()]
    if missing:
        print("Faltan páginas de documentación: " + ", ".join(missing), file=sys.stderr)
        return 1
    print(f"Documentación generada: {len(REQUIRED_PAGES)} páginas obligatorias presentes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
