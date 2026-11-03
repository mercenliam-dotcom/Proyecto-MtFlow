# ADR-0009 — Clasificación con el modelo entrenado en Roboflow

**Estado:** aceptada para el prototipo · **Fecha:** 2026-11-02

## Contexto

El equipo entrenó un clasificador en Roboflow: proyecto **"Tattoo styles"** (workspace de Martín Santiago), licencia CC BY 4.0.

| Dato | Valor |
|---|---|
| Tarea | Clasificación de imagen (una etiqueta) |
| Arquitectura | **ResNet18** (`tattoo-styles-2-resnet18-t1`) |
| Clases | 7: Alto contraste, Anime, Cibersigilismo, Lettering, Línea fina, Ornamentos, Tribal-Neotribal |
| Imágenes (dataset v3, 22-oct-2026) | 887: 648 entrenamiento (73 %), 160 validación (18 %), 79 prueba (9 %) |
| Preprocesamiento | Auto-orient, estirar a 224×224 · sin aumento de datos |

## Decisión

1. El servicio de inferencia (`ml_service`, ADR-0002) consulta ese modelo por la **API serverless de Roboflow**. Django no cambia: sigue llamando a `ml_service` igual que antes.
2. Las 7 clases se traducen a los códigos internos E-01…E-07 en `ml_service/app/config.py`. Una clase que el catálogo no conozca hace que la respuesta se rechace.
3. La **API key de Roboflow vive solo en `ml_service/.env`**: nunca en el navegador ni en Git.
4. Antes de enviarla, la imagen ya fue validada y re-codificada por Django (sin EXIF/GPS) y se reduce a un máximo de 640 px.
5. Si Roboflow no responde, el servicio devuelve 503 y la web muestra "servicio no disponible". La imagen no se pierde.
6. El predictor se elige con `ML_PREDICTOR` (`roboflow`, `local`, `simulado` o `auto`). El camino de pesos locales (EfficientNet-B0) se conserva.

## Consecuencias que hay que resolver o declarar

- **Diferencia con lo declarado en los informes:** ahí se dice EfficientNet-B0 con aprendizaje por transferencia. El prototipo usa **ResNet18** (también es aprendizaje por transferencia desde ImageNet). Hay que corregir el texto o justificar el cambio.
- **7 estilos y no 6.** Hay que actualizar el catálogo del informe (Anexo A) y los diagramas.
- **Sin clase "fuera de catálogo" (E-99).** Una foto que no sea un tatuaje (un meme, una mascota) igual recibirá uno de los 7 estilos, a veces con confianza alta. Mitigación: agregar en Roboflow una clase de descarte ("Otros") y mapearla a E-99 en `CLASES_ROBOFLOW`.
- **Transferencia internacional de datos.** Las imágenes de los clientes se envían a un proveedor externo (Roboflow, EE. UU.). Bajo la Ley 21.719 (vigencia plena 1-dic-2026) esto debe informarse en el consentimiento del formulario y declararse en el informe.
- **Dependencia del plan de Roboflow:** límites de uso y costos del plan contratado. Verificarlos antes de la demostración.
- **Métricas del modelo:** no son públicas en la página del proyecto. Exportar desde Roboflow la exactitud y la matriz de confusión del conjunto de prueba para el informe.
- Aumentar el dataset o aplicar aumento de datos: 79 imágenes de prueba para 7 clases son ~11 por clase, una muestra pequeña para afirmar métricas.
