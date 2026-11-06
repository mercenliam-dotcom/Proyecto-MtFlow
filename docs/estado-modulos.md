# Estado de módulos y cambios integrados

Fecha de revisión: 5 de noviembre de 2026. Destino de esta entrega: `main`.

Se integra la base de interfaz, cuentas, recepción SQL y bandejas de la rama
`feature/recepcion-bandejas-cotizaciones`, junto con la integración del modelo
local y el análisis inmediato implementados en esta sesión.

«Funcional» significa que el alcance descrito está implementado y verificado en
desarrollo. No significa que todo el proyecto esté terminado ni que se haya
validado un despliegue público.

## Cambios implementados en esta sesión

- Adaptador para el EfficientNetB0 v1 real de TensorFlow/Keras, con siete clases:
  Alto contraste, Anime, Cibersigilismo, Lettering, Linea Fina, Ornamentos y
  Tribal-Neotribal. Verifica los metadatos, el orden de clases y el SHA-256.
- Preprocesamiento equivalente al prototipo: RGB, orientación EXIF, 224 × 224,
  redimensionado bilineal y valores 0..255; sin volver a dividir por 255.
- FastAPI devuelve versión, siete confianzas, categoría, confianza máxima y
  umbral. La inferencia se ejecuta fuera del bucle asíncrono y reutiliza el modelo.
- Exigencia vigente del **60 %**: desde 0.60 se asigna el estilo ganador; por
  debajo se devuelve E-99, Fuera de catálogo. E-99 es abstención del sistema,
  no una octava clase aprendida ni una probabilidad inventada.
- Django vuelve a validar el vector y la decisión recibida en JSON.
- Análisis inmediato al seleccionar una imagen en `/cotizacion/`: progreso,
  resultado, detalle de siete puntuaciones, desactivación opcional y reintento.
  Cambiar o quitar la imagen cancela la respuesta anterior para evitar resultados
  desactualizados. La vista previa no guarda contactos, propuestas ni predicciones.
- Al enviar la propuesta, Django vuelve a clasificar la imagen limpia y guarda
  el resultado definitivo. No confía en resultados enviados por el navegador.
- Persistencia del umbral aplicado y mayor precisión decimal en las confianzas.
  Las predicciones históricas conservan su categoría y umbral registrado.
- Preparación automática de `admin` / `admin` en desarrollo. La cuenta se marca
  internamente para eliminarla al iniciar en producción, sin sustituir cuentas
  reales. Si sus relaciones impiden eliminarla, se deshabilita y se detiene el
  arranque de producción hasta resolverlas.
- Pruebas, ejemplos de entorno y documentación actualizados. El archivo de CI
  preparado utiliza Python 3.12; su activación en GitHub Actions sigue pendiente.

## Módulos funcionales con su alcance actual

| Módulo | Funcionalidad completada y verificada |
|---|---|
| Cuentas y acceso | Login/logout y cuentas del equipo Administrador/Usuario. Desde el 6 de noviembre se añade registro público exclusivo de Cliente, con portal propio y permisos separados; ver `portal-clientes-2026-11-06.md`. Una cuenta del equipo puede administrar y ser tatuadora. |
| Función de tatuadora | Selector público conectado a cuentas y perfiles habilitados; conserva la destinataria elegida y permite consultar su historial. |
| Clasificación ML local | Carga Keras, siete estilos, umbral del 60 %, abstención E-99, respuesta JSON y validación de Django. También existe una pantalla privada de prueba sin guardar solicitudes. |
| Análisis previo público | Clasifica al seleccionar la imagen, sin exigir contacto u otros campos y sin escribir registros. Tiene CSRF, validación de imagen y un límite independiente de consultas. |
| Recepción de propuestas | Contacto, referencia, medidas, tatuadora, precio provisional y análisis opcional; UUID único, control de reenvíos y guardado transaccional. Conserva la propuesta si ML falla. |
| Referencias privadas | Validación y recodificación JPEG/PNG, metadatos en BD y archivo privado; acceso con sesión, firma temporal y permiso de la profesional o administración. |
| Mis cotizaciones | Lista, filtro por estado, paginación y detalle de propuestas propias. Incluye imagen y análisis ya registrado. |
| Cotizaciones del equipo | Consulta global exclusiva de administradores, detalle y filtros combinados por tatuadora, estado y fechas; conserva consulta de profesionales desactivadas. |
| Administrador de desarrollo | Creación idempotente, contraseña almacenada mediante hash, preparación en WSGI/ASGI y eliminación de la cuenta marcada en modo producción. |

