# Perfil y navegación

`/cuentas/perfil/` abre la ficha de la cuenta autenticada; los clientes se dirigen a `/mi-cuenta/perfil/`. Incluye iniciales, nombre, apellido, correo y teléfono. La edición está plegada inicialmente y se abre automáticamente si hay errores. Cambiar el correo requiere la contraseña actual. No se aceptan identificadores ajenos ni campos de permisos en estos formularios.

Las tatuadoras tienen acceso desde la ficha a la gestión de su portafolio. Su teléfono se guarda en `web_tatuadora.telefono` (migración 0015), sin publicarse en el sitio del estudio. Los clientes conservan su teléfono en su perfil existente y la lógica de solicitudes históricas permanece igual.

El menú de cuenta está en la parte inferior izquierda: perfil, contraseña, portafolio para tatuadoras, cambiar de cuenta y cerrar sesión. Las dos últimas acciones cierran la sesión mediante POST protegido y vuelven al ingreso. El botón de navegación permite ocultar y mostrar la barra; recuerda la preferencia en escritorio. En móvil inicia cerrada. Sin JavaScript, la barra queda visible y los menús desplegables funcionan con HTML.

El buzón vuelve a una lista compacta sin panel lateral. Cada fila abre el detalle completo y mantiene las acciones y permisos existentes.
