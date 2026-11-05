# Requisitos vigentes — MTFlow

Este registro recoge decisiones confirmadas en la revisión local del 4 de
noviembre de 2026. Complementa los documentos del proyecto y debe mantenerse
alineado con ellos cuando se preparen nuevas entregas.

## Confirmados

- El cliente debe seleccionar a la tatuadora con quien quiere tatuarse.
- Recibir una propuesta no confirma una reserva. La profesional revisa la idea
  y posteriormente confirma o rechaza según la propuesta.
- Las cuentas pueden combinar administración y función de tatuadora.
- Cada tatuadora consulta sus propias cotizaciones; únicamente las administradoras
  pueden consultar todas en la bandeja del equipo.
- La agenda debe tener una interfaz de calendario tipo FullCalendar para gestionar
  las horas por tatuadora. La pantalla actual de horarios de demostración no cubre
  este requisito y no debe presentarse como agenda operativa.
- La clasificación orienta la revisión y no reemplaza la decisión profesional.

## Agenda: siguiente incremento pendiente

Mantener la relación entre propuesta, tatuadora y bloque horario (`Postulacion`,
`Tatuadora`, `BloqueHorario`). El calendario debe conectarse con la disponibilidad
guardada y las decisiones de la profesional, evitando confirmar una reserva al
recibir el formulario. La bandeja y su detalle permiten consultar la propuesta
que se revisará antes de agendar.

Antes de implementar la agenda se deben confirmar las reglas de duración de
sesiones, disponibilidad recurrente, bloqueos, solapamientos, confirmación de cita,
reprogramaciones y cancelaciones. También se debe definir el alcance administrativo
del calendario. Estas reglas no se dan por resueltas por esta entrega.

FullCalendar se considera referencia de interfaz solicitada; la selección concreta
de biblioteca y vistas se revisará al implementar la agenda.
