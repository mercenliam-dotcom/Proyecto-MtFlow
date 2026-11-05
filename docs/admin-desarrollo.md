# Cuenta predeterminada de desarrollo

> Desde la integración del 5/11, la creación/restauración automática requiere también `ADMIN_DESARROLLO_HABILITADO=1`. Está deshabilitada por defecto; se recomienda crear una cuenta propia con `createsuperuser`.

Por instrucción del usuario, con `DJANGO_DEBUG=1` se prepara automáticamente:

- Usuario: `admin`
- Contraseña: `admin`
- Rol: Administrador, sin cambio obligatorio de contraseña y sin función de tatuadora.

Funciona en desarrollo local y en un servidor web configurado en modo desarrollo.
La contraseña se guarda mediante el mismo hash Argon2 de las demás cuentas.
La preparación es idempotente: no duplica cuentas y restaura las credenciales de
la cuenta predeterminada en el siguiente arranque. Se ejecuta al terminar las
migraciones y al iniciar WSGI; en ASGI se ejecuta antes de atender la primera
petición, mediante un hilo para las operaciones de base de datos.

Antes del primer inicio, ejecutar `python manage.py migrate`. La migración
`cuentas.0003_admin_desarrollo` agrega una marca interna, no editable desde los
formularios, para distinguir esta cuenta de administradores reales.

Con **`DJANGO_DEBUG=0`**, las cuentas marcadas se eliminan automáticamente al
migrar y al arrancar la aplicación, incluso si se renombraron. No se crea una
cuenta de reemplazo con credenciales públicas. El administrador de producción
debe crearse de manera segura, por ejemplo con `python manage.py createsuperuser`.
Si existe una cuenta real llamada `admin` sin la marca, se conserva su contraseña
y no se reemplaza ni elimina.

Si la cuenta predeterminada tiene relaciones que impiden eliminarla, se desactiva,
se inutiliza su contraseña y se detiene el arranque de producción hasta reasignar
esas dependencias y eliminarla. Así no se borran propuestas o historial para
completar la transición. Las demás cuentas y sus datos se conservan.

Este tratamiento es una excepción para la cuenta predeterminada de desarrollo.
Las cuentas normales continúan con el flujo de desactivación del proyecto.
