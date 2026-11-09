# Ajustes del formulario, agenda y portafolio

- Botones de los módulos con tamaño y separación uniformes; controles de navegación más compactos.
- Se retira el presupuesto del formulario público. Los valores históricos de la base de datos se conservan.
- Instagram/TikTok son opcionales tanto en solicitud como en perfil. Si se elige una red pero no se proporciona usuario, se usa el correo obligatorio como medio de contacto.
- La selección de imagen inicia el análisis automáticamente; desaparece el interruptor. El servidor siempre intenta clasificar al recibir una nueva solicitud, independientemente de campos enviados por el navegador. Conserva la solicitud con estado ML no disponible si el servicio falla. No se inventa una predicción.
- Crear o editar un horario muestra el calendario propio junto al formulario. Seleccionar una fecha actualiza el campo y seleccionar una hora futura completa el inicio. Los eventos existentes se consultan sin abandonar el formulario. Las validaciones de disponibilidad y solapamiento siguen en el servidor.
- El campo de fecha de la reserva muestra DD/MM/AAAA; el calendario utiliza español de Chile y horas de 24 horas. Se aceptan fechas ISO en el servidor para compatibilidad, pero la interfaz usa día/mes/año.
- Las fotografías autorizadas y publicadas se integran en la galería filtrable por estilo. La opción de carrusel es independiente. Los ejemplos de estilo sin fotografías permanecen como espacios pendientes.

Verificación: 307 pruebas Django; navegador de escritorio y móvil con datos ficticios para fecha, agenda, subida de fotografía, filtro por estilo y análisis automático. Sin migraciones ni cambios al entrenamiento del modelo.
