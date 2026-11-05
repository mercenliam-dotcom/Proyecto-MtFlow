# Modelo local → FastAPI → Django → base de datos

El modelo de esta rama es EfficientNetB0 v2 de TensorFlow/Keras, con siete clases.
FastAPI ejecuta la inferencia en CPU y devuelve JSON. Solo Django escribe las
propuestas, referencias privadas, predicciones y confianzas en la base de datos.
No se llama a Roboflow en `ML_PREDICTOR=local`.

## Clases y decisión confirmada

| Código | Nombre exportado |
|---|---|
| E-01 | Alto contraste |
| E-02 | Anime |
| E-03 | Cibersigilismo |
| E-04 | Lettering |
| E-05 | Linea Fina |
| E-06 | Ornamentos |
| E-07 | Tribal-Neotribal |

Si la mayor puntuación es **mayor o igual a 0.60**, se sugiere esa categoría.
Si es menor, se devuelve **E-99: Fuera de catálogo** como abstención del sistema.
Se conservan las siete probabilidades originales: no se agrega una probabilidad
de E-99, no se reescala el vector y no se redondea antes de decidir.
Django vuelve a comprobar la regla y rechaza metadatos JSON contradictorios.
El umbral fijo de 0.60 no puede rebajarse mediante variables de entorno.

Este 60 % es una exigencia sobre la puntuación del clasificador, no un intervalo
estadístico ni una garantía del 60 % de aciertos. El modelo no fue entrenado para
detectar imágenes desconocidas. E-99 no acredita que la imagen no sea un tatuaje.
La decisión profesional sigue siendo necesaria; recibir una propuesta no la
rechaza, confirma ni reserva una cita automáticamente.

Un fallo de red, un modelo corrupto o probabilidades inválidas se distinguen de
la abstención: la propuesta se conserva con análisis `NO_DISPONIBLE`, sin inventar
una predicción E-99. Una inferencia válida bajo el umbral se guarda `COMPLETADO`
con categoría E-99 y sus siete confianzas.

## Archivos y entorno

Usar **Python 3.12**. En el entorno separado del servicio:

```powershell
cd ml_service
python -m pip install -r requirements.txt -r requirements-modelo.txt
```

La rama incluye estos cuatro archivos en `ml_service/modelos/efficientnet_b0_v2/`:

- `MTFlow_EfficientNetB0_v2.keras`
- `training_config.json`
- `class_names.json`
- `model_sha256.txt`

Los cuatro archivos bastan para ejecutar la inferencia. El modelo tiene SHA-256
`d0b1eddeb3c5742dba88acd85a1706080ff59c6058908fed37adb0d4860f0938`.

Crear `ml_service/.env` a partir de su ejemplo:

```dotenv
ML_SERVICE_API_KEY=una-clave-compartida-larga
ML_PREDICTOR=local
MTFLOW_MODEL_DIR=modelos/efficientnet_b0_v2
```

Las rutas relativas de `MTFLOW_MODEL_DIR` se resuelven desde `ml_service/`,
independientemente del directorio desde el cual se inicie el proceso.
En `config/.env` configurar la misma clave compartida, `ML_SERVICE_URL` con
`http://127.0.0.1:8001` y las variables Django explicadas en el README.
No se necesita una clave Roboflow. Los `.env` no se incluyen en Git.

Desde `config/`, aplicar `python manage.py migrate`: la migración
`web.0004_umbral_y_precision_prediccion` agrega el umbral aplicado y amplía la
precisión de las probabilidades. Los registros históricos conservan su categoría
y tienen umbral nulo, porque no se conoce el que se aplicó originalmente.
No se recalculan ni reclasifican automáticamente.

Arrancar en dos terminales, cada una con su entorno:

```powershell
# Desde ml_service/
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# Desde config/
python manage.py runserver 127.0.0.1:8000
```

## Preprocesamiento y trazabilidad

Se verifica el SHA-256 antes de cargar Keras con `safe_mode=True`, sin compilar.
Se comprueba el orden de clases contra `training_config.json` y se traduce cada
nombre a su código. El modelo debe recibir RGB 224 × 224 y producir siete salidas.

La v2 aplica la orientación EXIF, convierte a RGB y redimensiona a 224 × 224 con
Pillow mediante interpolación bilineal. Conserva el rango 0..255 porque el
reescalado forma parte del modelo.

Django valida y recodifica la imagen antes de enviarla, eliminando metadatos.
La referencia almacenada es la misma versión limpia enviada a FastAPI; compararla
con el prototipo requiere usar esos mismos bytes, pues recomprimir JPEG puede
cambiar casos ambiguos. FastAPI valida otra vez el archivo y ejecuta la inferencia
fuera del bucle asíncrono. Se carga una sola instancia y se serializan sus llamadas.

## Contrato JSON

`POST /clasificar`, multipart con campo `imagen`, cabecera `X-API-Key`.
Ejemplo ilustrativo de abstención; los números no corresponden a una foto real:

```json
{
  "version_modelo": "efficientnet_b0:v2:<SHA-256 completo>",
  "confianzas": {
    "E-01": 0.57, "E-02": 0.13, "E-03": 0.06, "E-04": 0.06,
    "E-05": 0.06, "E-06": 0.06, "E-07": 0.06
  },
  "estilo_sugerido": "E-99",
  "confianza_maxima": 0.57,
  "umbral_confianza": 0.6
}
```

