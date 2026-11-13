# Hallazgos de la implementación

Las cifras de este proyecto pertenecen a una muestra pequeña de desarrollo, no a producción. La evidencia pública conserva fallas y cambios; no se seleccionaron solo llamadas exitosas.

## Suite nativa

La ejecución final pasó **10/10 escenarios**, con una repetición por caso. Tres comprobaciones deterministas adicionales validaron los filtros de búsqueda y la ausencia de un ID inventado, a partir del JSON emitido por el agente. El formato de rutas del evaluador nativo de parámetros no quedó confirmado: las llamadas tenían filtros correctos, pero las rutas intentadas se marcaban como ausentes. Por eso la selección de herramienta se evalúa nativamente y la comparación exacta se realiza en el harness, de manera explícita.

Durante el desarrollo también apareció una respuesta fuera de dominio: el agente dio un resumen histórico pese a la instrucción de limitarse al marketplace. Se agregó una regla de alcance con una respuesta de rechazo breve. La suite final pasó ese caso. Un pase aislado no demuestra una tasa de confiabilidad sostenida; las repeticiones quedan disponibles mediante `--repeat`.

## Tres conversaciones de audio reales, con comprador sintético

1. **Falla de grounding.** En la primera sesión, el agente convirtió un precio de 21.800 USD en 22.800 USD al enumerar tres autos. La evaluación nativa lo marcó como fallo. Se limitó la recomendación inicial a una opción y se reforzó la copia exacta del precio de la herramienta. Esta llamada sigue incluida en el denominador.
2. **Conflicto explicado.** Con el precio corregido, una segunda sesión pidió un horario ocupado por una prueba previa. La API devolvió 409 y el agente informó el conflicto en vez de confirmar una visita falsa. Los cuatro criterios de análisis pasaron; no se cuenta como una nueva visita creada.
3. **Recorrido completo.** La última sesión recomendó la Duster del catálogo, explicó la ausencia de garantía comercial y creó una visita simulada solo después de confirmar auto, fecha y hora. Pasaron los cuatro criterios. Es la sesión del video incluido.

En el agregado: **2 de 3 conversaciones** con evaluación exitosa; **12 turnos de audio**, p50 **2059,6 ms** y p95 **3352,1 ms** desde el silencio del usuario hasta el primer audio del agente. La muestra incluye herramientas y versiones de prompt anteriores: no se presenta como benchmark de la versión final ni como latencia exclusiva del modelo.

Los resultados se pueden recalcular desde `evals/evidence.json`, sin acceso a transcripts ni credenciales. La suite final está identificada en `evals/native-evidence.json`. El video identifica su conversación de origen en `docs/media/demo.json`.
