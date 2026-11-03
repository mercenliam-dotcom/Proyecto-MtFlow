# Revisión MTFlow — 3 de noviembre de 2026

## Alcance

Rediseño local del sitio público y área privada; estimador referencial sin persistencia; revisión de controles de seguridad. Se conservan Django, FastAPI/Uvicorn y el contrato con Roboflow. No se instala Node ni se agrega un proveedor de análisis. No se modifica el entrenamiento, las credenciales, la base real, las migraciones existentes ni el despliegue.

## Diseño y compatibilidad

- `config/templates/layout.html`: estructura común, navegación, acceso por teclado y pie.
- Las bases pública y privada heredan esa estructura, manteniendo los nombres de bloques de sus pantallas anteriores.
- `config/static/css/design.css`: colores, tipografía, formularios, botones y adaptación a móvil compartidos. `app.css` conserva componentes específicos del equipo.
- Se conservan URLs, permisos, cierre de sesión por POST, filtros y selección de horarios. El portafolio usa los siete nombres del catálogo de ML, sin duplicar taxonomías.
- Las fotografías siguen pendientes y los horarios siguen siendo una demostración; no se presentan como obras ni reservas reales.

## Cotización referencial

Formulario POST con validación Django, CSRF, vista previa y rango en CLP calculado en el servidor. Los montos enviados por el navegador no son aceptados. Funciona también sin JavaScript; en ese caso la vista previa aparece tras procesar el formulario.

Tarifa `demo-2026-11-v1`, definida en `config/web/precios.py`:

| Lado mayor declarado | Rango base de demostración |
|---|---|
| Hasta 5 cm | $35.000–$60.000 |
| Más de 5 y hasta 15 cm | $65.000–$110.000 |
| Más de 15 y hasta 25 cm | $110.000–$190.000 |
| Más de 25 cm o por definir | Revisión manual |

Estos valores fueron inventados para el prototipo con autorización del usuario. **No representan una investigación de mercado, un promedio comprobado ni tarifas aprobadas por el estudio.** Ambas profesionales comparten la tabla provisional. Ajustes aditivos sobre el rango base: color +20 %, detalle alto declarado +25 %, pecho/costillas +15 %. Redondeo hacia fuera a múltiplos de $5.000 con Decimal. Coberturas y otras zonas requieren revisión manual. No se modelan todas las proporciones, el área real, el tiempo de diseño o las sesiones: por ello no se entrega un precio definitivo.

El análisis es opcional y se autoriza con una casilla sin marcar por defecto. Solo la imagen validada y recodificada se envía al servicio ML; los contactos no se envían allí. Se identifica la simulación y se conserva la estimación si ML falla. El estilo detectado **no** altera el precio: no hay evidencia para convertir la confianza del clasificador en una tarifa o grado de complejidad. La confianza de clasificación tampoco es precisión del precio.

Nombre, correo, teléfono e imagen se procesan para el resumen, no se almacenan como solicitudes ni se envían al equipo. No hay historial, citas, abonos ni pagos nuevos. Los registros normales del servidor no deben incluir cuerpos de POST. El proveedor de inferencia puede tener políticas de retención propias: deben revisarse antes de usar imágenes reales en producción. Para recalcular tras una respuesta hay que volver a seleccionar la imagen; no se conserva un archivo privado para reutilizarlo.

## Seguridad evaluada y reforzada

- Reutilización del validador de contenido JPEG/PNG: límites, formato real, dimensiones, nitidez, recodificación y eliminación de metadatos.
- Nuevo manejador de subida: corta cada archivo que exceda el límite durante la lectura multipart, antes de escribirlo completo en disco. El proxy debe imponer su propio límite de cuerpo y tiempo de recepción.
- Cotización limitada por IP a 10 POST cada 600 segundos, configurable; la caché local solo cubre un proceso. Para varios procesos o instancias se necesita caché compartida y límites en el proxy. Esto no garantiza protección frente a ataques distribuidos.
- Validación por lista de opciones permitidas, límites de texto y correo. Escape de salida conservado; sin HTML confiado, scripts en línea ni dependencias remotas.
- CSRF conservado, respuestas de cotización con `no-store`, URL fija del servicio ML y rechazo de redirecciones en el cliente existente.
- `CONFIAR_EN_PROXY` queda desactivado por defecto. Para terminar HTTPS en un proxy controlado se debe activar explícitamente **después de verificar que reescribe encabezados y bloquea acceso directo al backend**. Este ajuste requiere atención al desplegar, para evitar bucles de redirección.
- Compatibilidad con archivos `.env` con BOM de Windows.

### Cifrado y límites de la revisión

HTTPS protege el tráfico en producción cuando el certificado y el proxy están correctamente configurados. La URL no se “cifra” mediante IDs: identificadores aleatorios y firmas no sustituyen autorización. Las contraseñas ya usan hash Argon2; no son reversibles.

No se verificó un alojamiento ni un certificado real, y **no se agregó cifrado en reposo a SQLite**. La base real y sus copias requieren cifrado de disco/proveedor, control de accesos y gestión de claves. Para PostgreSQL debe verificarse TLS y, cuando sea posible, identidad del servidor mediante `verify-full` y una CA confiable. Django→ML debe usar HTTPS si atraviesa una red no confiable; el ejemplo HTTP es local. Los secretos continúan fuera del código.

La vista existente de archivos privados exige sesión y firma, pero no asocia cada archivo a su propietaria. Antes de almacenar referencias de clientes se debe incorporar autorización por objeto y pruebas de acceso cruzado; este estimador no guarda archivos ni usa esa ruta. Los roles y pruebas existentes no acreditan por sí solos aislamiento de futuras solicitudes.

No es una auditoría de penetración ni certificación. Quedan pendientes revisión del proveedor, respaldos/restauración, retención, separación de datos por profesional al implementar persistencia, límites distribuidos y comprobación real del despliegue.

Referencias consultadas: [Django, configuración](https://docs.djangoproject.com/en/5.2/ref/settings/), [OWASP, subida de archivos](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html).

## Verificación

Antes de modificar: 112 pruebas Django, con un error de limpieza de archivo abierto en Windows. Se corrigió cerrando FileResponse en la prueba; no se alteró la función de descarga.

Después: 127 pruebas Django aprobadas; 58 pruebas ML aprobadas y una prueba real Roboflow omitida. Las pruebas ML necesitaron ejecución fuera del entorno restringido porque este bloqueaba el socket interno de asyncio; no era una falla de la aplicación. Advertencia previa de compatibilidad futura entre Starlette y httpx, sin fallos.

Navegador: cotización con imagen sintética y rango $35.000–$60.000, filtros, selección/limpieza de horario, login y clasificación privada contra FastAPI simulado; revisión de diseño en escritorio y móvil, sin desbordamiento horizontal en cotización. No se usaron imágenes personales ni créditos de Roboflow. Las pruebas de base se ejecutaron en SQLite de prueba; falta repetirlas en PostgreSQL del despliegue.

Comprobación de despliegue con configuración sintética: sin errores; única advertencia por HSTS preload desactivado intencionalmente. No se activa una inscripción de dominio en listas preload desde esta revisión. `collectstatic` completado con 134 archivos y procesamiento de manifiestos. Esto verifica empaquetado, no un despliegue real.
