"""Ensayo reproducible de migración con datos históricos; solo SQLite temporal.

Ejecutar con el Python del proyecto desde cualquier directorio.
No lee ni modifica la base operativa. --inconsistente comprueba rollback.
"""
import os
import sys
import tempfile
from datetime import date, time
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / "config"))
os.environ.update(DJANGO_SETTINGS_MODULE="config.settings", DJANGO_DEBUG="1",
                  DJANGO_SECRET_KEY="migration-verification-only-not-production",
                  ML_SERVICE_API_KEY="not-used", DATABASE_URL="", ADMIN_DESARROLLO_HABILITADO="0")

with tempfile.TemporaryDirectory(prefix="mtflow_migracion_") as tmp:
    from django.conf import settings
    settings.DATABASES["default"]["NAME"] = str(Path(tmp) / "prueba.sqlite3")
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    try:
        call_command("migrate", "web", "0006", verbosity=0, interactive=False)
        apps = MigrationExecutor(connection).loader.project_state([("web", "0006_agenda_sin_solapes")]).apps
        U, T, C, P, B, I = [apps.get_model(*nombre.split(".")) for nombre in ("cuentas.Usuario", "web.Tatuadora", "web.Cliente", "web.Postulacion", "web.BloqueHorario", "web.Imagen")]
        u = U.objects.create(nombre_usuario="historica", email="historica@example.test", nombre="Ana", apellido="Prueba", password="!", es_tatuadora=True)
        t = T.objects.create(usuario=u, nombre="Ana Prueba")
        E, TP = apps.get_model("web", "Estilo"), apps.get_model("web", "TrabajoPortafolio")
        estilo = E.objects.create(codigo="E-05", nombre="Línea fina")
        for numero in (1, 2):
            TP.objects.create(tatuadora=t, estilo=estilo, titulo=f"Trabajo anterior {numero}", url=f"portafolio/anterior-{numero}.jpg", publicado_en=date(2026, 1, 1))
        c = C.objects.create(nombres="Cliente anterior", apellidos="Prueba", correo="anterior@example.test")
        p = P.objects.create(cliente=c, tatuadora=t, zona_cuerpo="brazo", alto_cm=5, ancho_cm=4, area_cm2=21 if "--inconsistente" in sys.argv else 20, categoria_tamano="pequeno", descripcion="IDEA: Una flor | COLOR: color | DETALLE: alto | COVER-UP: True", estado="RESERVADA", precio_final=100000, monto_abono=30000)
        referencia = p.referencia
        b1 = B.objects.create(tatuadora=t, postulacion=p, tipo="CITA", estado="RESERVADA", fecha=date(2026, 12, 10), hora_inicio=time(10), hora_fin=time(11))
        b2 = B.objects.create(tatuadora=t, postulacion=p, tipo="CITA", estado="RESERVADA", fecha=date(2026, 12, 10), hora_inicio=time(11), hora_fin=time(12))
        p.bloque = b1
        p.save()
        im = I.objects.create(postulacion=p, url="postulaciones/archivo-anterior.jpg", orden=1, es_principal=True, formato="JPEG", ancho_px=300, alto_px=400, tamano_bytes=10000)
        libre = P.objects.create(cliente=c, tatuadora=t, zona_cuerpo="brazo", alto_cm=2, ancho_cm=3, area_cm2=6, categoria_tamano="pequeno", descripcion="Descripción libre anterior, sin opciones", estado="RECIBIDA")
        if "--inconsistente" in sys.argv:
            try:
                call_command("migrate", verbosity=0, interactive=False)
            except RuntimeError as exc:
                assert "inconsistentes" in str(exc)
            else:
                raise AssertionError("La migración debió detenerse sin corregir datos por su cuenta")
            assert P.objects.get(pk=p.pk).area_cm2 == 21
            assert "web_contactosolicitud" not in connection.introspection.table_names()
            print("OK: inconsistencias detectadas y migración revertida sin pérdida de datos.")
        else:
            call_command("migrate", verbosity=0, interactive=False)
            from web.models import Postulacion, Cliente, Tatuadora, Imagen, Sesion
            nuevo = Postulacion.objects.get(pk=p.pk)
            assert nuevo.referencia == referencia and nuevo.cliente_id == c.pk
            assert nuevo.contacto.nombres == "Cliente anterior"
            assert nuevo.descripcion == "Una flor" and nuevo.color == "color" and nuevo.nivel_detalle == "alto" and nuevo.cobertura is True
            assert nuevo.area_cm2 == 20 and nuevo.categoria_tamano == "pequeno"
            assert set(nuevo.sesiones.values_list("pk", flat=True)) == {b1.pk, b2.pk}
            assert nuevo.precio_final == 100000 and nuevo.monto_abono == 30000
            assert nuevo.abono_verificado_en is None  # No inventar verificación de un pago antiguo.
            assert nuevo.total_cobrado == 0
            assert nuevo.contacto.primer_apellido == "Prueba"
            from web.models import TrabajoPortafolio
            fotos = list(TrabajoPortafolio.objects.all())
            assert len({f.referencia for f in fotos}) == 2
            assert all(not f.visible and not f.autorizacion_publicacion for f in fotos)
            assert Imagen.objects.get(pk=im.pk).url == "postulaciones/archivo-anterior.jpg"
            assert Tatuadora.objects.get(pk=t.pk).nombre_artistico is None
            texto = Postulacion.objects.get(pk=libre.pk)
            assert texto.descripcion == libre.descripcion and texto.color is None and texto.cobertura is None
            assert Cliente.objects.filter(pk=c.pk).exists()
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA integrity_check")
                assert cursor.fetchone()[0] == "ok"
                cursor.execute("PRAGMA foreign_key_check")
                assert not cursor.fetchall()
            print("OK: contactos, opciones, dos sesiones, importes, referencia e imagen conservados; integridad correcta.")
    finally:
        connection.close()
