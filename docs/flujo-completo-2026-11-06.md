# Flujo local de solicitudes, agenda y cierre

Implementado sobre la integración `42bfe1f`, en la rama `feature/flujo-completo-2026-11-06`. El DER del informe queda pendiente de actualización por decisión del equipo. No se modifican los documentos originales del informe.

## Recorrido para demostrar

1. La administración habilita cuentas con función de tatuadora. No se crean cuentas reales ni se cambian contraseñas automáticamente.
2. El cliente completa `/cotizacion/`: nombres, primer y segundo apellido, correo, contacto preferido, presupuesto opcional, idea, medidas, tatuadora e imagen JPG/PNG de hasta 10 MiB. Puede proponer fecha y hora futuras; ambas deben ir juntas. Esto no bloquea horarios.
3. La solicitud aparece en `/panel/cotizaciones/`. Las bandejas son filtros de la misma tabla: pendientes, aceptadas, rechazadas y terminadas. La confianza se muestra solo al equipo. En el detalle se conservan los datos y la referencia privada.
4. La tatuadora confirma o corrige el estilo de la imagen principal. `EtiquetaConsolidada` registra su decisión y fecha; la predicción original no se modifica. Esta operación no inicia entrenamiento ni marca la imagen como apta para entrenar.
5. La profesional registra precio total, abono solicitado y medidas finales. La interfaz distingue «Cotizada» (acuerdo registrado) y «Confirmada» (abono verificado con dinero disponible). Son presentaciones del estado comercial existente, no nuevas copias de una solicitud.
6. Después de comprobar el pago externo, registra el abono recibido acumulado. No se supone ningún porcentaje obligatorio. La agenda exige abono y disponibilidad, respeta los bloqueos personales e impide solapamientos, también mediante restricciones de base de datos.
7. Se pueden reservar varias sesiones. Cada una puede realizarse, cancelarse o marcarse como inasistencia después de su término. Una sesión realizada no finaliza por sí sola todo el trabajo.
8. En caso de inasistencia se registra por separado el acuerdo: pendiente, conservar para reagendar, retener o devolver. Ninguno genera un ingreso adicional automáticamente. Una devolución acordada debe registrarse además como movimiento efectivamente realizado. Para reagendar tras inasistencia se exige registrar ese acuerdo.
9. Los pagos adicionales y devoluciones se registran con importe, comprobación, observación, fecha y responsable. El total neto es el abono verificado más pagos adicionales menos devoluciones. No se permite devolver más de lo recibido ni cobrar más del precio acordado.
10. «Terminar trabajo» exige al menos una sesión realizada y ninguna pendiente de realización. El cierre deja constancia del cobro y saldo reales: puede quedar un saldo pendiente, que se registra después cuando efectivamente se reciba.

## Métricas y portafolio

- `/panel/metricas/`: actividad semanal o mensual, estados actuales de solicitudes ingresadas en ese período, trabajos terminados por estilo revisado, zonas e inasistencias. Las clasificaciones no revisadas se identifican como tales.
- Los importes de dinero son acumulados históricos y están rotulados así: abonos, cobros netos, saldo e importes retenidos por acuerdo; no son ganancias porque no se registran costos. No se atribuye a cada semana un ingreso histórico cuya fecha original de recepción no fue registrada. El depósito preexistente sigue siendo un registro acumulado; los pagos adicionales y devoluciones sí tienen sus fechas individuales.
- El dashboard se actualiza cada minuto mientras está visible mediante JavaScript y `fetch`, sin React, Node.js ni dependencias nuevas. Si falla la conexión conserva la última vista confirmada.
- `/panel/portafolio/`: cada tatuadora agrega y edita fotos del tatuaje terminado o del estudio, elige publicación y carrusel. Puede relacionar un trabajo terminado propio. Se exige autorización de publicación; los borradores permanecen privados.
- La portada tiene carrusel navegable y galería de fotos publicadas. Mientras no haya fotos destacadas, muestra dos tarjetas de presentación, sin atribuir a las artistas tatuajes ficticios. No copia referencias de clientes al portafolio ni entrena con las fotografías.
- No existe enlace público al contacto privado de las profesionales, pasarela de pago, chatbot ni reentrenamiento automático.

## Persistencia y normalización

Migraciones `0010` y `0011`:

- `ContactoSolicitud`: columna `primer_apellido` (renombrada desde `apellidos`), `segundo_apellido`, canal y usuario social. Los apellidos históricos se conservan íntegros en la primera columna: no se intenta adivinar cómo separarlos. La propiedad Python `apellidos` es solo compatibilidad, no otro campo persistido.
- `Postulacion`: preferencia de fecha/hora, abono solicitado, medidas finales y acuerdo sobre el destino del abono. Medidas declaradas y finales representan hechos diferentes. Área y categoría siguen siendo calculadas; no se almacenan copias derivadas.
- `MovimientoCobro`: relación de muchos movimientos con una solicitud, tipo pago adicional/devolución, monto positivo, responsable y fecha. No duplica el abono existente; no se almacena un total calculado.
- `BloqueHorario`: admite `NO_ASISTIO` en citas; conserva la ocupación histórica del intervalo. `Sesion` continúa como única relación entre solicitud y bloque.
- `TrabajoPortafolio`: referencia UUID, relación opcional con solicitud propia terminada, tipo, publicación/autorización, selección para carrusel y fecha de modificación. Una foto final es un objeto distinto de la imagen de referencia.
- Los cambios no mezclan contacto declarado con identidad verificada de `Cliente`. Tampoco crean una tabla por bandeja: todas apuntan a `Postulacion`.
- Las migraciones retiran y reinstalan las restricciones de coherencia y solapamiento al reconstruir tablas SQLite. Cada fotografía anterior recibe un UUID diferente y queda como borrador hasta revisar su autorización. Se completa el catálogo de estilos sin sobrescribir nombres existentes.

## Validación y límites

- Suite Django: 258 pruebas, incluidos flujos nuevos, permisos, CSRF, versiones de edición, pagos repetidos, devoluciones, cierre multis sesión, privacidad/publicación, migración e integridad de agenda.
- El ensayo de migración usa una base temporal poblada y conserva contactos, importes, referencias, imágenes y relaciones de sesiones. Una base inconsistente se rechaza sin corregir sus datos silenciosamente.
- La vista previa visual usa una base y una cuenta de demostración separadas de los datos reales.
- SQLite y almacenamiento local continúan activos para la presentación. No se despliega AWS, no se aprovisionan RDS/S3 y no se cambian claves Roboflow.
- Las restricciones contemplan PostgreSQL, pero no se afirma haber validado en un servidor PostgreSQL real. TLS, cifrado del almacenamiento, disponibilidad y rendimiento del despliegue final requieren su verificación en AWS.
- El DER y las aclaraciones correspondientes del informe se actualizarán después. Este documento registra lo implementado y sus límites, no certifica todos los requisitos no funcionales de producción.
