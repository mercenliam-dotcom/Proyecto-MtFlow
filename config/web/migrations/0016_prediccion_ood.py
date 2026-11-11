from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("web", "0015_tatuadora_telefono")]
    operations = [
        migrations.AddField(model_name="prediccion", name="ood", field=models.JSONField(blank=True, null=True)),
        migrations.AddField(model_name="prediccion", name="motivo_abstencion", field=models.CharField(
            blank=True, default="", max_length=32, choices=[("", "Sin abstención"),
            ("fuera_distribucion", "Fuera de distribución"), ("confianza_insuficiente", "Confianza insuficiente")])),
    ]
