# Bandeja del equipo y detalle administrativo

Requisito confirmado: solo las administradoras pueden ver todas las cotizaciones.
Las tatuadoras conservan el acceso a sus propias propuestas en «Mis cotizaciones».

## Acceso

- Bandeja del equipo: `/panel/equipo/cotizaciones/`.
- Detalle administrativo: `/panel/equipo/cotizaciones/<referencia UUID>/`.
- Accesos desde el menú y la tarjeta del panel, visibles solo para administradoras.
- Ambas rutas validan el permiso en el servidor; un enlace conocido no otorga acceso.

## Funciones

La bandeja muestra cliente, tatuadora destinataria, fecha, estado, medidas y precio
sugerido registrado. Permite combinar filtros por tatuadora, estado y rango de
fechas inclusivo según la zona local configurada. La lista se pagina de 20 en 20,
de más reciente a antigua, conservando filtros al cambiar de página. Una fecha
o selección inválida muestra errores y no se ignora silenciosamente.

El detalle comparte la presentación de la bandeja personal: contacto, descripción,
medidas, imagen privada, última predicción y sus confianzas, avisos de simulación,
análisis no solicitado/no disponible y archivos heredados ausentes. No ejecuta
inferencias nuevas. La vuelta al listado y la navegación corresponden al área
administrativa cuando se abre desde la bandeja del equipo.

Las profesionales desactivadas con historial siguen disponibles como filtro de
consulta. Esto no las habilita para recibir nuevas propuestas ni iniciar sesión.
La consulta no cambia el estado, confirma reservas ni permite reasignar propuestas.

## Verificación

183 pruebas Django aprobadas en SQLite, incluyendo 12 nuevas de bandeja global,
autorización, detalle, filtros combinados, fechas inclusivas, errores, paginación,
consulta histórica y separación respecto de la bandeja personal. Se verificaron
lista y detalle de una propuesta de prueba en el navegador local.
La bandeja no requiere migraciones adicionales ni nuevas dependencias.

La configuración de funciones combinadas de cuentas se documenta en
`cuentas-tatuadoras.md`. Los requisitos confirmados y el calendario tipo FullCalendar
pendiente se mantienen en `requisitos-vigentes.md`.

Todos los cambios de esta revisión se publican en
`feature/recepcion-bandejas-cotizaciones`, para revisión del equipo.
