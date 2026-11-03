# Integración continua (CI)

`ci.yml` corre todas las pruebas de Django (sobre PostgreSQL 16) y del servicio de inferencia en cada push y en cada Pull Request, además de `check --deploy`.

Está aquí y no en `.github/workflows/` porque GitHub solo acepta archivos de esa carpeta si quien los sube tiene un token con el permiso **`workflow`**.

## Activarlo (una sola vez)

**Opción A — desde la web de GitHub (no necesita token):**
1. En el repositorio, elige la rama, entra a *Add file → Create new file*.
2. Nombre: `.github/workflows/ci.yml`
3. Pega el contenido de `docs/ci/ci.yml` y guarda con *Commit changes*.

**Opción B — desde la terminal:** crear un token con los permisos `repo` y `workflow`, y luego:
```bash
mkdir -p .github/workflows && git mv docs/ci/ci.yml .github/workflows/ci.yml
git commit -m "ci: activar pruebas automáticas" && git push
```
