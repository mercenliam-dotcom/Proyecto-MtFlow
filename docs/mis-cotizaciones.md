# Mis cotizaciones — revisión del equipo

La bandeja está disponible en `/panel/cotizaciones/`, desde el menú del equipo
y la tarjeta «Mis cotizaciones» en `/panel/`. El detalle usa la referencia UUID:
`/panel/cotizaciones/<referencia>/`.

## Alcance y permisos

- Cada cuenta ve solo las propuestas dirigidas a su perfil de tatuadora.
- En esta bandeja un administrador ve también únicamente sus propuestas.
  La administración global existente continúa en `/gestion-interna/`.
- El filtro por estado se construye exclusivamente con estados de propuestas
  propias. La lista muestra 20 propuestas por página, de más reciente a antigua.
- El detalle presenta contacto, descripción, medidas, precio sugerido registrado,
  referencias privadas y la última predicción registrada de cada imagen.
- Los precios mostrados son el valor registrado, no una nueva estimación ni un
  rango reconstruido. Las solicitudes sin precio indican revisión personalizada.
- El resultado simulado se identifica expresamente. No se ejecutan inferencias
  nuevas al consultar una propuesta. El estado de la propuesta no se modifica.
- El acceso directo al detalle ajeno devuelve 404. Las imágenes conservan firma,
  vencimiento y autorización por profesional, implementados en recepción.
- Las imágenes ausentes de registros antiguos muestran un aviso y no interrumpen
  el detalle. No se cargan imágenes de URLs externas registradas en la base.
- Las cuentas sin propuestas o sin perfil reciben un estado vacío comprensible.

Esta entrega permite consulta. La confirmación/rechazo y asignación de horarios
se implementarán como un paso posterior, con sus reglas y permisos específicos.

## Validación

162 pruebas Django aprobadas en SQLite: las 144 anteriores y 18 nuevas de bandeja,
detalle, permisos, enlaces directos, imagen privada, datos heredados, filtros,
paginación, escape de texto, simulación y ausencia de análisis. Se verificó además
la navegación en la vista previa local con una propuesta de prueba y su imagen.
No hay cambios de esquema ni dependencias adicionales para esta bandeja.

## Cómo revisar

1. Iniciar sesión en `/cuentas/ingresar/` y entrar a «Mis cotizaciones».
2. Enviar una propuesta pública eligiendo a esa tatuadora.
3. Comprobar que aparece en su lista y abrir «Ver propuesta».
4. Revisar contacto, medidas, referencia y resultado ML si se solicitó.
5. Acceder desde una segunda cuenta: la propuesta no debe aparecer y su enlace
   directo debe devolver 404; la imagen privada también debe quedar bloqueada.

Los cambios de recepción y bandeja se publican juntos para revisión en
`feature/recepcion-bandejas-cotizaciones`.
