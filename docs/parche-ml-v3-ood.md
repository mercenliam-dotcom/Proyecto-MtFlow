# Parche ML v3 con OOD

Base: `feature/optimizacion-agenda`, commit `d34d987`.
Origen del parche: `b8beb17` (modelo v3 y OOD local).

Se integra EfficientNetB0 v3 con sus pesos, clases y preprocesamiento originales,
y el detector OOD por distancia coseno al quinto vecino. La calibración y las
referencias se verifican mediante SHA-256. Se sugiere un estilo únicamente si
la referencia pasa OOD y la confianza máxima es al menos 0,60. En otro caso se
devuelve E-99 y se solicita revisión profesional; la solicitud puede continuar.

Django valida la respuesta y guarda los metadatos OOD y el motivo de abstención.
Los cambios de pantalla se limitan al resultado del análisis ML. La agenda,
el portafolio, las cuentas, pagos y reservas conservan la versión de la rama base.
No se incluyen los lanzadores, entornos ni cambios generales de documentación
de la rama de pruebas anterior.

## Uso

Instalar `ml_service/requirements.txt` y `ml_service/requirements-modelo.txt`
en el entorno del servicio ML (Python 3.12), como en la integración anterior.
Los valores predeterminados seleccionan v3 y activan OOD. Si el entorno tenía
valores explícitos para v2, actualizarlos:

```dotenv
MTFLOW_MODEL_DIR=modelos/efficientnet_b0_v3
MTFLOW_OOD_ENABLED=1
MTFLOW_OOD_CALIBRATION=modelos/efficientnet_b0_v3/ood/calibracion_ood_v3.json
```

Aplicar `python manage.py migrate` desde `config` en el entorno de destino.
La migración `web.0016_prediccion_ood` agrega dos campos a las predicciones;
no reclasifica los registros existentes. Reiniciar ambos servicios.

Los archivos de evaluación incluidos corresponden a sus pruebas de origen;
no representan una medición nueva ni garantizan que OOD detecte toda imagen ajena.

## Verificación de esta integración

- Servicio ML: 62 pruebas aprobadas.
- Integración OOD en Django: 6 pruebas aprobadas, incluido el guardado de sus
  metadatos y la recepción de una solicitud que requiere revisión manual.
- Carga de los pesos reales e inferencia HTTP con v3 y OOD: aprobadas.
- Migraciones: no hay cambios de esquema pendientes fuera de la migración incluida.
- Suite Django: 328 pruebas, 319 aprobadas y 9 incidencias. La rama base sin el
  parche reproduce exactamente las mismas 9 incidencias entre sus 322 pruebas
  (6 fallos y 3 errores, vinculados a agenda, fechas y scripts en plantillas).
  Se conservan sin correcciones para respetar el alcance solicitado.
- Comparación con la base: los archivos de agenda y portafolio no cambian.
  En `web/models.py` solo se agregan los dos campos OOD a `Prediccion`.

La verificación se hizo con una base temporal. No se migró la base habitual
ni se desplegaron servicios.
