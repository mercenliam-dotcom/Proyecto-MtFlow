from django.db import migrations, models
from django.db.models import F


def marcar_existentes(apps, schema_editor):
    # Las solicitudes anteriores no aparecen como avisos nuevos.
    apps.get_model("web", "Postulacion").objects.filter(vista_en__isnull=True).update(vista_en=F("creada_en"))


class Migration(migrations.Migration):
    dependencies = [("web", "0015_tatuadora_telefono")]
    operations = [
        migrations.AddField(model_name="postulacion", name="vista_en", field=models.DateTimeField(blank=True, null=True)),
        migrations.RunPython(marcar_existentes, migrations.RunPython.noop),
    ]
