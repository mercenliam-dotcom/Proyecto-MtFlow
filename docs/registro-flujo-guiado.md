# Solicitudes pendientes y Registro

`/panel/cotizaciones/` muestra únicamente RECIBIDA y EN_REVISION. `/panel/registro/` conserva ACEPTADA, RESERVADA, REALIZADA y RECHAZADA de la tatuadora autenticada. Son consultas a la misma tabla: no se trasladan ni duplican filas. Las bandejas globales del equipo mantienen su alcance anterior.

Registro incluye filtros de aceptadas (incluye reservadas y finalizadas), por agendar, agendadas, finalizadas y rechazadas. El detalle completo permanece accesible y vuelve al apartado correspondiente. Los enlaces anteriores de bandejas aceptadas/rechazadas redirigen al Registro.

«Evaluar solicitud» abre el detalle con un diálogo para escoger aceptar o rechazar. La elección no modifica datos: dirige al formulario completo de acuerdo o motivo. Cerrar o presionar Escape permite continuar revisando el detalle. Sin JavaScript se conservan los enlaces y formularios normales.

En el recorrido guiado, guardar el acuerdo abre la confirmación manual del pago externo; confirmar un importe suficiente abre la creación de la sesión con la solicitud ya seleccionada. La tatuadora puede elegir continuar más tarde desde Registro. No se verifica ni se registra dinero automáticamente. El rechazo confirmado vuelve a los registros rechazados. Los errores de formulario mantienen el recorrido y requieren corrección antes de avanzar.

No hay cambios de modelos, migraciones ni permisos. Se conservan la propiedad de las solicitudes, CSRF, validaciones de importes, controles de versión, disponibilidad y restricciones de agenda.
