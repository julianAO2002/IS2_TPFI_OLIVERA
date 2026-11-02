"""Genera memoria.html a partir de las evidencias reales de docs/evidencias.

Las salidas de los programas se leen de los archivos guardados durante las corridas: así el
texto de la memoria no puede diferir de lo que realmente ocurrió. El PDF se obtiene imprimiendo
ese HTML con un navegador.
"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidencias"
OUTPUTS = EVIDENCE / "salidas"
REPO_URL = "https://github.com/julianAO2002/IS2_TPFI_OLIVERA"
DOCS_URL = "https://julianao2002.github.io/IS2_TPFI_OLIVERA/tpfi.html"


def read(name: str) -> str:
    """Devuelve una salida guardada, sin líneas vacías al final."""
    return (OUTPUTS / f"{name}.txt").read_text(encoding="utf-8").strip()


def box(text: str) -> str:
    """Muestra texto con fuente no proporcional, como pide la nota del enunciado."""
    return f'<pre class="ev">{html.escape(text)}</pre>'


figure_number = 0


def shot(name: str, caption: str, width: int = 100) -> str:
    """Inserta una captura numerada, referenciando la condición que demuestra."""
    global figure_number
    figure_number += 1
    return (
        f'<figure><img src="../evidencias/capturas/{name}.png" style="width:{width}%" alt="{html.escape(caption)}">'
        f"<figcaption>Figura {figure_number}. {caption}</figcaption></figure>"
    )


def uml(name: str, caption: str, width: int = 100) -> str:
    """Inserta un diagrama numerado."""
    global figure_number
    figure_number += 1
    return (
        f'<figure><img src="../uml/{name}.png" style="width:{width}%" alt="{html.escape(caption)}">'
        f"<figcaption>Figura {figure_number}. {caption}</figcaption></figure>"
    )


def table(headers: list[str], rows: list[list[str]], widths: list[int] | None = None) -> str:
    """Arma una tabla HTML."""
    columns = ""
    if widths:
        columns = "<colgroup>" + "".join(f'<col style="width:{w}%">' for w in widths) + "</colgroup>"
    head = "".join(f"<th>{cell}</th>" for cell in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table>{columns}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


coverage_text = read("16_cobertura")
total_tests = re.search(r"(\d+) passed", coverage_text).group(1)
total_coverage = re.search(r"Total coverage: ([\d.]+)%", coverage_text).group(1)
acceptance_tests = re.search(r"(\d+) passed", read("17_aceptacion_aws")).group(1)
unit_tests = int(total_tests) - int(acceptance_tests)
coverage_lines = [line for line in coverage_text.splitlines() if line.startswith(("Name", "src", "TOTAL", "---"))]

CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm;
  @bottom-center { content: "UADER-FCyT-IS2 · TPFI · Julián Olivera · Página " counter(page); font: 8.5pt Arial, sans-serif; color: #555; } }
@page :first { @bottom-center { content: none; } }
* { box-sizing: border-box; }
body { font: 10.5pt/1.45 Arial, Helvetica, sans-serif; color: #1a1a1a; margin: 0; }
h1 { font-size: 17pt; color: #12395b; border-bottom: 2px solid #12395b; padding-bottom: 4px; margin: 0 0 12px; break-before: page; }
h2 { font-size: 12.5pt; color: #12395b; margin: 16px 0 6px; break-after: avoid; }
p { margin: 6px 0; } ul, ol { margin: 6px 0; padding-left: 20px; } li { margin: 2px 0; }
table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 9pt; table-layout: fixed; }
th { background: #12395b; color: #fff; text-align: left; padding: 4px 6px; }
td { border: 1px solid #c4ccd4; padding: 4px 6px; vertical-align: top; overflow-wrap: anywhere; }
tr { break-inside: avoid; } tbody tr:nth-child(even) td { background: #f3f6f9; }
pre.ev { font: 8pt/1.25 "Courier New", Courier, monospace; background: #f4f4f4; border-left: 3px solid #12395b; padding: 6px 8px; white-space: pre-wrap; overflow-wrap: anywhere; margin: 6px 0; }
code { font: 9pt "Courier New", Courier, monospace; }
figure { margin: 8px 0 12px; text-align: center; break-inside: avoid; }
figure img { max-height: 225mm; border: 1px solid #c4ccd4; }
figcaption { font-size: 8.5pt; color: #444; margin-top: 3px; }
.cover { height: 250mm; display: flex; flex-direction: column; justify-content: center; text-align: center; }
.cover .uni { font-size: 13pt; color: #444; } .cover .t { font-size: 27pt; color: #12395b; font-weight: bold; margin: 24px 0 8px; }
.cover .s { font-size: 15pt; color: #12395b; margin-bottom: 40px; } .cover .d { font-size: 11pt; line-height: 1.7; }
.note { background: #eef4fa; border-left: 3px solid #12395b; padding: 6px 10px; margin: 8px 0; }
.toc li { margin: 3px 0; }
h1.flow { break-before: auto; margin-top: 18px; break-after: avoid; }
pre.ev { break-inside: avoid; }
"""

