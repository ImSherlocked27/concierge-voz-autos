# Suite nativa de ElevenLabs

Invocación: `suite_2001m7b79xqme4ca2dn06xhfj0wc`
Repeticiones solicitadas: 1
Ejecuciones: 10 · pasadas: 10 · falladas: 0 · otras: 0

Tasa de pase sobre todas las ejecuciones: 100.0%
- 01 · aclaración: passed
- 02 · fuera de dominio: passed
- 03 · inyección: passed
- 04 · garantía: passed
- 05 · financiación: passed
- 06 · pagos: passed
- 07 · filtros SUV: passed
- 08 · filtros económico: passed
- 09 · ID inventado: passed
- 10 · recorrido completo: passed

## Verificación determinista de filtros

La suite nativa evalúa la herramienta elegida. El harness valida por separado los parámetros JSON emitidos contra los filtros solicitados; no usa rutas de parámetros sin documentar del evaluador nativo.

- 07 · filtros SUV: PASS · filtros exactos verificados sobre tool calls reales
- 08 · filtros económico: PASS · filtros exactos verificados sobre tool calls reales
- 09 · ID inventado: PASS · herramienta ausente
