# DER actualizado de MTFlow

Fecha: 6 de noviembre de 2026. Referencia: DER del informe existente (imagen14.jpg). Este documento describe la implementación actual, no funcionalidades futuras.

## Usar en dbdiagram.io

Crear un diagrama y pegar el contenido completo de `MTFlow_DER_actualizado.dbml`. Usa los nombres del DER original. `MTFlow_esquema_fisico.dbml` representa lo mismo con los nombres reales de las tablas de Django. No se deben pegar ambos juntos. La correspondencia exacta está en `correspondencia_modelos.json`.

Los archivos contienen 17 tablas de negocio. Se omiten tablas internas de Django (migraciones, sesiones de acceso, grupos, permisos y registros del administrador). Los tipos se expresan para PostgreSQL, pero este cambio mantiene SQLite local y no despliega una base nueva. DBML documenta el esquema; no reemplaza las migraciones Django ni debe ejecutarse como migración SQL. Sintaxis: https://dbml.dbdiagram.io/docs/

## Cambios respecto del DER original

| Área | Representación actual |
| --- | --- |
| Cuentas | Nueva tabla `usuario`: credenciales y permisos antes asociados a tatuadora. Solo ADMIN (Administradora) y USUARIO (Usuario/cliente). `tatuadora` es un perfil profesional 1:1; toda tatuadora debe ser ADMIN. |
| Cliente con cuenta | Nueva `perfil_cliente`, vinculada 1:1 a usuario. La solicitud tiene `cuenta_cliente_id` opcional para consultar exclusivamente las propias solicitudes. No se vinculan solicitudes ajenas por coincidencia de correo. |
| Contacto | Nueva `contacto_solicitud`: datos declarados al enviar, con nombres y ambos apellidos separados. Editar el perfil no cambia el contacto histórico. `cliente` se conserva como entidad heredada opcional; no es otro rol. Sus campos históricos no se inventan ni se eliminan. |
| Agenda | Nueva `sesion`: cada cita pertenece a una solicitud, que puede tener varias sesiones. Sustituye el bloque único de la solicitud. Fecha y hora propuestas son referenciales; no reservan. |
| Cotización y pagos | Precio acordado, abono solicitado, abono recibido y verificación. Nueva `movimiento_cobro` para pagos adicionales y devoluciones, sin duplicar el abono. Pagos fuera de la plataforma. |
| Inasistencia | Estado NO_ASISTIO en la cita y destino del abono en la solicitud. No implica ingreso adicional ficticio: se registra lo efectivamente cobrado. |
| Historial | Nueva `evento_solicitud` para actor, fecha y detalle de operaciones. Aceptadas y rechazadas son filtros de solicitudes, no copias en otras tablas. |
| Imágenes y ML | Se mantienen imagen, predicción, confianza por estilo y etiqueta consolidada. Se incorpora trazabilidad del resultado, umbral y versión. La revisión no sobrescribe la predicción ni entrena automáticamente el modelo. |
| Portafolio | Se amplía trabajo_portafolio para publicación, carrusel, autorización y vínculo opcional con la solicitud. La fotografía del trabajo final es distinta de la imagen privada de referencia. |
| Datos derivados | Área, categoría de tamaño, saldo y total cobrado se calculan; no se dibujan como columnas almacenadas. |
| Claves | tatuadora_estilo tiene una PK id y unicidad de la pareja tatuadora/estilo, en lugar de la PK compuesta del dibujo anterior. |

El diagrama original contemplaba dirección y fecha de nacimiento en cliente; no se incluyen como si estuvieran implementadas. El nombre profesional se obtiene de la cuenta, con nombre artístico independiente. La tabla heredada cliente conserva su estructura previa, incluidos apellidos históricos sin división automática.

## Roles y acceso

- Administradora: cuentas y funciones del equipo. Buzón personal y operaciones sobre solicitudes asignadas; conserva la consulta global del equipo que ya existía.
- Usuario (cliente): perfil y solicitudes propias. El registro público siempre asigna este rol; no permite elegir Administradora.
- La migración conserva IDs, contraseñas y vínculos: CLIENTE pasa a USUARIO; las antiguas cuentas USUARIO marcadas como tatuadoras o superusuarias pasan a ADMIN. ADMIN permanece igual.

La migración de roles es irreversible desde Django porque una reversión automática podría devolver permisos profesionales a clientes. Se conserva respaldo completo antes de aplicarla.

## Reglas que no representa completamente un dibujo

Los archivos incluyen claves, nulabilidad, unicidad y restricciones explícitas CHECK. Las notas explican el índice parcial de imagen principal, las restricciones contra solapamientos, la coherencia tatuadora/sesión y las validaciones de aplicación. Las acciones de eliminación indicadas son las de Django; DBML no instala sus triggers. Fechas y valores iniciales administrados por Django se documentan como notas, no como falsos defaults de SQL.

El contacto histórico y el perfil actual representan hechos distintos; no se sincronizan ni se fusionan automáticamente. Este DER permite revisar la normalización con la implementación real, pero no sustituye la justificación formal de las dependencias funcionales del informe.

La derivación de solicitudes entre tatuadoras sigue siendo una propuesta: no se agrega una tabla inexistente. Tampoco se incorpora entrenamiento automático, pasarela de pago ni contacto privado público.

## Regeneración

Desde la carpeta del proyecto, con su entorno Python y configuración local: `python scripts/generar_der_dbml.py`. El generador lee metadatos de modelos, no registros personales ni contraseñas.