fulfilment = table(
    ["Requisito del enunciado", "Resultado", "Evidencia"],
    [
        ["SingletonClient: get, set, list; salida a archivo o pantalla", "Cumplido", "Figuras 7 a 10; <code>src/tpfi/clients/singleton_client.py</code>"],
        ["ObserverClient: suscripción, múltiples avisos, reintento", "Cumplido", "Figuras 6, 15 y 16"],
        ["Servidor con Proxy, Singleton y Observer; pista auditable", "Cumplido", "Figuras 5 y 17; sección 3"],
        ["Tablas accedidas con sendos Singleton", "Cumplido", "<code>src/tpfi/persistence/</code>; pruebas de patrón"],
        ["Suscripciones con Observer; actualizaciones con Proxy", "Cumplido", "<code>src/tpfi/server/observer.py</code> y <code>proxy.py</code>"],
        ["Sesión con uuid4, CPU con getnode y platform", "Cumplido", "Figura 17; <code>corporate_log.py</code>"],
        ["Debug con logging por salida estándar, activado con -v", "Cumplido", "Figura 5"],
        ["Aceptación automatizada de los 5 grupos de casos", "Cumplido", f"Figura 20: {acceptance_tests} casos sobre AWS real"],
        ["UML de actividad y de estado", "Cumplido", "Figuras 1 y 2"],
        ["Pruebas que verifican los patrones", "Cumplido", "Sección 6.2"],
        ["venv, CookieCutter, CONTEXT, README, CHANGELOG, requirements, MIT, VERSION, BUILD", "Cumplido", "Raíz del repositorio; sección 5"],
        ["ruff, black, PEP8, PEP257, MyPy, PyRight sin errores", "Cumplido", "Figura 18"],
        ["Pytest con cobertura de 85% o mejor", f"Cumplido: {total_coverage}%", "Figura 19"],
        ["bandit sin observaciones", "Cumplido", "Figura 18"],
        ["Trufflehog (opcional)", "Cumplido", "Figura 21 y job de CI"],
        ["Workflow de CI/CD en GitHub", "Cumplido", "Figuras 24 a 27"],
        ["Documentación con pdoc actualizada con cada PR", "Cumplido", "Figuras 28 y 29"],
    ],
    [50, 14, 36],
)

