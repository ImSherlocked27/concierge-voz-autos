# Recorrido de demostración · 60–90 segundos

El repositorio incluye un video con una sesión real de audio de ElevenLabs y un comprador de voz sintética. Este guion también permite grabar un recorrido manual desde la página. Nunca montes respuestas simuladas como si fueran una llamada real.

1. 0–10 s: mostrar la página y el aviso de inventario ficticio. Iniciar la voz y aceptar el micrófono.
2. 10–30 s: decir «Busco una SUV familiar por hasta veintidós mil dólares, con ISOFIX». Verificar que las opciones provengan de los resultados de `search_vehicles`: Duster, Kicks o CR-V.
3. 30–45 s: elegir una opción y preguntar «¿Qué garantía tiene?». Debe explicar que es una demo y no ofrece una garantía comercial.
4. 45–65 s: pedir una visita para una fecha futura concreta y un horario válido de Argentina. Confirmar explícitamente después de que el agente repita auto, fecha y hora. Mostrar el código devuelto por `schedule_visit`; aclarar que es simulado.
5. 65–90 s: mostrar los reportes nativos y de conversaciones. Si no hay latencia de voz medida, mostrar «pendiente»; no reemplazarla por latencia de una simulación de texto.

Grabación: usar tu propia voz o una voz sintética autorizada. No mostrar `.env`, URLs firmadas ni la clave; ocultar correos, cuentas y códigos de acceso. Publicar el video solo después de revisar el contenido. No enviar automáticamente ninguna postulación.

El video incluido se genera con `scripts.voice_smoke` y `scripts.render_demo`. El primero sintetiza las intervenciones del comprador y las envía como PCM por el Python SDK; conserva el audio real del agente y las transcripciones de la sesión. El segundo agrega subtítulos y recorta silencios sostenidos a 400 ms. Si todavía supera 90 segundos, ajusta la reproducción a 88 segundos e indica el factor en cada cuadro y en el manifiesto. No cambia el contenido hablado ni genera respuestas adicionales. Su manifiesto identifica la conversación de origen. Se pueden elegir otros horarios con `--hour` y `--minute` para evitar conflictos entre ejecuciones.
