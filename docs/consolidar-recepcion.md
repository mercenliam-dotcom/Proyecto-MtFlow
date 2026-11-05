# Consolidar la recepción — revisión del equipo

Rama: `feature/consolidar-recepcion`. Base: `local/avance-total-2026-11-04`.
La entrega se publica para revisión en `feature/recepcion-bandejas-cotizaciones`.

## Comportamiento

El cliente elige obligatoriamente a su tatuadora. La propuesta se guarda como
`RECIBIDA` y no ocupa un bloque horario: la profesional posteriormente confirma
o rechaza la propuesta. Una cuenta o perfil desactivado no se ofrece en el formulario.
Si no hay profesionales habilitadas, se muestra el problema sin asignar otra
tatuadora ni crear una propuesta incompleta.

Se guarda exclusivamente la imagen JPG/PNG validada y recodificada, dentro de
`MEDIA_ROOT/postulaciones/`, con nombres aleatorios. `Imagen.url` contiene una
ruta interna relativa, no una URL pública. Se registran sus dimensiones reales,
bytes y nitidez. El endpoint firmado existente exige además que la imagen esté
registrada y pertenezca a una propuesta de la usuaria; administradores pueden
acceder a todas. Las imágenes antiguas con rutas ficticias no se recuperan ni
se reconstruyen mediante esta migración.

Contacto, propuesta, imagen y predicción se guardan en una transacción propia.
Ante fallos de escritura o de base de datos se revierte el conjunto y se intenta
eliminar el archivo, incluyendo escrituras parciales y fallos del commit.
Un apagado abrupto o un fallo adicional al borrar el archivo requiere revisar
el almacenamiento; la base de datos y el disco no comparten una transacción física.

Cada formulario lleva un token firmado válido por 24 horas y una referencia UUID
única en la base. Reenviar el mismo formulario no genera otra propuesta ni modifica
la anterior. Para una propuesta nueva se usa «Enviar otra propuesta». Una carrera
entre envíos se resuelve mediante la restricción única; en SQLite un bloqueo puede
devolver un error recuperable y permitir reintentar con el mismo token.

El correo de un formulario público no acredita identidad. Cada envío nuevo guarda
su propio registro de contacto; no sobrescribe ni agrupa personas por correo.
La consolidación de clientes verificados queda fuera de esta entrega.

El análisis sigue siendo opcional. Se conserva la propuesta si el servicio ML no
responde. `estado_ml` diferencia `NO_SOLICITADO`, `COMPLETADO` y `NO_DISPONIBLE`.
Se guardan versión, estilo, confianza máxima, todas las confianzas devueltas por
el cliente ML y alerta orientativa, sin normalizar sus porcentajes. La columna
`tiempo_inferencia_ms` mide la llamada completa Django→ML, incluyendo la red;
no representa exclusivamente el cálculo del modelo. Una alerta no acepta ni
rechaza automáticamente la propuesta.

Se mantiene la categoría por área incorporada en la rama SQL (hasta 25, 150 y
625 cm²). El tarifario sigue siendo provisional. Para revisión manual, el precio
sugerido queda vacío, en lugar de registrar un cero ficticio.

## Cambios de datos

La migración `web.0002_consolidar_recepcion` agrega referencias UUID a los registros
existentes y los marca con estado ML `LEGADO` («Sin trazabilidad previa»). No intenta
deducir si antes se solicitó un análisis. Amplía correo a 254 caracteres, teléfono
a 25 y versión del modelo a 120 para alinearlos con la entrada admitida.
No modifica migraciones anteriores ni incorpora dependencias.

El perfil automático de tatuadora usa ahora los nombres del modelo de usuario
de MTFlow, en lugar de los atributos del usuario predeterminado de Django.
Se conserva el mecanismo existente de creación de perfiles; el equipo debe
mantener habilitados solo los perfiles que reciben propuestas.

## Revisión manual

Con el entorno y las variables locales indicadas en README, desde `config/`:

```powershell
python manage.py migrate
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py runserver
```

1. Abrir `/cotizacion/` y comprobar que no se puede enviar sin elegir tatuadora.
2. Enviar una propuesta con JPG o PNG y verificar la referencia de recepción.
3. Consultar `Postulacion` e `Imagen` desde `/gestion-interna/`: la profesional,
   medidas y archivo deben corresponder al envío. No debe aparecer una reserva.
4. Reenviar el mismo POST y comprobar que no se duplica. Para un envío distinto,
   usar «Enviar otra propuesta».
5. Repetir con el análisis opcional, con ML caído y con revisión manual de precio.
6. Revisar los casos automatizados de fallos y permisos en `web/test_recepcion.py`.

La bandeja de propuestas, confirmación/rechazo, agenda real, notificaciones,
publicación de imágenes y entrenamiento con referencias quedan para otras ramas.
No se agrega ninguna pantalla pública para consultar propuestas guardadas.

## Validación

- 144 pruebas Django aprobadas en SQLite, incluyendo las seis pruebas previas
  de cotización que estaban desactualizadas.
- Migraciones y modelos coinciden (`makemigrations --check --dry-run`).
- Casos nuevos: elección obligatoria, archivo recodificado y metadatos, JPG/PNG,
  perfiles desactivados, reenvíos, tokens alterados, caída de ML, registro de
  confianzas, aislamiento de contactos, permisos por imagen, fallos de escritura,
  archivo parcial, rollback de base de datos y fallo de commit.
- La vista previa usa datos sintéticos y ML simulado. La validación en PostgreSQL
  y con Roboflow real queda pendiente; no se consumieron créditos en esta entrega.
