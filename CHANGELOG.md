# Registro de cambios

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y las versiones
siguen [Versionado Semántico](https://semver.org/lang/es/). El número de build aumenta con cada
PR integrado.

## [1.0.0] - 2026-11-02

### Agregado

- Build 4: diagramas UML, evidencias de ejecución, memoria final y README completo.
- Build 3: la documentación publicada incluye todos los módulos, y el build falla si falta alguno.
- Build 2: servidor SingletonProxyObserverTPFI, patrones Proxy y Observer, programas
  SingletonClient y ObserverClient, y pruebas de aceptación contra moto y AWS real.
- Build 1: esqueleto generado con cookiecutter-pypackage, herramientas de calidad, workflows de CI
  y CD, protocolo de mensajes y acceso a CorporateData y CorporateLog con el patrón Singleton.

### Corregido

- `MessageReader` podía perder un mensaje parcial si `recv` vencía su plazo. Ahora los bytes se
  consumen recién con el mensaje completo. Lo detectó una prueba unitaria.
- Un suscripto trabado demoraba hasta 5 segundos por cliente la respuesta de un `set`, aunque el
  dato ya estuviera guardado. Cada suscriptor tiene ahora su cola y su hilo de envío. Lo detectó la
  revisión de resiliencia.
- Las pruebas de aceptación recorrían CorporateLog con `scan` y agotaron su capacidad de lectura en
  la primera corrida real. Ahora leen cada fila por clave.
