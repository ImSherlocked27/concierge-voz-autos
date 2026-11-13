# Evidencia de conversaciones

Datos agregados de exportaciones reales de ElevenLabs. Sin transcript ni audio en este informe.

| Métrica | Resultado |
| --- | --- |
| Conversaciones únicas | 3 |
| Éxito de conversaciones evaluadas | 66.7% |
| Evaluadas / sin resultado | 3 / 0 |
| Latencia p50 | 2059.6 ms |
| Latencia p95 | 3352.1 ms |
| Turnos de audio con latencia válida | 12 |
| Llamadas a herramientas | 6 |

Latencia: convai_ttf_audio_since_silence.elapsed_time (segundos → ms), desde el silencio del usuario hasta el primer audio del agente. Solo turnos posteriores al usuario con source_medium=audio o metadata.text_only=false cuando falta source_medium. Se excluye el saludo. Percentiles con interpolación lineal; no se mezclan simulaciones de texto.

## Criterios

- grounding: 2 éxitos, 1 fallas, 0 sin resultado.
- tools: 3 éxitos, 0 fallas, 0 sin resultado.
- resolution: 3 éxitos, 0 fallas, 0 sin resultado.
- policies: 3 éxitos, 0 fallas, 0 sin resultado.

La tasa de la suite nativa se informa por separado en evals/native-report.md. Este informe no estima calidad usando tests locales.
