from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0001_initial")]

    operations = [migrations.AddField(
        model_name="usuario", name="es_tatuadora",
        field=models.BooleanField(default=False, verbose_name="Es tatuadora", help_text="Puede recibir propuestas como tatuadora, independientemente de su rol de administración."),
    )]
