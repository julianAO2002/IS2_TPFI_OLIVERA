# Uso de herramientas de IA

El enunciado pide documentar aquí los prompts utilizados. Este archivo los registra sin correcciones.

## Herramientas

- Claude Code, con el modelo Claude Opus 5.5, como asistente de desarrollo.
- Gentle AI, para la revisión del código por lentes de riesgo, resiliencia y fiabilidad.
- Un agente de Claude Code separado, sin el contexto del desarrollo, para la verificación independiente.

## Prompts del alumno

1. "hace el is2_tpfi, hacelo en español y con comentarios de manera que entienda un estudainte. crea un repositorio nuevo. documenta todos los paso, saca captturas para la memoria final y arma la memoria final. documeta cuanto te dan los test los cambios que hiciste y demas. hace la entrea final y un resumen para mi y todo lo que pida"
2. "ahit e agrge el otro pdf y por ahi tengo las cotnraseñas"
3. "ahora si estan las cred4enciales"

## Decisiones del alumno durante el trabajo

La herramienta pidió autorización para revisar cada tramo de código. El alumno eligió "Review this change" en las cinco consultas:

1. Cambio completo (no se pudo revisar: superaba el tamaño admitido y se partió en tramos).
2. Servidor, clientes y pruebas.
3. Protocolo y persistencia Singleton.
4. Corrección de la documentación.
5. UML, evidencias, memoria y pruebas de la generación de documentación.

## Qué hizo la herramienta

- Leyó el enunciado, la nota de aplicación y los programas de diagnóstico de la cátedra.
- Consultó el esquema real de las tablas de AWS.
- Propuso el diseño y escribió el código, las pruebas, los diagramas, los workflows y la documentación.
- Ejecutó las verificaciones, las corridas contra AWS y las capturas.
- Redactó la memoria final a partir de las salidas guardadas.

## Qué verificar al usar estas herramientas

Los resultados de esta entrega se comprobaron con corridas reales, no con lo que afirmó la herramienta:
las salidas están en `docs/evidencias`. La sección 9 de la memoria registra los defectos encontrados,
incluidos los que introdujo la propia herramienta.
