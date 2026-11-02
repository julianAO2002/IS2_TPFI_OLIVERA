# tpfi - Trabajo Practico Final Integrador IS2

Objetivo: entregar el TPFI completo (codigo, pruebas, UML, CI/CD, memoria y resumen).
Branch: PRs apilados a `main`. Entrega: `auto-chain` + `stacked-to-main`.
Test runner: `pytest` dentro de `.venv`.

## Specs

Los textos entre comillas son citas textuales del enunciado.

- S1 SingletonClient: "python singletonclient.py -i=input.json {-o=output.json}{-v}". Entrada `{"UUID","ID","ACTION"}`; "Acción a realizar (\"get\", \"set\" o \"list\")"; "Solo en el caso de acción \"set\" todos los campos del tuple CorporateData"; "Para la acción \"list\" no se debe indicar \"ID\"". Salida opcional: "de no indicarse la salida se emitirá por salida estándar". Socket TCP "típicamente localhost:8080".
- S2 ObserverClient: "python observerclient.py {-s=hostname} {-p=port} {-o=output.json}{-v}". Genera UUID y acción "subscribe", "Enviará el archivo mediante un método POST", "Puede recibir múltiples respuestas por lo que deberá mantener el puerto abierto". Reintenta "cada 30 segundos, parametrizable", y "de lograrla debe enviar la acción de subscripción".
- S3 Servidor: "python singletonproxyobserver.py {-p=port}{-v}", por defecto "*:8080". Termina "solo" por "cancelación manual o terminación por excepción otra que cierre del socket".
- S4 subscribe: registra UUID, audita en CorporateLog "UUID, sesión, acción solicitada y timestamp" y "registra el socket para uso posterior. Puede tener registrados tantos sockets como requerimiento de subscripción pudiera recibir".
- S5 get: audita "UUID, sesión, acción solicitada, ID solicitado y timestamp", devuelve el tuple "o la indicación de error" y "cierra la conexión".
- S6 list: audita y devuelve "todos los tuples de la tabla" o error, y cierra.
- S7 set: "en caso de no informar algún campo el mismo no será modificado. Si la clave no existiera previamente se creará un registro nuevo, los campos no informados se indicarán en blanco". Se audita y "será retransmitido al cliente solicitante y a todos los clientes que previamente se hubieran subscripto".
- S8 Patrones: "El acceso físico a la tabla CorporateLog y CorporateData debe implementarse como sendas funciones bajo sendos patrones singleton", "La gestión de subscripciones tiene que implementarse como un patrón observer", "La gestión de actualizaciones debe implementarse mediante un patron proxy". "modular y utilizando técnicas de OOP".
- S9 Infraestructura: sesion con `uuid4()`, CPU con `uuid.getnode()` y `platform`, debug con `logging` por salida estandar activado por "-v".
- S10 Aceptacion automatizada: "Camino feliz de cada una de las acciones, incluyendo registros en tabla CorporateLog"; "argumentos malformados (cada uno)"; "sin indicar datos mínimos necesarios"; "Manejo en clientes de server aplicativo caido"; "Intento de levantar dos veces el servidor de aplicaciones"; impacto en ambas tablas.
- S11 UML: "Diagrama UML de actividad para gestión de list/get/set" y "Diagrama UML de estado para la gestión del patrón observer".
- S12 Pruebas de patrones: "verificar además que las clases implementadas efectivamente se implementan como los patrones requeridos".
- S13 Proyecto: venv, CookieCutter, CONTEXT.md, README.md, CHANGELOG.md, REQUIREMENTS.TXT, licencia MIT, documentacion pdoc o sphinx, VERSION y BUILD.
- S14 Calidad: ruff, black, PEP8, PEP257, MyPy y PyRight sin errores, Pytest "85% o mejor", bandit sin observaciones, Trufflehog opcional.
- S15 CI/CD: "workflow en github integrando la fase de CI/CD completa" y documentacion actualizada "con cada PR exitoso".
- S16 Pedido del alumno (ver L1): repositorio nuevo, espanol, comentarios didacticos, pasos documentados, capturas, memoria final, resultados de test y cambios, entrega final y resumen.

Supuestos (marcados como tales, no son requisitos del enunciado):

- A1 Protocolo: mensajes con cabecera estilo HTTP POST y `Content-Length` sobre TCP. El diagrama muestra GET para subscribe pero el texto dice POST tres veces; se sigue el texto.
- A2 Notificacion: `{"UUID","ID","ACTION":"change","DATA":{...}}`, segun la Ilustracion 1.
- A3 La tabla es compartida entre alumnos: las pruebas reales solo escriben IDs propios con prefijo `OLIVERA-TEST-` y solo borran esas filas.
- A4 La region de la nota de aplicacion es `us-west-2`, pero las credenciales y las tablas estan en `us-east-1`; se usa la del perfil AWS.

## Tasks

| ID | Specs | Ruta | Estado | Commit / evidencia |
|----|-------|------|--------|--------------------|
| T1 | S13, S14, S15 | inline | pendiente | - |
| T2 | S8, S9 | inline | pendiente | - |
| T3 | S4-S7, S8 | inline | pendiente | - |
| T4 | S1-S3 | inline | pendiente | - |
| T5 | S10, S12, S14 | inline | pendiente | - |
| T6 | S11 | inline | pendiente | - |
| T7 | S10, S16 | inline | pendiente | - |
| T8 | S15, S16 | inline | pendiente | - |
| T9 | S16 | inline | pendiente | - |

Detalle: T1 herramientas y CI; T2 persistencia Singleton; T3 Proxy y Observer; T4 programas y red; T5 aceptacion y cobertura; T6 UML; T7 corridas reales en AWS y evidencias; T8 repo remoto, PRs y documentacion publicada; T9 memoria, entrega y resumen.

Ruta: inline porque ningun disparador de escritor aplica (las unidades dependen entre si).

## Log

- L1 (2026-11-02, pedido original): "hace el is2_tpfi, hacelo en español y con comentarios de manera que entienda un estudainte. crea un repositorio nuevo. documenta todos los paso, saca captturas para la memoria final y arma la memoria final. documeta cuanto te dan los test los cambios que hiciste y demas. hace la entrea final y un resumen para mi y todo lo que pida"
- L2 (2026-11-02): "ahit e agrge el otro pdf y por ahi tengo las cotnraseñas" / "ahora si estan las cred4enciales". Se usa esa credencial para las tablas del TP. Coincide con el perfil `~/.aws`; el JSON queda fuera del repo.
- L3 (2026-11-02): cookiecutter-pypackage 74e369c generado con `COOKIECUTTER_PYPACKAGE_GITHUB=skip` porque el hook interactivo falla sin TTY. Commit 0716354.
- L4 (2026-11-02): RDD activo. Pronostico: mas de 400 lineas, se usa `stacked-to-main`.
