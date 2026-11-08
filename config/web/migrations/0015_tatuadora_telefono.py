from django.db import migrations, models
import web.validadores


class Migration(migrations.Migration):
    dependencies = [('web', '0014_cliente_solicitudes')]
    operations = [migrations.AddField(model_name='tatuadora', name='telefono', field=models.CharField(blank=True, max_length=25, validators=[web.validadores.telefono_contacto]))]
