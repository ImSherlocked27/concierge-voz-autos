# Por qué construí Concierge

Quise probar cómo cambia la búsqueda de un auto cuando puedo explicar lo que necesito con mis propias palabras. Un presupuesto, una caja automática y espacio para una familia parecen requisitos simples, pero una respuesta convincente no alcanza: el auto recomendado tiene que cumplirlos.

Ese fue el problema que elegí para esta demo. Mi objetivo fue conectar una conversación de voz con datos que pudiera revisar y con acciones que pudiera comprobar.

## Cómo lo resolví

Armé un catálogo ficticio de diez autos y una API pequeña con FastAPI. Le di al agente tres herramientas: buscar opciones, consultar un auto y agendar una visita simulada. Dejé los filtros en el backend para que la búsqueda tenga reglas claras: si no hay coincidencias, el agente tiene que decirlo y preguntar qué requisito podría cambiar.

Para las preguntas sobre reserva, garantía, transferencia y visitas, escribí cuatro documentos cortos. Los adjunté al contexto del agente. Esto me permitió probar respuestas sobre políticas, aunque no demuestra cómo funcionaría una búsqueda documental a gran escala.

La agenda usa SQLite. Pedí confirmación explícita antes de registrar una visita y agregué controles para que dos solicitudes concurrentes no ocupen el mismo turno. También hice que repetir una solicitud no cree una segunda reserva. Son visitas de prueba: no envío correos ni tomo datos personales.

Elegí ElevenLabs para la conversación y usé Sarah, una voz multilingüe disponible en la cuenta. Escribí el saludo y las instrucciones con voseo. Prefiero distinguir esas dos decisiones: el texto usa voseo, pero no evalué ni prometo un acento argentino.

## Qué comprobé

Guardé la evidencia para que quien revise el proyecto no dependa solamente del video:

- En la ejecución nativa registrada pasaron diez escenarios, con una repetición por escenario. El [reporte](../evals/native-report.md) conserva ese resultado; no lo interpreto como una tasa de éxito sostenida en producción.
- Verifiqué por separado tres combinaciones de parámetros. Durante el desarrollo, el evaluador nativo no encontraba las rutas de esos parámetros, así que hice la comprobación directamente sobre los argumentos de las herramientas.
- Grabé conversaciones reales del agente con un comprador de voz sintética. El [video](media/demo.mp4) está editado para acortar pausas; su [procedencia](media/demo.json) explica cómo lo generé.
- Agregué pruebas locales para autenticación, filtros, agenda, concurrencia y cuotas. También cubrí el arranque de la página con fallas de red, la recuperación del catálogo y la ausencia de soporte de micrófono.

Puedo repetir las comprobaciones locales sin gastar créditos:

```sh
python -m pytest -q
node --test tests/web.test.cjs
python -m scripts.configure
```

Las pruebas de página ejecutan el JavaScript con un DOM mínimo y respuestas controladas. Comprueban el comportamiento, pero no reemplazan una prueba de audio y permisos en un navegador real. Las evaluaciones remotas y las grabaciones publicadas corresponden a la ejecución anterior; no las presento como una nueva evaluación de estos cambios.

## Qué mejoré en esta revisión

Encontré que la página esperaba el catálogo y la configuración de voz como una sola operación. Si fallaba la voz, también desaparecía el catálogo. Separé ambas cargas: ahora puedo seguir buscando autos aunque ElevenLabs no esté disponible, y puedo reintentar la carga del catálogo sin recargar toda la página.

Agregué un tiempo máximo de espera para las solicitudes y mensajes concretos para problemas de acceso o micrófono. También dejé deshabilitado el inicio cuando el navegador no permite pedir audio. Al terminar una sesión, la interfaz se restablece aunque falle el cierre del SDK.

## Qué me falta resolver

La demo no tiene un despliegue permanente. Para compartir una conversación en vivo necesito un backend HTTPS con almacenamiento persistente y actualizar la dirección de las herramientas. El video y el catálogo local permiten revisar el proyecto mientras tanto.

Antes de usar algo así con clientes, trabajaría en la integración con inventario real, la operación de la agenda y la gestión de datos personales. También repetiría las evaluaciones con más conversaciones, ruido e interrupciones. Hoy puedo mostrar un recorrido acotado que funciona y explicar sus límites; todavía no medí su impacto comercial.

Para reproducirlo, dejé la instalación en el [README](../README.md), el [recorrido de demo](demo.md) y las [decisiones técnicas](design.md).
