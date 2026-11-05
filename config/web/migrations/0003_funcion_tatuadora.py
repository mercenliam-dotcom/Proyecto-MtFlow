from django.db import migrations


def conservar_perfiles_habilitados(apps, schema_editor):
    Usuario = apps.get_model("cuentas", "Usuario")
    Tatuadora = apps.get_model("web", "Tatuadora")
    alias = schema_editor.connection.alias
    perfiles = Tatuadora.objects.using(alias).filter(activa=True).values_list("usuario_id", flat=True)
    Usuario.objects.using(alias).filter(pk__in=perfiles).update(es_tatuadora=True)


class Migration(migrations.Migration):
    dependencies = [("web", "0002_consolidar_recepcion"), ("cuentas", "0002_usuario_es_tatuadora")]
    operations = [migrations.RunPython(conservar_perfiles_habilitados, migrations.RunPython.noop)]
