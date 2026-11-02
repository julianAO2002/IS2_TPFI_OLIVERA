# IS2 TPFI: servicios corporativos con Singleton, Proxy y Observer

Trabajo Práctico Final Integrador de Ingeniería de Software II (UADER-FCyT), realizado por
Julián Olivera. Implementa tres programas en Python que acceden a datos corporativos alojados
en AWS DynamoDB, dejan una pista de auditoría y avisan cada cambio a los clientes suscriptos.

| Programa | Función |
|----------|---------|
| `singletonproxyobserver.py` | Servidor TCP: aplica los patrones, audita y notifica |
| `singletonclient.py` | Cliente que ejecuta `get`, `set` y `list` |
| `observerclient.py` | Cliente que se suscribe y recibe cada cambio |

## Inicio rápido

Requiere Python 3.12 o superior, y credenciales de AWS configuradas con `aws configure`.

```bash
python -m venv .venv
.venv\Scripts\activate          # En Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

Cada comando corre en una terminal distinta:

```bash
python singletonproxyobserver.py -v
python observerclient.py -o=avisos.json
python singletonclient.py -i=examples/input_set.json
python singletonclient.py -i=examples/input_get.json -o=output.json
python singletonclient.py -i=examples/input_list.json
```

Antes de ejecutar los ejemplos, reemplazar `UUID` por el identificador de la CPU:

```bash
python -c "import uuid; print(uuid.getnode())"
```

## Uso

```text
python singletonproxyobserver.py {-p=port}{-v}
python singletonclient.py -i=input.json {-o=output.json}{-s=hostname}{-p=port}{-v}
python observerclient.py {-s=hostname}{-p=port}{-o=output.json}{-r=segundos}{-v}
```

| Opción | Significado | Valor por defecto |
|--------|-------------|-------------------|
| `-i` | Archivo JSON con el pedido | Obligatorio |
| `-o` | Archivo de salida | Salida estándar |
| `-s` | Host del servidor | `localhost` |
| `-p` | Puerto TCP | `8080` |
| `-r` | Segundos entre reintentos | `30` |
| `-v` | Activa los mensajes de debug | Apagado |

Códigos de salida de los clientes: `0` éxito, `1` error de la operación, `2` argumentos inválidos.

## Formato de los pedidos

```json
{"UUID": "123456", "ID": "UADER-FCyT-IS2", "ACTION": "get"}
{"UUID": "123456", "ACTION": "list"}
{"UUID": "123456", "ID": "MI-REGISTRO", "ACTION": "set", "telefono": "03442 43-1442"}
```

- `set` modifica solo los campos informados. Si la clave no existe, crea el registro con el resto
  de los campos en blanco.
- Los errores se devuelven como `{"Error": "descripción"}`.
- Los suscriptos reciben `{"UUID": ..., "ID": ..., "ACTION": "change", "DATA": {...}}`.

## Arquitectura

```text
Clientes --TCP (JSON con POST)--> Servidor --> Proxy --> Servicio real --> CorporateData
                                                |                          (Singleton)
                                                |--> CorporateLog (Singleton)
                                                '--> Suscripciones (Observer) --> Clientes
```

| Patrón | Dónde | Para qué |
|--------|-------|----------|
| Singleton | `src/tpfi/persistence/` | Un único acceso a cada tabla, seguro entre hilos |
| Proxy | `src/tpfi/server/proxy.py` | Auditar antes de operar y notificar después de un `set` |
| Observer | `src/tpfi/server/observer.py` | Avisar a una cantidad variable de suscriptos |

Los diagramas UML están en [`docs/uml`](docs/uml). La memoria final está en
[`docs/memoria/Memoria_Final_TPFI_Olivera.pdf`](docs/memoria/Memoria_Final_TPFI_Olivera.pdf). La
documentación del código se publica en
[GitHub Pages](https://julianao2002.github.io/IS2_TPFI_OLIVERA/tpfi.html).

## Calidad

```bash
python scripts/quality.py        # ruff, black, PEP8, PEP257, mypy, pyright, bandit y pytest
python scripts/build_docs.py     # Documentación pdoc en docs/api
```

Las pruebas no necesitan credenciales: usan `moto`, un DynamoDB simulado. Para correr la
aceptación contra las tablas reales:

```bash
# En PowerShell: $env:TPFI_ACCEPTANCE_AWS="1"
TPFI_ACCEPTANCE_AWS=1 python -m pytest tests/acceptance -m acceptance
```

Esas tablas son compartidas. Las pruebas solo escriben claves `OLIVERA-TEST-`, solo borran esas
claves y no recorren CorporateLog con `scan`, para no agotar su capacidad de lectura.

## Seguridad

- Las credenciales nunca se versionan: boto3 las toma del perfil de AWS. El workflow de CI ejecuta
  TruffleHog en cada PR.
- El servidor no tiene autenticación ni cifrado, porque el enunciado no los pide. Escucha en todas
  las interfaces (`*:8080`): debe usarse solo en una red de confianza.

## Documentación relacionada

- [CHANGELOG.md](CHANGELOG.md): registro de cambios.
- [CONTEXT.md](CONTEXT.md): prompts de IA utilizados.
- [VERSION](VERSION) y [BUILD](BUILD): versión y número de build.

## Licencia

MIT. Ver [LICENSE](LICENSE).
