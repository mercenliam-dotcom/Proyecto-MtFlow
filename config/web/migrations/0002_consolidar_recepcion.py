import uuid

from django.db import migrations, models


def referencias_existentes(apps, schema_editor):
    Postulacion = apps.get_model("web", "Postulacion")
    for pk in Postulacion.objects.using(schema_editor.connection.alias).filter(referencia__isnull=True).values_list("pk", flat=True).iterator():
        Postulacion.objects.using(schema_editor.connection.alias).filter(pk=pk).update(referencia=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("web", "0001_initial")]

    operations = [
        migrations.AddField("postulacion", "referencia", models.UUIDField(null=True, unique=True, editable=False)),
        migrations.RunPython(referencias_existentes, migrations.RunPython.noop),
        migrations.AlterField("postulacion", "referencia", models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
        migrations.AddField("postulacion", "estado_ml", models.CharField(
            max_length=20, default="LEGADO", choices=[
                ("LEGADO", "Sin trazabilidad previa"), ("NO_SOLICITADO", "No solicitado"),
                ("COMPLETADO", "Completado"), ("NO_DISPONIBLE", "No disponible"),
            ],
        )),
        migrations.AlterField("cliente", "correo", models.EmailField(max_length=254, null=True, blank=True)),
        migrations.AlterField("cliente", "telefono", models.CharField(max_length=25, null=True, blank=True)),
        migrations.AlterField("prediccion", "version_modelo", models.CharField(max_length=120)),
    ]
