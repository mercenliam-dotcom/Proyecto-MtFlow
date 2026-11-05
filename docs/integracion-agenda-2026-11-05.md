# Integración del equipo y agenda privada — 5 de noviembre de 2026

## Origen y alcance

Punto de partida del escritorio: `feature/integracion-mtflow`, commit `7eb9772`.
Único cambio local detectado: `config/mtflow_local.sqlite3`, que se conserva y migra, sin sustituirlo por una base del repositorio.

Se integra la cadena de commits del equipo, sin duplicar merges:

- `origin/main` (`f4a0442`): incluye SQL, recepción persistente, bandejas y clasificación inmediata.
- `origin/integracion-modelo-v2` (`1fce8af`): integración del modelo propio.
- `origin/pruebas-modelo-v2-con-pesos` (`23fc43e`): pesos y metadatos EfficientNetB0 v2.

Todos son descendientes del commit original. La integración local está en `integracion/buzon-agenda-2026-11-05`; no se publica ni modifica ninguna rama remota.

## Flujo disponible

1. El cliente envía su referencia y contacto desde `/cotizacion/`. El código del equipo registra Cliente, Postulacion, Imagen y, si corresponde, Prediccion/ConfianzaEstilo. La imagen recodificada se guarda en almacenamiento privado; la base guarda su ruta y metadatos.
2. La tatuadora entra a **Solicitudes**, `/panel/cotizaciones/`. Ve nombre, medidas, estimación, estado y confianza; puede ordenar por confianza o antigüedad. Una simulación se identifica y no gana prioridad por sus cifras.
3. El detalle muestra imagen privada, contacto y análisis completo. La profesional registra revisión, acuerdo y precio final; puede rechazar sin borrar el historial.
4. Registra el monto acumulado del abono, confirmando que verificó el pago externo. MTFlow no cobra ni se conecta a una pasarela.
5. En **Mi agenda**, `/panel/agenda/`, crea disponibilidad. Reserva una o varias sesiones dentro de ella, asociadas a la solicitud con abono verificado. También puede bloquear tiempo personal.
6. Reprograma o cancela horarios, con registro de los cambios de las sesiones. Cancelar libera el intervalo; una sesión realizada queda en el historial. Solo al completar la última sesión reservada se marca realizada la solicitud.

La confianza corresponde al resultado del clasificador; no mide la confiabilidad del cliente. El endpoint público ya no devuelve porcentajes ni el vector de puntuaciones. El cliente sigue viendo la sugerencia de estilo.

La agenda requiere una cuenta activa con **Es tatuadora** habilitado y su perfil activo. Una cuenta administrativa no se transforma automáticamente en tatuadora. La administración puede habilitar esa función desde **Cuentas del equipo**. `/horarios/` redirige a la agenda privada y desaparece del menú público.

## Datos y controles

- Nuevas migraciones `web.0005` y `web.0006`: sesiones múltiples, UUID de horarios, verificación de abonos, historial y restricciones de agenda. Se conserva `Postulacion.bloque` como primer bloque por compatibilidad con el modelo original.
- Cada operación valida propiedad en el servidor, usa CSRF y transacción, y bloquea primero el registro de la profesional. SQLite adquiere bloqueo de escritura antes de leer disponibilidad.
- La base también impide intervalos superpuestos: triggers en SQLite; restricciones de exclusión GiST en PostgreSQL. Los extremos son abiertos al término: 10:00–11:00 permite otra sesión desde 11:00.
- Una disponibilidad ocupada no puede retirarse o reducirse dejando sesiones sin cobertura. Cambios desde formularios antiguos se rechazan mediante la versión del bloque.
- Fechas civiles de Santiago, sin conversiones por la zona del navegador; Django rechaza horas inexistentes/ambiguas por cambio horario. Cada bloque termina el mismo día; una sesión que cruce medianoche debe dividirse.
- Imágenes privadas y vistas autenticadas sin caché. FullCalendar y su licencia se sirven localmente. El nonce de estilos permite su CSS sin habilitar scripts inline.
- La cuenta débil de demostración `admin/admin` queda deshabilitada por defecto: solo se prepara con `DJANGO_DEBUG=1` y `ADMIN_DESARROLLO_HABILITADO=1`. No se modifican contraseñas de cuentas legítimas.

## Verificación

La base SQLite original se probó en una copia: migración completa, integridad y claves foráneas correctas; los campos originales de la cuenta existente permanecieron idénticos.

Pruebas: suite Django completa (226 casos en la ejecución completa), más los casos finales de orden por confianza, UUID inválido, sesiones múltiples y acciones según estado (26 pruebas de agenda aprobadas después de esos ajustes). Servicio ML: 81 aprobadas y 1 omitida (prueba externa de Roboflow); no se enviaron imágenes a Roboflow. Sin cambios de modelos pendientes de migración. Se verificaron los metadatos y SHA-256 del bundle v2.

En navegador: acceso autenticado, calendario con datos de prueba, buzón, acuerdo e historial y rechazo visible de una reserva superpuesta. Datos de prueba separados de la base del escritorio.

## Pendientes explícitos

- La base local sigue siendo **SQLite**. No se crearon recursos en Supabase ni AWS. Las migraciones incluyen PostgreSQL, pero esa variante no se ejecutó contra un servidor real; requiere habilitar `btree_gist` y ensayar la migración con las credenciales del proyecto.
- Se conserva la configuración `.env` y el entorno existente. Los pesos v2 quedan integrados, pero no se ejecutó inferencia real con TensorFlow: el entorno actual es Python 3.10 y el bundle del equipo declara Python 3.12/TensorFlow 2.21.0. Preparar un entorno separado del servicio ML antes de cambiar el proveedor activo.
- Guardar imágenes no reentrena el modelo automáticamente. Faltan consentimiento/criterios de uso, etiquetado profesional, selección de ejemplos, evaluación y publicación de versiones. Aceptar o rechazar una solicitud comercial no equivale a una etiqueta de estilo.
- Las rechazadas se conservan por ahora. No se implementó borrado automático ni anonimización: deben definirse plazos y cómo separar imágenes autorizadas para entrenamiento de los datos personales.
- Estimaciones económicas siguen siendo referenciales. El abono es un registro manual; no se implementaron cobros ni devoluciones.
- Las restricciones y el historial cubren el flujo web de la tatuadora. Un administrador con acceso directo a modelos o SQL sigue siendo una autoridad privilegiada; no debe editar estados o reservas por fuera del flujo.

## Respaldos y restauración

Los respaldos se guardaron fuera del repositorio, en `Proyecto mtflow/respaldo_integracion_2026_11_05`, junto con un bundle de Git. Antes de aplicar se realiza otra copia consistente de SQLite, se guardan huellas de la configuración y los archivos privados, y se conserva la rama original.

Para restaurar, detener los procesos de la aplicación y respaldar primero los datos actuales. El código anterior necesita su base anterior: no basta con cambiar de rama tras aplicar migraciones. No usar `git reset --hard` ni sobrescribir una SQLite con solicitudes nuevas. La base dejó de estar versionada en las ramas del equipo y permanece ignorada por Git.

## Dependencia visual

FullCalendar Standard 6.1.19, licencia MIT incluida en `config/static/vendor/fullcalendar/LICENSE.md`. SHA-256 del JS: `223ff800a0b0b87a1c96c1d127a9a981434e14f88a7b1662fecade17c78ea203`.
Origen: https://cdn.jsdelivr.net/npm/fullcalendar@6.1.19/index.global.min.js
