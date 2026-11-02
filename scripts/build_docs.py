"""Genera la documentación HTML del paquete tpfi con pdoc en docs/api."""

import os

# Se ejecuta solo pdoc, con argumentos fijos.
import subprocess  # nosec B404
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    """Ejecuta pdoc sobre el paquete y devuelve su código de salida."""
    command = [sys.executable, "-m", "pdoc", "tpfi", "--output-directory", str(ROOT / "docs" / "api")]
    # pdoc tiene que poder importar el paquete, que vive dentro de src/.
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(command, check=False, env=environment).returncode  # nosec B603


if __name__ == "__main__":
    sys.exit(main())
