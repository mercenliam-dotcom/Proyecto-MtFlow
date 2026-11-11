# Validación del peso y picos de memoria al analizar imágenes

El límite de subida sigue siendo 10 MiB (10 × 1024 × 1024 bytes) por archivo.
La comprobación ya existía en Django y FastAPI. Ahora Identificar estilo,
Cotización y Portafolio también muestran el peso al seleccionar el archivo y
detienen el envío si supera el límite. El navegador recibe el límite configurado
en Django; el servidor vuelve a comprobarlo aunque no se ejecute JavaScript.

## Procesamiento

- FastAPI admite una imagen por vez, incluyendo lectura, decodificación e
  inferencia. Una solicitud simultánea recibe 503 y `Retry-After: 3` antes de
  leer y decodificar otra imagen. No hay una cola de fotos decodificadas.
- La decodificación y la inferencia se ejecutan fuera del bucle de FastAPI para
  que `/salud` pueda responder mientras se procesa una foto.
- Para v2/v3 se reutiliza la imagen ya decodificada. Se aplica la misma orientación
  EXIF y reducción bilineal RGB a 224×224, evitando copias RGB innecesarias a
  resolución completa. La imagen se cierra también cuando falla una operación.
- Django comprueba dimensiones antes de decodificar, evita una copia completa
  cuando no hay que rotar o convertir el modo y libera los píxeles al terminar.
- No cambian los pesos, las clases, los umbrales ni la calibración OOD.

Una foto de 3024×4032 puede pesar menos de 10 MiB y necesitar bastante más RAM
al decodificarse. El límite de peso comprimido y el límite de píxeles protegen
recursos diferentes. Se conserva el máximo de 40 millones de píxeles y 8000 px
por lado del servidor; esto no garantiza que cualquier imagen admitida quepa
en un servicio de 512 MB.

## Verificación local

- 106 pruebas del servicio ML aprobadas, incluidas la admisión concurrente, la
  disponibilidad de `/salud`, el cierre de imágenes y una foto de 3024×4032.
- La entrada 224×224 coincide píxel a píxel con la versión anterior en RGB,
  RGBA, escala de grises, CMYK y paleta, con las ocho orientaciones EXIF.
- Tres inferencias reales consecutivas sobre la misma foto sintética de
  3024×4032 produjeron las mismas siete puntuaciones, decisión y distancia OOD
  antes y después del cambio.
- En procesos separados sobre Windows, con el mismo entorno y una sola imagen
  en procesamiento, el pico RSS medido durante esas solicitudes pasó de
  506,39 a 416,39 MiB. El incremento sobre el modelo cargado pasó de 193,80 a
  103,98 MiB. Es una medición local de esa foto, no un límite máximo ni una
  medición de Render/Linux.
- Suite Django: 330 pruebas; las 8 incidencias restantes corresponden a pruebas
  de agenda y plantillas que ya fallaban en la rama base. No aparecieron
  incidencias nuevas en esta ejecución.

## Despliegue

Actualizar Django y FastAPI a este commit y conservar un único worker de
Uvicorn. No se agregan migraciones ni se requiere cambiar variables del modelo
v3. Comprobar en Render el consumo en reposo y durante subidas grandes y
solicitudes simultáneas. Si vuelve a ocurrir OOM, hace falta limitar dimensiones
admitidas o reducir el consumo del runtime; este parche no promete estabilidad
con 512 MB para todos los archivos.

## Ensayos de fiabilidad visual

`scripts/evaluar_fiabilidad_v3.py` permite reevaluar el test ID y una colección
OOD existente con pesos y umbrales fijos. Requiere las imágenes originales en
las rutas de sus manifiestos. Las variantes de una misma imagen no son muestras
independientes ni una nueva validación externa. Los casos de estilos mixtos
requieren etiquetas aceptables revisadas por una tatuadora.
