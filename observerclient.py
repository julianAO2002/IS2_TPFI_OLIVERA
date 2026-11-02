"""Lanzador de ObserverClient: python observerclient.py {-s=hostname} {-p=port} {-o=output.json}{-v}."""

import sys
from pathlib import Path

# El código vive en src/: se agrega al path para poder ejecutar sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tpfi.clients.observer_client import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
