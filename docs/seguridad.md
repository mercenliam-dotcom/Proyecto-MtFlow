# Matriz de seguridad — MTFlow

**Actualización 03-11-2026:** esta matriz describe controles del código, no acredita un despliegue. Ver [revisión y límites actuales](revision-2026-11.md). El cifrado del proveedor, certificados y respaldos no se verificaron. La vista privada de archivos aún requiere autorización por propietaria antes de usarse para referencias de clientes.

Cada medida indica dónde está implementada y qué prueba automática la verifica. Sirve como evidencia para el informe (RNF de seguridad, OWASP Top 10) y para la defensa.

## Cifrado: qué se cifra y qué no

Conviene redactarlo con precisión en el informe, porque "cifrado" se usa para cosas distintas:

| Dato | Mecanismo | Correcto decir |
|---|---|---|
| Tráfico navegador ↔ servidor | TLS (HTTPS) forzado + HSTS 1 año | **cifrado en tránsito** |
| Conexión Django ↔ PostgreSQL | `sslmode=require` | **cifrado en tránsito** |
| Base de datos y Storage en proveedor | Depende del despliegue y contrato | **Pendiente de verificar**; SQLite local no se cifra automáticamente |
| Contraseñas | Argon2id con sal | **hash**, no cifrado: es irreversible, nadie puede recuperar la contraseña, ni el administrador |
| Enlaces a imágenes privadas | Firma HMAC-SHA256 con caducidad (10 min) | **firma**, no cifrado: la ruta no se oculta, pero no se puede alterar ni reutilizar |
| Identificadores en URLs | UUID aleatorio | **no enumerable**: no se puede adivinar `/cuentas/2`, `/3`… |

SSL es el nombre antiguo; el protocolo vigente es TLS 1.2/1.3. En el informe conviene decir "TLS (HTTPS)".

## Medidas

