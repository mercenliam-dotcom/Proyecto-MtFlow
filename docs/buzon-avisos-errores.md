# Buzón y avisos

El buzón de pendientes y el Registro presentan filas compactas con nombre, estado, medidas, confianza y precio. Seleccionar una fila carga el panel de lectura sin salir de la bandeja. El enlace al detalle completo y la evaluación guiada siguen disponibles. Sin JavaScript, cada fila abre el detalle completo. Los resúmenes personales mantienen el filtro por tatuadora; la vista de equipo conserva sus permisos administrativos existentes.

Los avisos temporales duran siete segundos, pueden cerrarse y pausan su desaparición al recibir foco o pasar el cursor. Complementan los errores junto a los campos y los mensajes de Django; no los eliminan. Incluyen validación nativa, errores devueltos por formularios y avisos de los componentes de análisis, imágenes y agenda.

Un fallo de lectura del buzón ofrece un error persistente, aviso temporal y reintento. Detectar pérdida de conexión en una página abierta muestra un aviso persistente; recuperar conexión no reenvía formularios ni confirma pagos. Si todo el servidor está apagado, la página de error inicial pertenece al navegador: el servidor no puede entregar un template en ese caso.

Las páginas propias 400, 403, 404 y 500 mantienen su código HTTP y no revelan excepciones. La página 500 no depende de consultar la base de datos. Los rechazos CSRF también tienen explicación amigable. Django conserva sus pantallas técnicas cuando DEBUG está activo; para ver el diseño localmente se puede abrir `/vista-previa/error/404/`, cambiando el código por 400, 403, 500 o 503. Esta vista solo funciona con DEBUG activo; 503 es una vista de demostración del servicio no disponible.

No hay cambios de esquema ni eliminación de solicitudes, pagos o archivos.
