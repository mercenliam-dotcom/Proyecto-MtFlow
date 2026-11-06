# Aclaraciones de alcance para la presentación local

> Registro histórico. La implementación del 6 de noviembre y las decisiones posteriores están en [flujo-completo-2026-11-06.md](flujo-completo-2026-11-06.md). Ese documento actualiza los pendientes de esta lista, incluida la preferencia de fecha y hora del cliente.

Decisiones indicadas por el usuario después de la revisión de normalización:

- No implementar reentrenamiento automático en producción. La confirmación/corrección del estilo prevista por RF-02.3 es revisión profesional, no una pantalla de entrenamiento. Su interfaz sigue pendiente.
- Conservar Roboflow como proveedor activo. El equipo entrena y ajusta el modelo propio por separado; no cambiar aún el entorno ni activar los pesos locales.
- La agenda es una herramienta privada de organización. La tatuadora acuerda los horarios con el cliente y reserva después de verificar el abono. Puede definir duración variable, varias sesiones y descansos. No incorporar selección ni reserva pública de horas. La disponibilidad pública, si se muestra, es orientativa (días y horario general de atención). Esto requiere actualizar RF-03.2 del informe.
- Contacto y pagos externos: la profesional inicia el contacto usando los datos de la solicitud. No publicar un botón directo de contacto con la tatuadora como requisito de este flujo. Un enlace privado al chat del cliente con texto preparado es distinto de un chatbot; no se implementa en este cambio y debe aclararse el alcance de RF-05.1.
- Cotizada/confirmada describen fases anteriores a la reserva. No agregar pasos después de reservar para repetir un acuerdo ya registrado. Mantener explícita la diferencia entre precio acordado, abono recibido y total efectivamente cobrado al finalizar. Falta alinear la interfaz y los estados con RF-04.
- Estadísticas pendientes: solicitudes aceptadas, estilos trabajados/rechazados, importes por estilo y zonas, con filtros semanales/mensuales y aislamiento por profesional. Usar etiquetas de estilo revisadas; no tratar un rechazo comercial como corrección automática de la clasificación. Evitar sumar varias veces una solicitud por tener varias sesiones.
- Portafolio: menor prioridad. El equipo cargará inicialmente fotos propias y del estudio. Carrusel evaluado como mejora pendiente, sin imágenes ficticias obligatorias. La carga manual de archivos para la demostración no equivale a la gestión por profesional prevista en RF-07.
- Límite de imagen confirmado: 10 MB (10 × 1024 × 1024 bytes), formatos JPG/JPEG y PNG. Se conservan validación de contenido, límites de píxeles y recodificación. Actualizar la mención de WEBP en el informe. Ajustados Django, JavaScript, ayudas de formulario y FastAPI; no cambia el proveedor ML.

Los puntos marcados como pendientes no quedan implementados por este documento. Este registro complementa el informe original, no lo reemplaza ni modifica automáticamente su archivo.
