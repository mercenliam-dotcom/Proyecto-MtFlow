from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("web", "0003_funcion_tatuadora")]

    operations = [
        migrations.AddField(
            model_name="prediccion", name="umbral_confianza",
            field=models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="prediccion", name="confianza_maxima",
            field=models.DecimalField(max_digits=17, decimal_places=16),
        ),
        migrations.AlterField(
            model_name="confianzaestilo", name="confianza",
            field=models.DecimalField(max_digits=17, decimal_places=16),
        ),
    ]
