# Clientes, solicitudes e imágenes

La relación principal del DER es `cliente 1 → N postulacion 1 → N imagen`. Cada solicitud tiene un cliente obligatorio. Cada imagen referencia su solicitud, conserva sus metadatos y apunta a un archivo privado. Los archivos no se insertan como binarios dentro de SQLite ni se publican en el portafolio automáticamente.

`cliente.usuario_id` vincula opcionalmente una cuenta autenticada. Es único: varios envíos desde la misma cuenta reutilizan el cliente, incluso si van a distintas tatuadoras. La propiedad del portal se consulta mediante ese vínculo; se elimina `postulacion.cuenta_cliente_id` para no mantener dos caminos independientes de autorización.

Los visitantes sin cuenta reciben un registro de cliente sin usuario asociado. No se fusionan por correo, teléfono o nombre, porque esos datos declarados no prueban que sean la misma persona. No se añade una función de fusión manual en esta entrega.

`contacto_solicitud` sigue siendo una instantánea por envío, no otra identidad ni otro rol. Guarda nombres, apellidos y medio de contacto tal como se declararon. El perfil actual y el contacto histórico pueden diferir deliberadamente. Las imágenes siguen vinculadas a la solicitud concreta que las recibió.

La migración conserva todos los clientes históricos, solicitudes, contactos, imágenes, referencias y pagos. Para solicitudes identificadas por una cuenta anterior crea un cliente canónico por esa cuenta; para las anónimas conserva el cliente previo o lo crea desde su contacto. Si falta toda fuente de contacto, se detiene sin inventar datos. Es irreversible automáticamente; se guarda respaldo antes de aplicarla.

Comprobaciones: tres envíos de una cuenta comparten cliente; invitados con el mismo correo siguen separados; otras cuentas no acceden a solicitudes ni imágenes; el historial no cambia al editar el perfil; el ensayo de migración conserva las relaciones y rutas de imágenes.
