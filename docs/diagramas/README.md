# Diagramas de MTFlow — entrega final (17 de noviembre de 2026)

Diagramas actualizados a lo que **hace hoy el programa**. Cada uno sale del código o de
una fuente editable que está en esta carpeta, para que el informe y la aplicación no se
vuelvan a separar.

Para Word, usar el `.svg` (vectorial, no se pixela al ampliar). El `.png` sirve para
revisarlos rápido.

## Inventario

| # | Diagrama | Notación | ¿Cambió? | Qué cambió respecto del informe |
|---|---|---|---|---|
| 01 | Casos de uso: Visitante y Cliente | UML | **Sí** | Cliente con cuenta (hereda del Visitante), catálogo, consentimiento público, validación de datos y revisión del dominio del correo, imagen que se conserva, rango de estimación, **recuperar contraseña**. |
| 02 | Casos de uso: Tatuadora y Administradora | UML | **Sí** | Acuerdo con rango precargado, abono 30–40 %, agenda sin solapamiento, **consentimiento con dos firmas**, cierre de sesión e inasistencia, pago final, **terminar trabajo con saldo en cero y consentimiento**, galería de referencias, métricas, cuentas del equipo. |
| 03 | Clases del dominio | UML | **Sí** | Generado desde los modelos: 20 clases. Nuevo `Consentimiento` y `Postulacion.precio_sugerido_maximo`. |
| 04 | DER / MER (modelo físico) | IE (pata de gallo) | **Sí** | Generado desde los modelos: 20 tablas, 186 columnas, 32 relaciones. Tabla nueva `consentimiento` (1 a 1 con `postulacion`) y columna nueva `postulacion.precio_sugerido_maximo`. |
| 05 | Máquina de estados de la solicitud | UML | **Sí** | Estados reales del código (RECIBIDA, EN_REVISION, ACEPTADA, RESERVADA, REALIZADA, RECHAZADA), con las condiciones para terminar: sesión realizada, consentimiento completo y saldo en cero. |
| 06 | Secuencia: envío de una solicitud | UML | **Sí** | Revisión automática del correo, imagen pendiente que sobrevive a los errores, doble clasificación (no se confía en el navegador) y Post/Redirect/Get (al recargar, el formulario queda vacío). |
| 07 | Secuencia: acuerdo y reserva, consentimiento, sesión, pago y cierre | UML | **Nuevo** | Reemplaza la secuencia «Reserva»: acuerdo con rango, abono, agenda con bloqueo de fila (RNF-11), consentimiento, pago final y término del trabajo. |
| 08 | Componentes | UML | **Sí** | Módulos reales de Django (`web`, `cuentas`, `nucleo`, `clasificacion`), servicio FastAPI con EfficientNetB0 v3 y detección fuera de distribución, almacén privado, DNS (revisión del correo) y SMTP (recuperar contraseña). |
| 09 | Proceso TO-BE | BPMN 2.0 | **Sí** | Tareas nuevas o modificadas marcadas en verde: validación y revisión del correo, conservar datos e imagen ante errores, rango de precio, acuerdo con abono 30–40 %, consentimiento, verificación de saldo y cierre en solo lectura. |
| — | Proceso AS-IS | BPMN 2.0 | **No** | Describe cómo trabajaba el estudio **antes** del sistema (Instagram/WhatsApp, cotización manual). Lo que se agregó al programa no cambia ese proceso: se mantiene el del informe. |
| 09b | Proceso TO-BE (actividad con calles) | UML | **Nuevo** | Misma notación que el AS-IS del informe para compararlos lado a lado. |
| 11 | Topología de comunicaciones | — | **Sí** | Puertos y protocolos reales: HTTPS 443, PostgreSQL con TLS 5432, SMTP 587, DNS 53 y red privada para el servicio ML. |
| 12 | Infraestructura | UML | **Sí** | Render (servicio web + servicio privado de inferencia + disco persistente) y Supabase PostgreSQL; sin Amazon S3. |
| 13 | Arquitectura de software | UML | **Sí** | Django sin DRF, inferencia con TensorFlow/Keras (no PyTorch), almacenamiento privado en disco. |
| 10 | Despliegue | UML | **Sí** | Render (gunicorn + Django, sin Django REST Framework) con disco persistente para las imágenes privadas; Supabase solo como PostgreSQL 16 (Supabase Storage no está implementado: queda como mejora futura); servicio ML separado (FastAPI + EfficientNetB0 v3 con TensorFlow, clave X-API-Key); servicios externos SMTP (recuperar contraseña) y DNS (revisión del dominio del correo). |

