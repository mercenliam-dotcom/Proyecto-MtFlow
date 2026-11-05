# Avance integrado: recepción y bandejas de cotizaciones

Rama de revisión: `feature/recepcion-bandejas-cotizaciones`.

Integra las ramas previas de interfaz, cuentas, seguridad, Roboflow e implementación
SQL, y completa la recepción persistente de propuestas y su consulta por el equipo.
La propuesta permanece dirigida a la tatuadora elegida por el cliente; su recepción
no confirma una reserva ni un precio final.

## Funcionalidades de esta entrega

- **Recepción persistente:** elección obligatoria de tatuadora, contacto y medidas,
  referencia única de recepción y protección contra duplicados del mismo envío.
- **Referencias privadas:** validación y recodificación de JPG/PNG, archivo real,
  dimensiones, bytes y nitidez; descarga con sesión, firma y autorización por usuaria.
- **Consistencia:** guardado transaccional y limpieza de archivos ante fallos de disco
  o base de datos; mensajes de error sin confirmar propuestas incompletas.
- **Clasificación opcional:** conserva la solicitud si ML falla y registra estado,
  versión, estilo, confianzas y duración de la llamada; identifica la simulación.
- **Cuentas con funciones combinadas:** una administradora también puede ser
  tatuadora. La casilla «Es tatuadora» controla su inclusión en el selector público,
  que muestra los nombres actuales de las cuentas habilitadas.
- **Mis cotizaciones:** cada tatuadora consulta únicamente sus propuestas, con
  paginación, filtro por estado y detalle de contacto, medidas, referencia y análisis.
- **Cotizaciones del equipo:** acceso exclusivo de administradoras a todas las
  propuestas, filtros por tatuadora, estado y fechas inclusivas y detalle administrativo.
- **Historial:** conserva las propuestas de profesionales desactivadas y muestra
  avisos para referencias antiguas cuyos archivos no están disponibles.

## Accesos principales

| Ruta | Uso |
|---|---|
| `/cotizacion/` | Enviar una propuesta eligiendo tatuadora |
| `/cuentas/ingresar/` | Acceso del equipo |
| `/cuentas/` | Gestión de cuentas y función de tatuadora, solo administración |
| `/panel/cotizaciones/` | Bandeja personal |
| `/panel/cotizaciones/<referencia>/` | Detalle personal |
| `/panel/equipo/cotizaciones/` | Bandeja global, solo administración |
| `/panel/equipo/cotizaciones/<referencia>/` | Detalle administrativo |

## Preparación para revisión

Con el entorno y las variables de desarrollo del README configurados, desde
`config/` ejecutar:

```powershell
python manage.py migrate
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py runserver
```

Las migraciones agregan la función de tatuadora a las cuentas, referencias UUID
y estado de análisis a las propuestas, y alinean longitudes de datos. Se conserva
la habilitación de los perfiles existentes; revisar y desmarcar «Es tatuadora» en
las cuentas exclusivamente administrativas o de demostración. Las cuentas nuevas
requieren seleccionar esa función expresamente.

Se verificaron **183 pruebas Django en SQLite**, con datos temporales. Incluyen
recepción, archivos, rollback, reenvíos, funciones combinadas, filtros, permisos y
aislamiento entre profesionales. Se comprobaron lista, detalle e imagen en la vista
previa local, y las migraciones sobre una copia poblada. No se incorporan cuentas,
contraseñas ni configuración privada de esa vista previa a esta entrega.

## Pendientes explícitos

- Agenda operativa por tatuadora con calendario tipo **FullCalendar**.
- Flujo de confirmación/rechazo y conexión posterior con reservas y horarios reales.
- Validación de las reglas de duración, disponibilidad, solapamientos y cambios de cita.
- Tarifario definitivo y validación del despliegue con PostgreSQL y Roboflow real.

La pantalla de horarios sigue siendo de demostración. La clasificación orienta la
revisión profesional; no acepta ni rechaza automáticamente propuestas.

## Documentación de revisión

- [Recepción](consolidar-recepcion.md)
- [Cuentas y función de tatuadora](cuentas-tatuadoras.md)
- [Bandeja personal](mis-cotizaciones.md)
- [Bandeja del equipo](bandeja-equipo.md)
- [Requisitos vigentes y agenda pendiente](requisitos-vigentes.md)
