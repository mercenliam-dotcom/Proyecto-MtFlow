from django.db import migrations


class Migration(migrations.Migration):
    """Une la rama de avisos (vista_en) con la de ML v3 (OOD); no cambia tablas."""
    dependencies = [("web", "0016_postulacion_vista_en"), ("web", "0016_prediccion_ood")]
    operations = []
