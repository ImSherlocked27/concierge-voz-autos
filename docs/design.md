# Decisiones y límites

## Alcance

Este proyecto demuestra una integración de ElevenLabs Agents con un sistema externo pequeño. Es un escenario de contratación, no un marketplace operativo. Todos los autos, precios, kilometrajes y políticas fueron creados para esta demo, sin copiar inventario, prompts o datos internos de un empleador.

## Grounding y herramientas

El prompt no contiene un listado de autos. Las recomendaciones requieren respuestas de la API y los IDs deben provenir de la misma conversación. Las políticas se adjuntan a la knowledge base como documentos de texto en modo prompt porque son breves; esto usa la KB nativa sin afirmar una evaluación de recuperación RAG a gran escala.

El agente debe reconocer cero resultados, atributos ausentes y errores. La API no puede demostrar por sí sola que el usuario confirmó verbalmente una visita: esa regla se evalúa en el agente y la API exige `confirmed=true`. El backend no ofrece una garantía criptográfica de consentimiento conversacional.

## Estado y concurrencia

SQLite persiste visitas y cupos. `BEGIN IMMEDIATE` y restricciones únicas protegen conflictos y reintentos concurrentes. Los turnos se normalizan a UTC-3 y deben estar dentro de los próximos 30 días, de lunes a viernes y cada media hora de 09 a 18. No se guardan nombres, teléfonos ni correos.

La app usa una instancia con disco persistente. Un despliegue distribuido requeriría una base compartida, gestión de capacidad, retención y rate limiting adicional. No se presenta este diseño como infraestructura de producción.

## Credenciales y consumo

La clave solo se carga del entorno del servidor. Las herramientas autentican con un secret de ElevenLabs y comparación de tiempo constante en FastAPI. El agente requiere autenticación; el navegador recibe una URL firmada después de validar el código de demo y reservar cuota. El acceso al catálogo no gasta créditos.

Una URL firmada es una credencial temporal: quien la posea puede usarla mientras sea válida. El límite diario nativo, concurrencia y duración máxima protegen el gasto además del contador local. El código de acceso debe rotarse si se comparte públicamente. Un despliegue abierto sostenido requiere controles de abuso adicionales.

El onboarding oficial se verificó con una solicitud TTS HTTP 200. Eso verifica la conexión y generación de audio, pero no demuestra por sí solo el recorrido ASR → LLM → tools → TTS. La evidencia del agente se informa por separado.

## Voz

Idioma de agente: `es`. Prompt y saludo con voseo rioplatense. Preferencia de biblioteca: Carolina, Rioplatense, Argentina. Si no está agregada a la cuenta, se utiliza Sarah como respaldo multilingüe. No se atribuye acento argentino a Sarah. La clave generada por el onboarding no autorizó agregar voces (`voices_write`), por lo que se mantiene una vía manual documentada.

## Evals

Las definiciones fuente se transforman a los tres formatos nativos del SDK y se suben a ElevenLabs. El test de recorrido usa el backend ficticio; la agenda creada sigue siendo simulada. El harness conserva denominadores de evaluaciones conocidas/desconocidas y excluye métricas ausentes o inválidas. Los tests locales usan fixtures sintéticos exclusivamente para verificar el cálculo, nunca como evidencia de conversaciones reales.

La suite nativa y las conversaciones de audio tienen reportes distintos. Las simulaciones permiten evaluar texto y herramientas, pero no prueban micrófono, acento, interrupciones o latencia de voz. p50/p95 con pocas muestras solo describen esa muestra.

## Operación

Un Quick Tunnel permite probar webhooks desde ElevenLabs sin configurar hosting permanente. Su URL cambia y deja de funcionar al cerrar el proceso; no debe incluirse en la postulación como una demo siempre disponible. El repositorio y Dockerfile permiten reproducir el servicio en un host propio.

Los IDs remotos se guardan inmediatamente en `.local/state.json` para reintentar un alta interrumpida. No elimines ese archivo para actualizar recursos existentes. Los documentos de KB se suben una sola vez: una edición de políticas requiere retirar explícitamente su ID local y reconfigurar para subir la nueva versión. La rotación del secret requiere actualizar tanto ElevenLabs como el backend; no basta editar `.env`.
