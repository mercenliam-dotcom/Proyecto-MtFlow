from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("cuentas", "0002_usuario_es_tatuadora")]

    operations = [
        migrations.AddField(
            model_name="usuario", name="es_admin_desarrollo",
            field=models.BooleanField(default=False, editable=False),
        ),
    ]