## Qué reemplazar en el informe (Informe_MTFlow_EVA_2.docx)

Revisión figura por figura del informe contra el código (20 de noviembre de 2026).

| Figura del informe | Acción | Archivo | Motivo |
|---|---|---|---|
| Diagrama de componentes | Reemplazar | `08_componentes` | Decía Django REST Framework, Bootstrap, almacenamiento de objetos e integración con Instagram/WhatsApp/TikTok; nada de eso existe en el código. |
| Diagrama de despliegue | Reemplazar | `10_despliegue` | Django REST Framework y Supabase Storage no están implementados. |
| Secuencia «Reserva» | Reemplazar | `07_secuencia_sesion_y_cierre` | El paso «Redirección a WhatsApp» no existe; faltaban acuerdo, abono, bloqueo de horario, consentimiento, pago final y cierre. |
| Secuencia «Clasificación de imagen» | Reemplazar | `06_secuencia_envio_solicitud` | Decía que la imagen va a almacenamiento de objetos; faltaban la imagen pendiente y la revisión del correo. |
| AS-IS (actividad) | **Mantener** | — | Proceso del estudio antes del sistema; sigue siendo correcto. |
| TO-BE (actividad) | Reemplazar | `09b_actividad_TO-BE` | Misma notación que el AS-IS, para compararlos. Agrega validación, consentimiento, pago final y cierre. El BPMN `09_BPMN_TO-BE` puede ir como complemento. |
| Casos de uso (General, Gestión de solicitudes, Cotización y agendamiento, Portafolio y analítica) | Reemplazar los cuatro | `01_casos_uso_visitante_cliente` y `02_casos_uso_equipo` | Faltaban registro de cliente, recuperar contraseña, consentimiento, abono, pago final, terminar trabajo, referencias y cuentas del equipo. |
| Modelo de datos (DER, dbdiagram) | Reemplazar | `04_DER` | El del informe tiene 11 tablas; la base real tiene 20. |
| Topología de comunicaciones | Reemplazar | `11_topologia_comunicaciones` | Mostraba «Object Storage»; faltaban puertos reales, red privada del servicio ML, SMTP y DNS. |
| Diagrama de infraestructura | Reemplazar | `12_infraestructura` | Mostraba Amazon S3 (además contradecía al de despliegue, que decía Supabase Storage). |
| Diagrama de arquitectura | Reemplazar | `13_arquitectura_software` | Decía Django REST Framework, **PyTorch** (el modelo es TensorFlow/Keras) y Amazon S3. |
| Diagrama de clases | Agregar si corresponde | `03_clases_dominio` | El informe no lo tiene; es opcional. |
| Máquina de estados | Agregar si corresponde | `05_estados_solicitud` | El informe no la tiene; explica los estados comerciales que el texto menciona. |

Ojo con el texto del informe: si en algún párrafo se menciona Django REST Framework,
PyTorch, Amazon S3, Supabase Storage, Bootstrap o la «redirección a WhatsApp», hay que
corregirlo igual que en los diagramas.

## Casos de uso (para la tabla del apartado 8.2)

La numeración cambió respecto del informe, porque el sistema creció. Conviene reemplazar
la tabla completa por esta.

