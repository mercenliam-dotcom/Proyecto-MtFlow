# Pago externo, reserva y disponibilidad pública

## Recorrido de la tatuadora

1. En el detalle de su solicitud, **Aceptar solicitud** abre un formulario con el precio acordado, abono solicitado y medidas opcionales. No exige haber cobrado.
2. **Confirmar abono recibido** abre otro formulario: importe recibido y casilla que confirma la comprobación externa. La plataforma no procesa transferencias ni espera una confirmación bancaria.
3. **Agendar una sesión** crea la primera cita o una sesión adicional: solicitud, fecha, inicio y término. Se exige pago positivo que cubra el abono solicitado y horario libre dentro de la jornada.

Los pagos verificados registrados por la opción de cobros también habilitan la reserva si cubren el importe requerido. No se debe volver a contabilizar ese mismo dinero como abono. Las devoluciones reducen el importe disponible; se conservan los acuerdos por inasistencia. Cada modificación mantiene las comprobaciones de propiedad y concurrencia.

## Jornada y excepciones

El horario inicial acordado es lunes a sábado, de 10:00 a 19:00 (Santiago), y domingo cerrado. **Mi agenda → Editar horario de trabajo semanal** permite cambiarlo por tatuadora. Se guarda en `HorarioTrabajo`, un registro por tatuadora y día de semana.

Un bloque de tipo **Horario excepcional de una fecha** sustituye la jornada habitual de ese día. Permite, por ejemplo, abrir un domingo de 10:00 a 14:00. Varias excepciones no superpuestas permiten una jornada partida. Los bloqueos personales descuentan disponibilidad; para cerrar una fecha completa se bloquea su jornada. No se puede reducir un horario dejando fuera una sesión reservada.

## Formulario público

El cliente, con o sin cuenta, elige tatuadora y consulta su calendario. Verde indica intervalos disponibles; gris, citas o bloqueos. No se exponen identificadores de citas, nombres, teléfonos, notas, pagos ni motivos. Se muestran solo horas de trabajo. La lista ofrece posibles inicios cada 30 minutos: no implica que el tatuaje dure 30 minutos.

La propuesta es opcional y no reserva. La tatuadora acuerda la duración y el horario final. El servidor vuelve a comprobar que la fecha sea futura, que el inicio pertenezca a la jornada y que no esté ocupado, incluso con JavaScript deshabilitado. El calendario se actualiza al cambiar tatuadora o fecha y cada minuto. Un horario puede cambiar mientras el cliente completa la solicitud; se valida otra vez al enviar.

Las reservas privadas validan el intervalo completo, abono, propiedad, fechas, solapamientos y zona horaria. Las fechas pasadas y las horas transcurridas se restringen también en la interfaz. Los registros anteriores se conservan.

## Verificación

Pruebas de flujo HTTP de aceptación, pago y primera reserva; pago previo sin duplicación; rechazo de pagos sin confirmación; privacidad por tatuadora; domingos y excepciones; horas pasadas y ocupadas; modificación del horario semanal sin invalidar citas. Prueba de navegador con datos aislados: una reserva desaparece de las opciones públicas. DER actualizado con 18 tablas de negocio.