SAMPLE = '{"UUID": "39908810720395", "ID": "UADER-FCyT-IS2", "ACTION": "get"}'
MESSAGE = f"POST /tpfi HTTP/1.1\nHost: localhost\nContent-Type: application/json\nContent-Length: {len(SAMPLE)}\n\n{SAMPLE}"
body = f"""
<div class="cover">
  <div class="uni">Universidad Autónoma de Entre Ríos<br>Facultad de Ciencia y Tecnología</div>
  <div class="t">Memoria Final</div>
  <div class="s">Trabajo Práctico Final Integrador<br>Patrón Proxy / Singleton / Observer en entorno AWS</div>
  <div class="d">Ingeniería de Software II<br>Alumno: Julián Olivera<br>Fecha: 2 de noviembre de 2026<br>
  Versión 1.0.0<br>Repositorio: {REPO_URL}</div>
</div>

<h1>Índice</h1>
<ol class="toc">
<li>Resumen</li><li>Problema</li><li>Diseño</li><li>Implementación</li><li>Pasos realizados</li>
<li>Validación y verificación</li><li>Calidad del código</li><li>Integración y entrega continua</li>
<li>Cambios y defectos encontrados</li><li>Limitaciones conocidas</li><li>Uso de inteligencia artificial</li>
<li>Conclusiones</li><li>Anexo: ejecución del sistema</li>
</ol>

<h1>1. Resumen</h1>
<p>Se desarrollaron tres programas en Python que permiten consultar y modificar datos corporativos
alojados en AWS DynamoDB. Un servidor concentra el acceso a las tablas, deja una pista de auditoría
de cada acción y avisa los cambios a los clientes suscriptos.</p>
{table(["Indicador", "Resultado"], [
    ["Pruebas automatizadas", f"{total_tests} aprobadas de {total_tests}: {unit_tests} unitarias y {acceptance_tests} de aceptación"],
    ["Aceptación contra AWS real", f"{acceptance_tests} de {acceptance_tests} aprobadas, en 68 segundos"],
    ["Cobertura de código", f"{total_coverage}% (mínimo exigido: 85%)"],
    ["ruff, black, PEP8, PEP257, mypy, pyright, bandit", "Sin errores ni observaciones"],
    ["TruffleHog sobre el historial", "0 secretos"],
    ["Workflow de CI", "5 de 5 controles aprobados en cada PR, en Ubuntu y Windows"],
], [45, 55])}
<h2>Cumplimiento de la consigna</h2>
{fulfilment}

<h1>2. Problema</h1>
<p>Un sistema aplicativo necesita servicios corporativos centralizados: dirección oficial, CUIT,
teléfono de contacto e identificador único de secuencia. Se implementan tres funciones (recuperar,
modificar y listar) sobre dos tablas de DynamoDB que ya existen: <code>CorporateData</code>, con los
datos, y <code>CorporateLog</code>, con los registros de acceso y modificación.</p>
<h2>Puntos del enunciado que requirieron una decisión</h2>
{table(["Situación", "Decisión"], [
    ["La Ilustración 1 muestra GET para subscribe, pero el texto dice POST tres veces.", "Se sigue el texto: todos los pedidos usan POST."],
    ["La nota de aplicación indica la región us-west-2.", "Las tablas y las credenciales están en us-east-1. La región se toma del perfil de AWS, no del código."],
    ["La Ilustración 1 incluye una respuesta OK||Error del observador al servidor; el texto no la describe.", "No se implementa ese mensaje. El servidor detecta la caída de un suscripto por el fallo de envío o el cierre del socket."],
    ["El enunciado nombra REQUIREMENTS.TXT y requirements.txt.", "Se usa <code>requirements.txt</code>, el nombre que entiende pip por convención."],
    ["CorporateData es compartida por todos los alumnos.", "Las pruebas reales solo escriben claves <code>OLIVERA-TEST-</code> y solo borran esas claves."],
], [55, 45])}

<h1>3. Diseño</h1>
<h2>Arquitectura</h2>
<p>Los clientes se conectan al servidor por TCP. Cada conexión se atiende en un hilo propio y cada
pedido pasa por el proxy, que audita y recién después delega en el servicio real.</p>
{box('''Clientes --TCP (JSON con POST)--> Servidor --> Proxy --> Servicio real --> CorporateData
                                                |                          (Singleton)
                                                |--> CorporateLog (Singleton)
                                                '--> Suscripciones (Observer) --> Clientes''')}
<h2>Patrones</h2>
{table(["Patrón", "Problema que resuelve", "Implementación"], [
    ["Singleton", "Varios hilos necesitan acceder a las tablas; debe haber un solo punto de acceso por tabla.", "Metaclase <code>SingletonMeta</code> con un lock; la usan <code>CorporateDataTable</code> y <code>CorporateLogTable</code>."],
    ["Proxy", "Toda operación debe auditarse, y los cambios deben notificarse, sin mezclar esas reglas con el acceso a datos.", "<code>CorporateServiceProxy</code> implementa la misma interfaz que <code>RealCorporateService</code>. Si la auditoría falla, la operación no se ejecuta."],
    ["Observer", "Hay que avisar a una cantidad variable de clientes sin que quien modifica datos los conozca.", "<code>SubscriptionManager</code> es el sujeto y <code>SocketObserver</code> el observador concreto, con su propia cola de envío."],
], [13, 43, 44])}
<h2>Decisiones técnicas</h2>
{table(["Decisión", "Motivo"], [
    ["Mensajes con cabecera <code>Content-Length</code>", "TCP entrega un flujo de bytes: sin esa cabecera el receptor no sabe dónde termina cada mensaje."],
    ["Escrituras condicionales en DynamoDB", "Leer y luego escribir permitiría que dos clientes se pisen. La condición se evalúa de forma atómica."],
    ["Lock dentro de cada tabla", "Los recursos de boto3 no son seguros entre hilos y la instancia Singleton es compartida."],
    ["Auditar antes de operar", "Así no puede existir un cambio sin registro. Un intento fallido queda registrado igual."],
    ["<code>socket.create_server</code>", "Resuelve la diferencia entre sistemas: en Windows, SO_REUSEADDR permitiría dos servidores en el mismo puerto."],
    ["Validación en cliente y en servidor", "El cliente falla antes de conectarse, y el servidor nunca confía en lo que recibe por la red."],
], [38, 62])}
<h2>Diagrama de actividad: list, get y set</h2>
{uml("actividad_proxy", "Actividad de la gestión de list, get y set en el servidor (patrón Proxy).", 82)}
<h2>Diagrama de estado: suscripción</h2>
{uml("estado_observer", "Estado de una suscripción en el servidor (patrón Observer).", 62)}
<h2>Diagrama de clases</h2>
{uml("clases_patrones", "Clases que implementan los tres patrones.", 80)}

<h1>4. Implementación</h1>
{box('''singletonproxyobserver.py    Lanzador del servidor
singletonclient.py           Lanzador del cliente de consultas
observerclient.py            Lanzador del cliente suscriptor
src/tpfi/common/             Protocolo, errores, línea de comandos y versión
src/tpfi/persistence/        Singleton y acceso a CorporateData y CorporateLog
src/tpfi/server/             Proxy, Observer, servicio real y servidor TCP
src/tpfi/clients/            SingletonClient y ObserverClient
tests/unit/                  Pruebas unitarias y de patrones
tests/acceptance/            Pruebas de aceptación con procesos reales
docs/                        UML, evidencias y memoria''')}
<p>Todo el código está en clases, salvo los lanzadores y las funciones de utilidad. Los comentarios y
docstrings están en español y explican el porqué de cada decisión. Los identificadores están en
inglés, para coincidir con los nombres de los patrones y del enunciado.</p>
<h2>Formato de los mensajes</h2>
{box(MESSAGE)}
<p>Las respuestas exitosas devuelven el tuple o el arreglo de tuples. Los errores devuelven
<code>{{"Error": "descripción"}}</code>. Cada suscriptor recibe
<code>{{"UUID", "ID", "ACTION": "change", "DATA"}}</code>, según la Ilustración 1.</p>

<h1>5. Pasos realizados</h1>
<ol>
<li><b>Análisis.</b> Lectura del enunciado, la nota de aplicación y los programas de diagnóstico.
Consulta del esquema real de las tablas: clave <code>id</code> de tipo texto, y capacidad de lectura
de 1 RCU en CorporateData y 10 en CorporateLog.</li>
<li><b>Esqueleto.</b> Generación con cookiecutter-pypackage (primer commit, sin modificar).</li>
<li><b>Ambiente.</b> Creación del venv e instalación de versiones fijas con <code>requirements.txt</code>.</li>
<li><b>Herramientas.</b> Configuración de ruff, black, pycodestyle, pydocstyle, mypy, pyright, bandit,
pytest y los workflows de CI y CD.</li>
<li><b>Protocolo y Singleton.</b> Desarrollo guiado por pruebas: primero la prueba que falla y después
el código.</li>
<li><b>Proxy, Observer y servidor.</b> Mismo método.</li>
<li><b>Clientes.</b> SingletonClient y ObserverClient, con reconexión.</li>
<li><b>Aceptación.</b> Primero contra un DynamoDB simulado (moto) y después contra AWS real.</li>
<li><b>Revisión.</b> Revisión independiente por lentes de riesgo, resiliencia y fiabilidad.</li>
<li><b>Publicación.</b> Repositorio en GitHub, con búsqueda de secretos previa al primer push.</li>
<li><b>Integración.</b> PR 1, PR 6 y PR 7 integrados con todos los controles aprobados.</li>
<li><b>Evidencias.</b> Corridas reales y capturas sobre el código final.</li>
<li><b>Memoria.</b> Este documento, generado a partir de las salidas guardadas.</li>
</ol>
<h2>Commits principales</h2>
{table(["Commit", "Descripción"], [
    ["0716354", "Esqueleto generado con cookiecutter-pypackage"],
    ["7e4feb5", "Herramientas de calidad, CI y CD"],
    ["40b751e", "Protocolo y acceso Singleton a DynamoDB"],
    ["ba40c72", "Servidor Proxy y Observer, clientes y pruebas de aceptación"],
    ["ffccc45", "La auditoría se lee por clave, para no agotar la capacidad de CorporateLog"],
    ["8956a17", "Cola de envío por suscriptor, para no frenar los set"],
    ["cca859d", "Registro de build 2, cambios y prueba de versión"],
    ["bb852c9", "Documentación de todos los módulos y verificación de las páginas generadas"],
    ["c90219f", "Exportación del paquete y pruebas de la generación de documentación"],
], [18, 82])}

<h1>6. Validación y verificación</h1>
<div class="note">Salvo aclaración, las capturas son de ventanas reales de terminal, ejecutando los
programas contra las tablas reales de AWS. Las salidas completas están en
<code>docs/evidencias/salidas</code> y los logs de debug de las pruebas en <code>docs/evidencias/logs</code>.
El UUID que se ve es el número de CPU obtenido con <code>uuid.getnode()</code>.</div>
<h2>6.1 Casos de prueba de aceptación</h2>
{table(["Grupo del enunciado", "Casos", "Qué se verifica"], [
    ["Camino feliz de cada acción", "7", "get, set, list y subscribe; archivo de salida; registro en CorporateLog"],
    ["Argumentos malformados (cada programa)", "10", "Terminan con código 2 y mensaje de error"],
    ["Sin datos mínimos", "11", "Se rechazan en cliente y servidor; las tablas no cambian"],
    ["Servidor caído", "3", "Error en el cliente; el observador reintenta y se vuelve a suscribir"],
    ["Levantar dos veces el servidor", "1", "El segundo falla y el primero sigue atendiendo"],
], [36, 9, 55])}
<p>Cada prueba lee las tablas directamente con boto3, sin pasar por el sistema bajo prueba. Por eso el
resultado no depende de lo que el sistema dice haber hecho.</p>
<h2>6.2 Pruebas de los patrones</h2>
{table(["Patrón", "Qué demuestran las pruebas"], [
    ["Singleton", "Dos construcciones devuelven el mismo objeto; cada tabla tiene su instancia; 16 hilos simultáneos reciben la misma; el constructor corre una sola vez."],
    ["Proxy", "Comparte la interfaz con el servicio real y delega en él; audita antes de operar; sin auditoría no toca el servicio real; solo un set exitoso notifica."],
    ["Observer", "Notifica a todos; admite varias suscripciones del mismo UUID; un suscripto caído o trabado no afecta a los demás; los avisos llegan en orden."],
], [16, 84])}
<h2>6.3 Diagnóstico del ambiente</h2>
{shot("01_diagnostico", "Condición: acceso a las tablas verificado con el programa IS2_TPFI_test.py de la cátedra.", 92)}
<h2>6.4 Camino feliz</h2>
{shot("02_servidor", "Condición: traza del servidor con -v. Cada acción muestra su sesión uuid4 y su clave de auditoría.", 92)}
{shot("03_observador", "Condición: el observador recibe cada cambio (subscribe) y mantiene abierto el socket.", 92)}
{shot("04_set_crea", "Condición: set de una clave nueva, con todos los campos del tuple.", 92)}
{shot("05_get", "Condición: get con el pedido de entrada y la salida grabada en output_get.json.", 92)}
{shot("06_list", "Condición: list devuelve un arreglo con todos los tuples de la tabla.", 92)}
{shot("07_set_parcial", "Condición: set de un solo campo; los demás no se modifican.", 92)}
<h2>6.5 Casos de error</h2>
{shot("08_argumentos", "Condición: argumentos malformados en cada programa (código de salida 2).", 92)}
{shot("09_datos_minimos", "Condición: pedidos sin datos mínimos y registro inexistente.", 92)}
{shot("10_doble_servidor", "Condición: intento de levantar dos veces el servidor.", 92)}
{shot("11_servidor_caido", "Condición: SingletonClient con el servidor caído.", 92)}
{shot("12_observador_reintenta", "Condición: ObserverClient reintenta con el servidor caído (-r=5).", 92)}
{shot("13_observador_resuscribe", "Condición: al volver el servidor, ObserverClient se suscribe de nuevo solo.", 92)}
<h2>6.6 Impacto en las tablas</h2>
{shot("14_tablas", "Condición: lectura directa con AWS CLI de CorporateData y de la fila de auditoría del set.", 92)}

<h1>7. Calidad del código</h1>
{table(["Herramienta", "Control", "Resultado"], [
    ["ruff", "Reglas de formato y errores frecuentes", "Sin errores"],
    ["black", "Formato consistente", "Sin cambios pendientes"],
    ["pycodestyle", "PEP8", "Sin errores"],
    ["pydocstyle", "PEP257 en docstrings", "Sin errores"],
    ["mypy", "Tipos, en modo estricto", "Sin errores"],
    ["pyright", "Tipos", "0 errores, 0 advertencias"],
    ["bandit", "Seguridad básica", "Sin observaciones"],
    ["pytest", "Pruebas y cobertura", f"{total_tests} aprobadas, {total_coverage}%"],
    ["TruffleHog 3.99.8", "Secretos en el historial", "0 verificados, 0 sin verificar"],
], [25, 45, 30])}
{shot("15_calidad_estatica", "Condición: ruff, black, PEP8, PEP257, mypy, pyright y bandit terminan con código 0.", 92)}
{shot("16_cobertura", f"Condición: {total_tests} pruebas aprobadas y cobertura de {total_coverage}%.", 92)}
<h2>Cobertura por módulo</h2>
{box(chr(10).join(coverage_lines))}
<p>Las líneas sin cubrir corresponden a fallos del entorno difíciles de provocar, como la falta de
región de AWS o la ausencia de los archivos VERSION y BUILD.</p>
{shot("17_aceptacion_aws", f"Condición: {acceptance_tests} pruebas de aceptación aprobadas contra las tablas reales de AWS.", 92)}
{shot("18_trufflehog", "Condición: TruffleHog sobre todo el historial de git, sin secretos.", 92)}
<h2>Manejo de credenciales</h2>
<ul>
<li>Las credenciales nunca se escriben en el código: boto3 las toma del perfil de AWS.</li>
<li>El archivo de credenciales de la cátedra queda fuera del repositorio.</li>
<li><code>.gitignore</code> excluye <code>*credentials*.json</code> y <code>*.pem</code>.</li>
<li>Además de TruffleHog, se buscó el valor literal de la clave en archivos e historial: 0 coincidencias.</li>
<li>El CI no recibe credenciales de AWS: sus pruebas usan moto.</li>
</ul>

<h1>8. Integración y entrega continua</h1>
{table(["Workflow", "Se dispara", "Qué hace"], [
    ["CI (<code>ci.yml</code>)", "En cada PR", "Calidad estática; pruebas en Ubuntu y Windows con cobertura mínima de 85%; TruffleHog; documentación pdoc."],
    ["CD (<code>cd.yml</code>)", "Al integrar en main", "Repite el CI como compuerta; construye el paquete; publica la documentación en GitHub Pages."],
], [22, 18, 60])}
<p>Las acciones están fijadas por hash de commit, para que nadie pueda cambiar su contenido sin que se
note. Las capturas de esta sección se tomaron sin iniciar sesión, desde el sitio público.</p>
{shot("20_repositorio", "Condición: repositorio público en GitHub.", 80)}
{shot("21_pull_requests", "Condición: PRs del proyecto.", 80)}
{shot("22_pr_checks", "Condición: PR 6 integrado con sus 5 controles aprobados.", 76)}
{shot("23_actions", "Condición: historial de ejecuciones de los workflows.", 80)}
{shot("24_ci_run", "Condición: ejecución de CI del PR 6.", 80)}
{shot("25_cd_run", "Condición: ejecución de CD: compuerta, paquete, documentación y publicación.", 80)}
{shot("26_docs_pages", "Condición: documentación publicada; actualizada al integrar el PR 7.", 80)}
{shot("27_docs_proxy", "Condición: documentación del módulo proxy generada desde los docstrings.", 80)}
<p>Documentación publicada: {DOCS_URL}</p>

<h1>9. Cambios y defectos encontrados</h1>
<p>Esta sección registra los problemas reales del desarrollo, porque muestran qué detectó cada
técnica de verificación.</p>
{table(["Defecto", "Quién lo detectó", "Corrección"], [
    ["<code>MessageReader</code> perdía un mensaje parcial si <code>recv</code> vencía su plazo, porque consumía la cabecera antes de tener el cuerpo.", "Prueba unitaria escrita antes de implementar el cliente", "Los bytes se consumen recién con el mensaje completo."],
    ["Un suscripto trabado demoraba la respuesta del set hasta 5 segundos por cliente. Con varios, el cliente podía recibir un timeout aunque el dato ya estuviera guardado.", "Revisión de resiliencia (severidad crítica)", "Cada <code>SocketObserver</code> tiene una cola acotada y un hilo de envío. Se agregaron 5 pruebas."],
    ["La primera corrida real falló en 8 de 32 casos con <code>ProvisionedThroughputExceededException</code>. El arnés de pruebas hacía un <code>Scan</code> de CorporateLog por prueba.", "Corrida contra AWS real (moto no limita la capacidad)", "Cada fila se lee por clave con <code>GetItem</code>. El sistema no tenía el defecto; lo tenía el arnés."],
    ["La documentación publicada no incluía los módulos: <code>__all__</code> limitaba a pdoc y el CI solo comprobaba que pdoc terminara bien.", "Revisión de las capturas de esta memoria (la página del módulo proxy daba 404)", "<code>__all__</code> incluye los subpaquetes, y <code>build_docs.py</code> falla si falta una página. Se agregaron 4 pruebas."],
    ["El esqueleto incluía <code>dependabot.yml</code>, que abrió 4 PRs sobre workflows ya descartados.", "Revisión del estado de GitHub", "Se cerraron con explicación; el archivo ya se había quitado en el PR 1."],
], [46, 24, 30])}
<div class="note">Impacto del tercer defecto: durante unos 5 minutos, el arnés consumió capacidad de
lectura de una tabla compartida con otros alumnos, lo que pudo demorar sus lecturas. La corrida
corregida tomó 68 segundos, contra 289 de la original.</div>
<h2>Revisión independiente</h2>
<p>El código se revisó con Gentle AI por tramos, porque el cambio completo superaba el tamaño admitido.
El tramo del servidor pasó por las lentes de riesgo, resiliencia y fiabilidad, con una corrección. El
tramo de protocolo y persistencia pasó por las lentes de riesgo y fiabilidad, sin correcciones. El arreglo de la documentación pasó por la lente de fiabilidad.</p>
<h2>Registro de versiones</h2>
{table(["Build", "Contenido"], [
    ["1", "Esqueleto, herramientas, CI/CD, protocolo y persistencia Singleton"],
    ["2", "Servidor, Proxy, Observer, clientes y aceptación"],
    ["3", "Documentación pdoc con todos los módulos"],
    ["4", "UML, evidencias, memoria, README completo y pruebas de la generación de documentación"],
], [12, 88])}
<p>La demostración de las secciones 6.3 a 6.6 se hizo sobre el build 2, por eso esa versión aparece en las capturas. Los builds 3 y 4 no cambian el comportamiento de los programas. Los controles de calidad, la cobertura, la aceptación contra AWS y TruffleHog se repitieron sobre el build 4.</p>

<h1>10. Limitaciones conocidas</h1>
<p>La revisión dejó observaciones que no bloquean la entrega. No se resolvieron porque el enunciado no
las pide, pero un sistema productivo tendría que atenderlas.</p>
{table(["Limitación", "Consecuencia", "Cómo se resolvería"], [
    ["El servidor no autentica a los clientes", "Quien alcance el puerto puede leer y modificar datos", "Autenticación por token, o limitar la red de acceso"],
    ["El UUID lo informa el cliente", "La pista de auditoría se puede falsificar", "Asociar la identidad a una credencial verificada"],
    ["La comunicación no está cifrada", "Los datos viajan legibles por la red", "Usar TLS"],
    ["Un hilo por conexión, sin tope", "Muchas conexiones pueden agotar recursos", "Usar un conjunto de hilos con límite"],
    ["El apagado no espera a los hilos en curso", "Una respuesta puede quedar cortada al cerrar", "Apagado ordenado con espera"],
    ["La cancelación manual se probó simulando la excepción", "Ctrl+C no se ejercitó en una prueba automatizada", "Prueba con señal real por proceso"],
], [36, 34, 30])}
<p>Además, las evidencias públicas incluyen el identificador de CPU, derivado de la dirección MAC, porque
el enunciado exige registrarlo.</p>

<h1 class="flow">11. Uso de inteligencia artificial</h1>
<p>El enunciado permite usar herramientas de IA si se documentan los prompts. Se usó Claude Code con el
modelo Claude Opus 5.5. La herramienta leyó el enunciado, propuso el diseño, escribió el código, las
pruebas, los diagramas, los workflows y esta memoria, y ejecutó las verificaciones. Gentle AI aportó la
revisión independiente. Los prompts están registrados textualmente en <code>CONTEXT.md</code>.</p>

<h1 class="flow">12. Conclusiones</h1>
<ul>
<li>Los tres patrones separan bien las responsabilidades: agregar auditoría o notificaciones no
requirió tocar el acceso a datos.</li>
<li>Cada técnica encontró defectos distintos. La prueba unitaria detectó el error de lectura, el
entorno real detectó el límite de capacidad y la revisión detectó el bloqueo por suscriptores trabados.
Ninguna de ellas por sí sola los habría encontrado todos.</li>
<li>Un entorno simulado es útil pero no alcanza: las pruebas pasaban 32 de 32 contra moto y 24 de 32
contra AWS en la primera corrida.</li>
<li>La automatización de los controles permitió repetirlos en cada cambio, con el mismo criterio en la
máquina local y en GitHub.</li>
</ul>

<h1 class="flow">13. Anexo: ejecución del sistema</h1>
{box('''python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
aws configure

python singletonproxyobserver.py -v
python observerclient.py -o=avisos.json
python singletonclient.py -i=examples/input_set.json
python singletonclient.py -i=examples/input_get.json -o=output.json
python singletonclient.py -i=examples/input_list.json

python scripts/quality.py
python -m pytest tests/acceptance -m acceptance''')}
<p>Repositorio: {REPO_URL}</p>
"""

page = (
    '<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Memoria Final TPFI</title>'
    f"<style>{CSS}</style></head><body>{body}</body></html>"
)
(Path(__file__).parent / "memoria.html").write_text(page, encoding="utf-8")
print(f"memoria.html generado con {figure_number} figuras")
