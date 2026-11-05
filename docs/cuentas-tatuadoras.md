# Cuentas y función de tatuadora

Una cuenta combina dos decisiones independientes:

| Permiso de cuenta | Es tatuadora | Función |
|---|---|---|
| Administrador | Sí | Administra cuentas y recibe sus propias propuestas |
| Administrador | No | Administra, sin aparecer en el selector público |
| Usuario | Sí | Recibe y consulta sus propias propuestas, sin administrar cuentas |
| Usuario | No | Acceso de equipo sin recibir nuevas propuestas |

En **Cuentas del equipo → Crear / Editar cuenta**, la opción **Es tatuadora**
habilita la recepción de propuestas. El perfil vinculado se crea automáticamente
si todavía no existe. Solo administradores pueden gestionar estas opciones.
Activar la función de tatuadora no concede permisos de administración.

El formulario público ofrece únicamente perfiles habilitados, vinculados a
cuentas activas con `es_tatuadora=True`. Sus nombres provienen de la cuenta actual,
evitando alias históricos como «Nueva Artista». El envío conserva la relación
`Postulacion → Tatuadora → Usuario`; «Mis cotizaciones» utiliza esa misma relación.
Cambiar el nombre de la cuenta no cambia la destinataria de las propuestas.

Desmarcar la función impide recibir nuevas propuestas; conserva el perfil y las
propuestas anteriores para consulta. Desactivar la cuenta impide iniciar sesión.
Un perfil desactivado explícitamente en la administración tampoco se ofrece.

## Compatibilidad

`cuentas.0002_usuario_es_tatuadora` agrega la opción, desactivada para cuentas nuevas.
`web.0003_funcion_tatuadora` la activa en cuentas que ya tenían un perfil habilitado,
para conservar la configuración previa. No cambia roles ni destinatarias existentes.
Conviene revisar esos perfiles heredados en Cuentas y desmarcar la función en las
cuentas exclusivamente administrativas o de demostración.

No se introduce un catálogo genérico de múltiples roles: se mantiene el control
de permisos existente y se permite combinarlo con la función de tatuadora.

## Verificación del equipo

1. En Cuentas, crear o editar una usuaria y marcar «Es tatuadora».
2. Si también administra, conservar su rol Administrador.
3. Abrir `/cotizacion/`, elegir su nombre y enviar una propuesta.
4. Entrar con esa cuenta a `/panel/cotizaciones/`: la propuesta debe aparecer allí.
5. Otra cuenta no debe verla. Al desmarcar «Es tatuadora», la profesional desaparece
   del selector sin perder el historial.

Pruebas en `web/test_selector_tatuadoras.py`: nombres actuales, cuentas y perfiles
desactivados, envío a la usuaria elegida, administración combinada, habilitación de
perfiles existentes, ausencia de duplicados y conservación del historial.