## Módulos parciales y pendientes

| Módulo | Disponible | Falta completar |
|---|---|---|
| Estimación comercial | Rango provisional calculado en el servidor según medidas y opciones. | Validación del tarifario del estudio, precio final y reglas comerciales definitivas. |
| Ciclo comercial de la propuesta | Recepción, estados almacenados y consulta del equipo. | Acciones de confirmar/rechazar, motivos, transiciones y conexión con citas. |
| Agenda y disponibilidad | Pantalla de horarios ficticios y modelo `BloqueHorario`. | Calendario operativo tipo FullCalendar, disponibilidad real, solapamientos, duración, reservas, cambios y cancelaciones. |
| Portafolio | Página pública con filtro de los siete estilos y espacios para fotografías. | Contenido real y flujo de carga, edición y publicación conectado a la BD. |
| Datos y archivos en producción | Modelos y migraciones, configuración PostgreSQL y almacenamiento privado local. | Validación en PostgreSQL del despliegue y adaptación del almacenamiento de imágenes al proveedor elegido. |
| Despliegue público | Configuración por entorno y preparación de la separación Django/FastAPI. | Aprovisionar ambos servicios, pesos, secretos, dominio/HTTPS, almacenamiento, respaldos y verificación en el alojamiento. |
| Integración continua | Flujo de pruebas preparado en `docs/ci/ci.yml`. | Activarlo en `.github/workflows/` y comprobar su ejecución remota. |
| Analítica y estadísticas | No hay un módulo operativo publicado. | Consultas, indicadores, visualizaciones y permisos. |
| Abonos y pagos | Existen algunos campos en el modelo de datos. | Flujo operativo de registro, validación y consulta; no hay pasarela implementada. |
| Revisión de etiquetas y reentrenamiento | Predicciones trazables y modelo `EtiquetaConsolidada`. | Flujo de revisión humana integrado en Django y procedimiento de actualización del modelo; subir una imagen no reentrena el modelo. |

## Validación realizada

- **203 pruebas Django aprobadas**, con SQLite temporal.
- **79 pruebas del servicio aprobadas** y una prueba contra Roboflow real omitida.
- `makemigrations --check --dry-run`: sin cambios pendientes.
- Navegador: una referencia obtuvo «Alto contraste» con 60,65 % antes de enviar.
- HTTP real: clasificación previa sin escrituras y posterior guardado de una
  propuesta E-01 y otra E-99, ambas con umbral 0.60 y siete confianzas.
- El modelo conserva su matriz original de 70 imágenes: 55 aciertos por argmax.
  Con umbral 0.60 asigna categoría a 43 y se abstiene en 27; 39 de las 43
  asignaciones fueron correctas en ese conjunto. No es una garantía para imágenes nuevas.
- El preprocesamiento coincide con el prototipo en esas imágenes y en las ocho
  orientaciones EXIF comprobadas.

Estas verificaciones corresponden al entorno local y la base de demostración.
No acreditan funcionamiento de PostgreSQL, almacenamiento cloud o HTTPS en un
alojamiento público. Los conectores Roboflow y PyTorch se conservan como
alternativas explícitas/históricas; el modo principal es Keras local.

## Preparación después de actualizar el repositorio

1. Configurar los `.env` de Django y FastAPI usando los ejemplos, con la misma
   clave compartida. Los secretos reales no forman parte del repositorio.
2. Instalar las dependencias web y las del servicio. Para Keras usar Python 3.12
   y `ml_service/requirements-modelo.txt`, además de `ml_service/requirements.txt`.
3. Aprovisionar los cuatro archivos del bundle en
   `ml_service/modelos/efficientnet_b0_v1/`, o configurar `MTFLOW_MODEL_DIR`.
   Los pesos no se incluyen en Git ni se descargan automáticamente.
4. Desde `config/`, ejecutar `python manage.py migrate`. Las migraciones nuevas
   son `cuentas.0003_admin_desarrollo` y `web.0004_umbral_y_precision_prediccion`.
5. Iniciar FastAPI y Django como se describe en el README. La cuenta
   predeterminada se prepara automáticamente solo en modo desarrollo.

La base SQLite que estaba versionada en una entrega anterior se retira del estado
actual de Git, conservando la copia local. Esto no reescribe el historial anterior.
No se publican la base de demostración, `.env`, referencias privadas, dataset,
entornos virtuales ni pesos del modelo.

Detalles: [modelo local y contrato JSON](modelo-local-fastapi.md),
[administrador de desarrollo](admin-desarrollo.md) y
[agenda pendiente](requisitos-vigentes.md).