| Amenaza | Medida | Dónde | Prueba |
|---|---|---|---|
| Registro no autorizado | No existe ruta de registro; crear cuentas exige rol ADMIN verificado en servidor | `cuentas/urls.py`, `permisos.py` | `SinRegistroPublico`, `PermisosPorRol` |
| Escalada de privilegios | Rol validado en cada petición; `CHECK` en la BD sobre el rol; nadie se quita su propio rol; siempre queda ≥1 admin | `permisos.py`, `models.py`, `forms.py` | `test_usuario_normal_no_puede_ascenderse_por_post`, `ProteccionDelUltimoAdmin` |
| Contraseñas débiles | Mín. 10, letra + número, no común, no solo números, no parecida al usuario | `settings.AUTH_PASSWORD_VALIDATORS`, `validadores.py` | `test_contrasena_*` |
| Fuerza bruta | Bloqueo 15 min tras 5 fallos por usuario (20 por IP); mensaje idéntico exista o no la cuenta | `seguridad.py` | `test_bloqueo_tras_intentos_fallidos`, `test_mismo_mensaje_si_usuario_no_existe` |
| Inyección SQL | Solo ORM con consultas parametrizadas; formato de usuario restringido | todo el proyecto | `test_inyeccion_sql_en_usuario` |
| XSS / alterar plantillas | Autoescape activo; prohibido `|safe`, `mark_safe`, `autoescape off`; CSP sin scripts en línea; plantillas solo en el servidor | `settings.TEMPLATES`, `middleware.py` | `test_plantillas_escapan_html`, `test_no_hay_scripts_en_linea_en_plantillas` |
| Host header ("cambiar el localhost") | `ALLOWED_HOSTS` estricto; `X-Forwarded-Host` ignorado | `settings.py` | `HostHeader` |
| Redirección maliciosa (open redirect) | `next` solo si es ruta interna relativa | `nucleo/redirecciones.py` | `test_redireccion_externa_bloqueada` |
| CSRF | Token en todo formulario POST; cerrar sesión solo por POST | Django + `views.py` | `test_sin_csrf_rechaza`, `test_salir_solo_por_post` |
| Secuestro de sesión | Cookies `HttpOnly`, `Secure`, `SameSite=Lax`; id de sesión rotado al ingresar; expira en 8 h o al cerrar el navegador | `settings.py` | `test_sesion_cambia_al_ingresar` |
| Clickjacking | `X-Frame-Options: DENY` + `frame-ancestors 'none'` | `settings.py` | `test_cabeceras_de_seguridad` |
| Subida de documentos o videos | Solo `.jpg/.jpeg/.png` **y** firma binaria real JPEG/PNG; detecta PDF, Word, MP4, MOV, WebM, GIF, WebP, SVG, HTML | `nucleo/imagenes.py` | `DocumentosYVideosRechazados`, `FormatosRechazados` (16 casos) |
| Archivo disfrazado (`video.mp4` → `video.jpg`) | Se ignoran extensión y Content-Type declarados; manda el contenido | `imagenes.py` | `test_mp4_renombrado_jpg_con_content_type_mentiroso` |
| Video o página por URL | No existe campo URL; el servidor nunca descarga direcciones escritas por el usuario (sin SSRF) | `clasificacion/forms.py` | `test_campo_url_inyectado_se_ignora` |
| PNG animado (APNG) | Rechazado | `imagenes.py` | `test_png_animado_apng` |
| Bomba de descompresión | Límite de 40 MP; aviso de Pillow tratado como error | `imagenes.py` | `test_bomba_de_descompresion` |
| Archivo políglota / código oculto | La imagen se re-codifica desde los píxeles; el original se descarta | `imagenes.py` | `test_elimina_contenido_politoglota` |
| Fuga de ubicación del cliente | Se eliminan todos los metadatos EXIF (incluido GPS) | `imagenes.py` | `test_elimina_metadatos_exif` |
| Path traversal | Nombre de archivo reemplazado por UUID; vista de archivos no sale de `MEDIA_ROOT` | `imagenes.py`, `nucleo/views.py` | `test_nombre_guardado_es_aleatorio`, `test_no_sale_de_media_aunque_este_firmado` |
| Exceso de archivos o tamaño | 10 MB por imagen, máx. 3 archivos por petición | `settings.py` | `test_demasiado_pesada`, `test_mas_de_tres_archivos_rechazado` |
| Servicio ML expuesto | Clave compartida `X-API-Key` (comparación en tiempo constante); sin `/docs` públicos; re-valida la imagen | `ml_service/app/main.py` | `test_sin_clave_rechaza`, `test_sin_documentacion_publica` |
| Respuesta ML manipulada | Validación estricta del JSON (clases, rango, suma positiva y ≤ 1,01); sin seguir redirecciones | `cliente_ml.py` | `ValidacionRespuesta` |
| Fuga de detalles en errores | Páginas 400/403/404/500 propias; `DEBUG=0` en producción | `nucleo/errores.py` | `test_error_404_no_filtra_detalles` |
| Admin de Django predecible | Ruta configurable (`DJANGO_ADMIN_URL`) | `config/urls.py` | — |
| Fuga de la clave de Roboflow | Solo en `ml_service/.env` (ignorado por Git); viaja en `Authorization: Bearer`, nunca en la URL ni en el cuerpo; nunca llega al navegador; no se registran URLs ni cuerpos de error | `ml_service/app/roboflow_workflow.py`, `predictor.py` | `test_peticion_respeta_la_definicion_del_workflow`, `test_servicio_responde_503_si_roboflow_falla` |
| Datos enviados a un tercero (Roboflow) | Se envía solo la imagen re-codificada (sin EXIF/GPS) y reducida a 640 px; sin nombre, correo ni teléfono | `predictor.py` | `test_peticion_bien_formada` |
| Respuesta del modelo manipulada o inesperada | Clases desconocidas, valores fuera de [0,1] o NaN se rechazan; nunca se adivina una clase | `predictor.py`, `cliente_ml.py` | `test_clase_desconocida_se_rechaza`, `test_respuestas_invalidas` |
