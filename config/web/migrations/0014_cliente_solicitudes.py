from importlib import import_module
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

guardas = import_module("web.migrations.0010_movimientocobro_and_more")


def vincular_clientes(apps, schema_editor):
    alias = schema_editor.connection.alias
    Cliente = apps.get_model("web", "Cliente")
    Postulacion = apps.get_model("web", "Postulacion")
    Contacto = apps.get_model("web", "ContactoSolicitud")
    Usuario = apps.get_model("cuentas", "Usuario")
    Perfil = apps.get_model("cuentas", "PerfilCliente")
    por_cuenta = {}
    for p in Postulacion.objects.using(alias).order_by("pk").iterator():
        if p.cuenta_cliente_id:
            if p.cuenta_cliente_id not in por_cuenta:
                u = Usuario.objects.using(alias).get(pk=p.cuenta_cliente_id)
                perfil = Perfil.objects.using(alias).filter(usuario_id=u.pk).first()
                c = Cliente.objects.using(alias).create(usuario_id=u.pk, nombres=u.nombre, primer_apellido=u.apellido,
                    segundo_apellido=getattr(perfil,"segundo_apellido",""), correo=u.email, telefono=getattr(perfil,"telefono",""))
                por_cuenta[u.pk] = c.pk
            cliente_id = por_cuenta[p.cuenta_cliente_id]
        elif p.cliente_id:
            # Conservar identidades históricas ya vinculadas; nunca asignarles una cuenta por correo.
            cliente_id = p.cliente_id
        else:
            contacto = Contacto.objects.using(alias).filter(postulacion_id=p.pk).first()
            if contacto is None:
                raise RuntimeError(f"Solicitud {p.pk} sin cliente ni contacto. Revisar antes de migrar; no se inventarán datos.")
            c = Cliente.objects.using(alias).create(nombres=contacto.nombres, primer_apellido=contacto.primer_apellido,
                segundo_apellido=contacto.segundo_apellido, correo=contacto.correo, telefono=contacto.telefono)
            cliente_id = c.pk
        Postulacion.objects.using(alias).filter(pk=p.pk).update(cliente_id=cliente_id)


class Migration(migrations.Migration):
    dependencies = [("web","0013_horariotrabajo"), ("cuentas","0005_remove_usuario_cliente_sin_privilegios_equipo_and_more")]
    operations = [
        migrations.RunPython(guardas.retirar_guardas, guardas.instalar_guardas),
        migrations.RenameField(model_name="cliente", old_name="apellidos", new_name="primer_apellido"),
        migrations.AlterField(model_name="cliente", name="primer_apellido", field=models.CharField(max_length=160, blank=True)),
        migrations.AddField(model_name="cliente", name="segundo_apellido", field=models.CharField(max_length=80, blank=True)),
        migrations.AddField(model_name="cliente", name="usuario", field=models.OneToOneField(to=settings.AUTH_USER_MODEL, related_name="cliente_registro", null=True, blank=True, on_delete=django.db.models.deletion.RESTRICT)),
        migrations.RunPython(vincular_clientes),
        migrations.AlterField(model_name="postulacion", name="cliente", field=models.ForeignKey(to="web.cliente", related_name="solicitudes", on_delete=django.db.models.deletion.RESTRICT)),
        migrations.RemoveField(model_name="postulacion", name="cuenta_cliente"),
        migrations.RunPython(guardas.instalar_guardas, guardas.retirar_guardas),
    ]
