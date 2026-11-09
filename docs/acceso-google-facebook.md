# Acceso con Google y Facebook

## Estado

La integración está implementada, pero cada proveedor permanece deshabilitado hasta configurar sus credenciales. Los botones aparecen en Ingresar y Crear cuenta únicamente para proveedores configurados. No se crearon aplicaciones externas ni se obtuvieron credenciales automáticamente.

Un nuevo cliente autoriza el proveedor y luego confirma sus datos, elige un usuario y una contraseña de respaldo de MTFlow. Los siguientes accesos pueden hacerse con el proveedor o con usuario/contraseña. La contraseña de respaldo pertenece a MTFlow; nunca debe ser la contraseña de Google/Facebook. Los registros siempre crean USUARIO sin permisos de tatuadora ni administración.

Una cuenta existente puede vincular o desvincular un proveedor desde **Mi perfil → Gestionar accesos con Google y Facebook**, confirmando su contraseña local. Coincidir en correo no vincula ni da acceso automáticamente. Se mantienen las solicitudes y los permisos de la cuenta original. Cancelar la autorización no crea cuentas.

## Preparación local

Desde la raíz del proyecto, en Git Bash:

```bash
source .venv/Scripts/activate
python -m pip install -r requirements.txt
cd config
python manage.py migrate
```

Agregar a `config/.env`, sin subirlo a Git:

```dotenv
SOCIAL_AUTH_BASE_URL=http://127.0.0.1:8000
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
FACEBOOK_CLIENT_ID=
FACEBOOK_CLIENT_SECRET=
FACEBOOK_API_VERSION=
```

Reiniciar Django después de configurar. La URL base es el origen de la aplicación, sin ruta final. Usar el mismo host al visitar la página: no mezclar localhost con 127.0.0.1 porque cambia la sesión que verifica la autorización.

## Google

1. Crear o seleccionar el proyecto del estudio en Google Cloud y configurar Google Auth Platform: marca, audiencia y permisos mínimos de identidad (`openid`, `email`, `profile`). Añadir usuarios de prueba si la aplicación está en modo de pruebas.
2. Crear un cliente OAuth para aplicación web.
3. Registrar exactamente esta URI de redirección local: `http://127.0.0.1:8000/cuentas/social/google/callback/`.
4. Copiar el ID y secreto a las variables de Google en `.env`.

No se pide acceso al contenido del correo ni a contactos. Se exige que Google confirme el correo como verificado.

## Facebook

1. Crear/configurar una aplicación del estudio en Meta for Developers con Facebook Login para web y los permisos `public_profile` y `email`.
2. Configurar el sitio y la URI OAuth válida: `{SOCIAL_AUTH_BASE_URL}/cuentas/social/facebook/callback/`. Si la configuración de Meta exige HTTPS para pruebas, usar un origen HTTPS de desarrollo y actualizar también SOCIAL_AUTH_BASE_URL; no desactivar las validaciones del proveedor.
3. Copiar el App ID y App Secret a las variables de Facebook. En FACEBOOK_API_VERSION indicar la versión habilitada en el panel, con formato `vNN.N`; no escribir literalmente ese marcador.
4. Configurar usuarios de prueba/roles para desarrollo. Antes del acceso público, completar los requisitos que muestre Meta para la aplicación, incluyendo política de privacidad y eliminación de datos.

Facebook puede no entregar un correo. En ese caso se solicita al completar la cuenta, igual que en el registro local; nunca se utiliza ese correo para vincular otra cuenta existente.

## Despliegue

Cambiar SOCIAL_AUTH_BASE_URL al dominio HTTPS final y registrar las dos URI finales en sus respectivos proveedores. La aplicación no habilita proveedores con un origen HTTP en producción. Guardar secretos fuera de Git, por ejemplo mediante la configuración segura del servicio AWS.

Las credenciales de producción no deben copiarse en capturas, pruebas ni chats. Si se revoca o cambia una aplicación externa, actualizar las variables y volver a probar con cuentas de prueba.

## Persistencia y seguridad

La migración cuentas.0006 agrega `IdentidadSocial`, vinculada a usuario. Son únicos `(proveedor, identificador)` y `(usuario, proveedor)`. Se almacena solo proveedor, identificador, cuenta local y fecha de vinculación. No se guardan tokens de acceso/refresh ni contraseñas del proveedor. Las cuentas y solicitudes previas no se reescriben.

Authlib verifica el protocolo; Google utiliza OIDC con state, nonce, PKCE y validación de firma/issuer/audiencia/caducidad. Facebook usa código de autorización y consulta autenticada del ID con appsecret_proof. Las operaciones iniciales y la desvinculación requieren POST con CSRF; los intentos caducan a los diez minutos y están limitados. La vinculación también queda ligada a la cuenta y contraseña de la sesión que la inició.

Pruebas automatizadas usan proveedores simulados y claves de firma de prueba. No sustituyen una prueba real de autorización con las credenciales de las aplicaciones. Sin esas credenciales no se puede confirmar el acceso real de Google/Meta.

Referencias: [Google OIDC](https://developers.google.com/identity/openid-connect/openid-connect), [Authlib Django](https://docs.authlib.org/en/latest/oauth2/client/web/django.html), [Facebook Login](https://developers.facebook.com/docs/facebook-login/).