| CU | Nombre | Actor principal | Nuevo en la entrega final |
|---|---|---|---|
| CU-01 | Consultar portafolio por estilo | Visitante | |
| CU-02 | Explorar catálogo completo con filtro | Visitante | ✔ |
| CU-03 | Consultar horarios del estudio | Visitante | |
| CU-04 | Leer consentimiento informado | Visitante | ✔ |
| CU-05 | Enviar solicitud de tatuaje (incluye seleccionar tatuadora, validar datos, revisar el dominio del correo, adjuntar imagen, obtener estimación; se extiende con el análisis previo de la imagen) | Visitante / Cliente | validación, correo e imagen persistente |
| CU-06 | Registrarse como cliente | Visitante | |
| CU-07 | Iniciar sesión | Cliente | |
| CU-08 | Recuperar contraseña (solo clientes; enlace de un uso que vence en 2 horas) | Cliente | ✔ |
| CU-09 | Consultar mis solicitudes y su estado | Cliente | |
| CU-10 | Gestionar mi perfil (datos y foto) | Cliente | |
| CU-11 | Revisar bandeja de solicitudes | Tatuadora | |
| CU-12 | Confirmar o corregir el estilo sugerido | Tatuadora | |
| CU-13 | Registrar acuerdo y aceptar (precio desde el rango estimado, medidas precargadas) | Tatuadora | precarga del rango |
| CU-14 | Rechazar solicitud con motivo | Tatuadora | |
| CU-15 | Registrar abono verificado (30 % a 40 %) | Tatuadora | |
| CU-16 | Gestionar agenda (jornada, bloqueos, citas sin solapamiento) | Tatuadora | |
| CU-17 | Firmar consentimiento informado (ficha del cliente + declaración de la tatuadora) | Tatuadora y Cliente | ✔ |
| CU-18 | Cerrar sesión: realizada o inasistencia (exige consentimiento completo) | Tatuadora | condición de consentimiento |
| CU-19 | Registrar pago final o devolución | Tatuadora | |
| CU-20 | Terminar trabajo (exige saldo en cero y consentimiento; queda solo lectura) | Tatuadora | ✔ condiciones |
| CU-21 | Gestionar portafolio | Tatuadora | |
| CU-22 | Consultar imágenes de referencia | Tatuadora | ✔ |
| CU-23 | Consultar métricas del estudio | Tatuadora | |
| CU-24 | Consultar historial de operaciones | Tatuadora | |
| CU-25 | Gestionar cuentas del equipo | Administradora | |
| CU-26 | Consultar solicitudes de todo el equipo | Administradora | |

Actores de sistema: Servicio de clasificación ML, Servidor DNS (revisión del dominio del
correo) y Servidor de correo SMTP (recuperar contraseña). Toda tatuadora es Administradora;
una Administradora puede no tatuar.

**Acceso con Google/Facebook: no forma parte de la entrega.** El código quedó a medio
camino y está desactivado (`ACCESO_SOCIAL_VISIBLE=0`); no aparece en ningún diagrama de
comportamiento. La tabla `identidad_social` existe en la base de datos (por eso figura en el
DER y en el diagrama de clases, con una nota), pero no se usa. Se puede mencionar como
trabajo futuro.

## Cómo regenerarlos

Desde la carpeta del proyecto, con el entorno de Django activo:

```
python scripts/generar_der_dbml.py        # docs/der/*.dbml (para dbdiagram.io)
python scripts/generar_der_plantuml.py    # 04_DER.puml
python scripts/generar_clases_plantuml.py # 03_clases_dominio.puml
python scripts/generar_bpmn_tobe.py       # 09_BPMN_TO-BE.svg
```

Los `.puml` se convierten a imagen pegándolos en https://www.plantuml.com/plantuml o con
`java -jar plantuml.jar -tsvg archivo.puml`. Los 01, 02 y 05 a 08 se editan a mano en su
`.puml`; el 03 y el 04 se regeneran desde el código cuando cambian los modelos.

Al insertarlos en el informe: numerar las figuras y agregar el pie
«Figura N. Título. Fuente: elaboración propia».
