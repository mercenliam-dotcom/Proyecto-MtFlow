import re
from django.db import migrations

# Corrige textos antiguos del historial como
# "Antes: (datetime.date(2026, 11, 11), datetime.time(14, 30), datetime.time(17, 26)). Ahora: 2026-11-11 14:30–17:30"
TUPLA = re.compile(r"\(datetime\.date\((\d+), (\d+), (\d+)\), datetime\.time\((\d+), (\d+)(?:, \d+)*\), datetime\.time\((\d+), (\d+)(?:, \d+)*\)\)")
ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2}) (\d{2}:\d{2})–(\d{2}:\d{2})")


def _tupla(m):
    a, me, d, h1, m1, h2, m2 = (int(x) for x in m.groups())
    return f"{d:02d}/{me:02d}/{a} {h1:02d}:{m1:02d}–{h2:02d}:{m2:02d}"


def corregir(apps, schema_editor):
    Evento = apps.get_model("web", "EventoSolicitud")
    for evento in Evento.objects.filter(tipo__in=["reprogramada", "reservada"]).only("pk", "detalle"):
        nuevo = TUPLA.sub(_tupla, evento.detalle)
        nuevo = ISO.sub(lambda m: f"{m[3]}/{m[2]}/{m[1]} {m[4]}–{m[5]}", nuevo)
        if nuevo != evento.detalle:
            Evento.objects.filter(pk=evento.pk).update(detalle=nuevo[:500])


class Migration(migrations.Migration):
    dependencies = [("web", "0018_movimientocobro_comprobante")]
    operations = [migrations.RunPython(corregir, migrations.RunPython.noop)]
