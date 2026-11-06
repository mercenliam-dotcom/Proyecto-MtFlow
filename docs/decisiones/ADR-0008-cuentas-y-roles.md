# ADR-0008 — Cuentas y roles sin registro público

> Decisión histórica parcialmente sustituida por el [portal de clientes del 6 de noviembre de 2026](../portal-clientes-2026-11-06.md), autorizado posteriormente. Se conserva la creación administrativa de cuentas del equipo y se añade registro público limitado al rol Cliente.

**Estado:** aceptada · **Fecha:** 2026-11-02

## Contexto

El MER del 2 de octubre fijaba `AUTH_USER_MODEL = "cuentas.Tatuadora"`: el único usuario autenticado era la tatuadora. Para el prototipo se necesita además distinguir quién administra el sistema (crea cuentas, asigna permisos) de quién solo lo usa, y el equipo de desarrollo también necesita acceso.

## Decisión

1. El modelo de usuario pasa a ser `cuentas.Usuario` (tabla `usuario`) con un campo `rol`: **ADMIN** o **USUARIO**.
2. **No existe registro público.** Solo un administrador crea cuentas desde el panel. El primer administrador se crea con `python manage.py createsuperuser`.
3. Toda cuenta creada recibe una contraseña temporal que debe cambiarse en el primer ingreso.
4. Las cuentas no se borran, se desactivan (trazabilidad: `creado_por`).
5. El cliente del estudio sigue sin cuenta (decisión #1 del modelo de datos).

## Consecuencias

- Las tablas que en el MER apuntaban a `tatuadora` (`tatuadora_estilo`, `bloque_horario`, `postulacion`, `trabajo_portafolio`) apuntarán a `usuario`. Si se necesita saber qué cuentas son tatuadoras, se agrega `es_tatuadora` o se deduce de `tatuadora_estilo`. **Hay que actualizar los diagramas 03 (clases) y 04 (MER).**
- Se fija antes de la primera migración: cambiar `AUTH_USER_MODEL` después obliga a recrear la base.
