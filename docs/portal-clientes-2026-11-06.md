# Portal de clientes

Ampliación autorizada después del flujo profesional. Sustituye la decisión anterior de que todos los clientes debían enviar sin cuenta. El registro de solicitudes sin cuenta sigue disponible. El informe y DER quedan pendientes de ajuste por el equipo.

## Accesos

- `/mi-cuenta/registro/`: registro público exclusivo de clientes.
- `/cuentas/ingresar/`: acceso común; cada rol se dirige a su espacio.
- `/mi-cuenta/`: solicitudes enviadas desde esa cuenta, paginadas.
- `/mi-cuenta/perfil/`: nombres, primer y segundo apellido, correo, teléfono y preferencia de contacto. Cambiar el correo exige la contraseña actual.
- `/mi-cuenta/solicitudes/<referencia>/`: propuesta, referencia privada, estado comercial, precio, abono solicitado/verificado, cobro neto, saldo y sesiones asociadas. No permite gestionar el trabajo ni registrar pagos.
- `/cuentas/mi-contrasena/`: cambio de contraseña propio, compartido con el mecanismo existente y conservando su política de validación.

## Separación de permisos

Se añade `CLIENTE`. `ADMIN` y `USUARIO` conservan su significado de cuentas del equipo; no se cambia el rol de ninguna cuenta existente. La función `es_tatuadora` sigue siendo una habilitación separada para cuentas del equipo. Las opciones de administración aclaran esta distinción.

El registro público no acepta rol, grupos, permisos, superusuario, tatuadora, administrador de desarrollo ni creador desde el navegador. Fuerza `CLIENTE` y contraseña personal. Una restricción de base de datos impide combinar `CLIENTE` con tatuadora o superusuario. Las cuentas del equipo creadas por administración siguen usando el cambio obligatorio de contraseña temporal.

Todas las rutas de gestión, agenda, métricas, portafolio profesional, diagnóstico ML y archivos internos rechazan al rol cliente desde el servidor. La navegación del cliente solo muestra sus solicitudes, nueva solicitud, perfil y contraseña. El cambio de visibilidad del menú no es el control de acceso.

## Propiedad y privacidad

`Postulacion.cuenta_cliente` es una relación opcional con la cuenta que envió la propuesta. La establece el servidor a partir de la sesión autenticada, nunca a partir de un identificador o correo del formulario. La consulta de cada detalle e imagen exige esa misma relación.

Las solicitudes anteriores y los nuevos envíos anónimos conservan propietario nulo. No se vinculan por coincidencia de correo, ni al registrarse ni al editar el perfil. El correo declarado no equivale a identidad verificada. La reasignación de envíos anteriores requeriría un procedimiento independiente de comprobación que no forma parte de este cambio.

El token de envío sigue impidiendo duplicados. Si ya fue utilizado desde otra cuenta o sin sesión, no permite recuperar ni apropiarse del registro anterior. El registro público tiene límite de cinco intentos por IP y hora, además de CSRF y la política de contraseñas existente. El límite usa el cache configurado; un despliegue con varios procesos debe usar un cache compartido para que el contador sea global.

Las plantillas de cliente son independientes de las vistas del equipo. No muestran porcentajes de confianza, versiones del modelo, anotaciones de agenda, historial interno ni motivos internos de rechazo. Las imágenes se sirven solo con autenticación y comprobación de propiedad, con respuestas sin almacenamiento en caché.

## Perfil y datos históricos

`PerfilCliente` mantiene únicamente preferencias adicionales y una relación uno a uno con `Usuario`: teléfono, segundo apellido, canal y usuario social. Nombres, primer apellido y correo actuales se guardan una sola vez en `Usuario`.

`ContactoSolicitud` continúa siendo la instantánea declarada al enviar una solicitud. Editar el perfil precarga los siguientes formularios, pero no reescribe los contactos de propuestas anteriores. `Cliente`, la identidad opcional del modelo previo, no se fusiona ni se crea automáticamente por registrar una cuenta.

Migraciones: `cuentas.0004` añade el rol y perfil con restricciones; `web.0012` añade la relación opcional de propiedad, conservando los registros existentes y reinstalando las guardas de agenda necesarias para SQLite.

## Verificación

17 pruebas específicas del portal: registro sin elevación de privilegios, política de contraseñas, límite de intentos, CSRF, restricciones de base de datos, rechazo de rutas del equipo, aislamiento entre clientes, archivos privados, ausencia de vinculación por correo, idempotencia y rechazo de tokens ajenos, datos internos ocultos, perfil y contraseña.

La suite completa de 275 pruebas pasó después de incorporar el portal (258 anteriores y 17 nuevas). Se ensaya la migración con datos históricos y después con una copia de la base del escritorio antes de aplicarla. Se mantienen SQLite, los archivos locales y Roboflow; no se provisiona infraestructura ni se envían correos o mensajes externos.
