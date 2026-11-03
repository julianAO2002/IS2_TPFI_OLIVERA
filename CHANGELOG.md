# Registro de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones
siguen [Versionado Semántico](https://semver.org/lang/es/). El número de build aumenta con cada
PR integrado.

## [1.0.0] - 2026-11-02

### Agregado

- Build 4: diagramas UML, evidencias de ejecución, memoria final, README completo y pruebas de la
  generación de documentación.
- Build 3: `build_docs.py` falla si falta una página de la documentación.
- Build 2: servidor SingletonProxyObserverTPFI, patrones Proxy y Observer, programas
  SingletonClient y ObserverClient, y pruebas de aceptación contra moto y AWS real.
- Build 1: esqueleto generado con cookiecutter-pypackage, herramientas de calidad, workflows de CI
  y CD, protocolo de mensajes y acceso a CorporateData y CorporateLog con el patrón Singleton.

### Corregido

- Cada suscriptor desconectado dejaba un hilo vivo. Lo detectó la verificación independiente.
- `-s` no se validaba: un host inválido terminaba con un traceback, y uno vacío se conectaba a la propia
  máquina.
- `observerclient.py -v` no mostraba trazas durante la operación normal.
- Los archivos de entrada UTF-8 con BOM se rechazaban.
- `MessageReader` podía perder un mensaje parcial si `recv` vencía su plazo. Ahora los bytes se
  consumen recién con el mensaje completo. Lo detectó una prueba unitaria.
- Un suscripto trabado demoraba hasta 5 segundos por cliente la respuesta de un `set`, aunque el
  dato ya estuviera guardado. Cada suscriptor tiene ahora su cola y su hilo de envío. Lo detectó la
  revisión de resiliencia.
- La documentación publicada no incluía los módulos, porque `__all__` limitaba a pdoc. Se detectó al
  revisar las capturas de la memoria.
- Las pruebas de aceptación recorrían CorporateLog con `scan` y agotaron su capacidad de lectura en
  la primera corrida real. Ahora leen cada fila por clave.
