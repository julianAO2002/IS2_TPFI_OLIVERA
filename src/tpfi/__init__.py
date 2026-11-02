"""TPFI de Ingeniería de Software II: servicios corporativos sobre AWS DynamoDB.

El sistema tiene tres programas que se comunican por TCP:

- `tpfi.clients.singleton_client`: consulta y modifica datos corporativos.
- `tpfi.clients.observer_client`: se suscribe y recibe cada cambio.
- `tpfi.server.app`: servidor que aplica los patrones del trabajo.

Los patrones pedidos por el enunciado están en:

- Singleton: `tpfi.persistence.singleton`, usado por `tpfi.persistence.corporate_data`
  y `tpfi.persistence.corporate_log`.
- Proxy: `tpfi.server.proxy`.
- Observer: `tpfi.server.observer`.
"""

from tpfi import clients, common, persistence, server
from tpfi.common.version import __build__, __version__

# pdoc solo documenta lo que figura acá: si faltan los subpaquetes, omite sus módulos.
__all__ = ["__build__", "__version__", "clients", "common", "persistence", "server"]