`confianza_maxima` siempre se refiere al mayor valor de los siete estilos,
incluso cuando `estilo_sugerido` es E-99. No es la probabilidad de E-99.
`GET /salud` informa el estado, la versión del modelo y el umbral.
Una clave ausente/incorrecta devuelve 401; un fallo de inferencia devuelve 503.

Al enviar `/cotizacion/` con análisis autorizado, Django guarda `Postulacion`,
`Imagen`, `Prediccion` y siete filas `ConfianzaEstilo`. `Prediccion` registra el
estilo sugerido o E-99, la confianza máxima, el umbral, la versión con SHA-256 y
la duración de la llamada Django→FastAPI, no solo el tiempo puro del modelo.
La pantalla privada `/clasificacion/probar/` continúa siendo una prueba sin
guardar propuestas. Las bandejas consultan resultados ya guardados.

## Pruebas

```powershell
# Desde config/, con variables de desarrollo configuradas:
python manage.py test
python manage.py makemigrations --check --dry-run

# Desde ml_service/:
python -m pytest -q
```

Las pruebas incluyen los límites 0.59999998 y 0.60, ausencia de probabilidad E-99,
metadatos contradictorios, SHA-256 incorrecto, orden de clases, guardado de la
abstención y recepción sin reservas automáticas. La comprobación con pesos reales
y el recorrido HTTP completo se realizan además en la vista previa local.

## Análisis previo en el formulario de cotización

El formulario activa inicialmente «Analizar el estilo al seleccionar la imagen».
Al seleccionar un JPG/PNG válido muestra el progreso, la categoría y confianza,
o Fuera de catálogo si la mayor puntuación es menor al 60 %. El usuario puede
desactivar el análisis, quitar la imagen o reintentar si el servicio falla.
Cambiar la imagen o desactivar el análisis cancela la respuesta pendiente y
evita que una clasificación antigua se muestre sobre una referencia nueva.

La ruta pública `POST /cotizacion/analizar/` recibe únicamente la imagen y la
activación del análisis, valida CSRF, recodifica la imagen y consulta a FastAPI.
No necesita contacto, medidas o tatuadora, no guarda archivos ni escribe
propuestas/predicciones en la base. Tiene un límite propio de 20 análisis por
600 segundos por IP, independiente del límite de envío de propuestas.

La recepción definitiva vuelve a clasificar la referencia en el servidor y guarda
su resultado con umbral 0.60. No confía en la clasificación mostrada o enviada
por el navegador. Sin JavaScript el análisis sigue disponible al enviar.
Las propuestas históricas conservan el umbral con que fueron registradas.

## Verificación actual con umbral del 60 %

- 203 pruebas Django y 79 pruebas FastAPI aprobadas; sin migraciones pendientes.
- Navegador: selección de imagen con el formulario incompleto, progreso y resultado
  «Alto contraste» con 60,65 % antes de enviar. Sin errores de consola observados.
- HTTP real: el análisis previo no cambió los conteos de clientes, propuestas,
  imágenes, predicciones o confianzas. Al enviar la propuesta se guardaron el
  estilo E-01, máxima 0.6064817905426025, umbral 0.60 y siete confianzas.
  Otra referencia quedó E-99 con máxima 0.31980830430984497 y el mismo umbral.
- Las 70 imágenes originales conservan la matriz de confusión del modelo:
  55 aciertos por argmax. Con la nueva exigencia, 43 obtuvieron categoría,
  27 quedaron en abstención y 39 de las 43 asignaciones fueron correctas.
  Estas cifras corresponden al conjunto de prueba, no garantizan resultados nuevos.
## Verificación histórica con el umbral anterior de 90 %

- **194 pruebas Django aprobadas** y **79 pruebas del servicio aprobadas**; la
  prueba de Roboflow real se omitió porque esta integración usa inferencia local.
- `makemigrations --check --dry-run`: sin cambios pendientes.
- El preprocesamiento coincide exactamente con el prototipo en las 70 imágenes
  de prueba y en las ocho orientaciones EXIF comprobadas. La inferencia reproduce
  su matriz de confusión original: 55 aciertos entre 70 antes de aplicar abstención.
- Con exigencia de 0.90, 18 imágenes obtuvieron categoría y 52 quedaron en
  abstención. Las 18 asignaciones fueron correctas en ese conjunto de prueba.
  Es una medición sobre esas imágenes, no una garantía para referencias nuevas.
- Recorrido HTTP real: login de desarrollo, dos propuestas con imágenes del
  conjunto de prueba, FastAPI Keras, JSON y guardado en SQLite de demostración.
  Una propuesta quedó E-01 con confianza 0.9997434020042419 y otra E-99 con
  máxima 0.31980830430984497. Ambas guardaron siete confianzas, umbral 0.90 y
  estado de análisis COMPLETADO. Se compararon los valores guardados contra
  una nueva llamada real con la imagen limpia almacenada.
- Se comprobó rechazo 401 sin clave compartida. No se utilizaron servicios
  externos ni créditos Roboflow. La base original del repositorio no se modificó;
  deben aplicarse ambas migraciones nuevas al preparar esa base o PostgreSQL.
