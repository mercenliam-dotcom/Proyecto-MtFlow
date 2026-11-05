from django.db import migrations


def instalar(apps, schema_editor):
    tabla = "web_bloquehorario"
    grupos = {"ocupacion": "estado IN ('RESERVADA','REALIZADA','BLOQUEADO')", "disponibilidad": "estado = 'DISPONIBLE' AND tipo = 'DISPONIBILIDAD'"}
    # No eliminar ni resolver silenciosamente conflictos de datos anteriores.
    Bloque = apps.get_model("web", "BloqueHorario")
    qs = Bloque.objects.using(schema_editor.connection.alias)
    for b in qs.all().iterator():
        otros = qs.filter(tatuadora_id=b.tatuadora_id, fecha=b.fecha, hora_inicio__lt=b.hora_fin, hora_fin__gt=b.hora_inicio).exclude(pk=b.pk)
        if b.estado in ("RESERVADA", "REALIZADA", "BLOQUEADO"):
            conflicto = otros.filter(estado__in=("RESERVADA", "REALIZADA", "BLOQUEADO")).exists()
        elif b.estado == "DISPONIBLE" and b.tipo == "DISPONIBILIDAD":
            conflicto = otros.filter(estado="DISPONIBLE", tipo="DISPONIBILIDAD").exists()
        else:
            conflicto = False
        if conflicto:
            raise RuntimeError("La agenda anterior contiene horarios superpuestos. Revisarlos antes de aplicar esta migración.")
    if schema_editor.connection.vendor == "sqlite":
        for nombre, condicion in grupos.items():
            nueva = condicion.replace("estado", "NEW.estado").replace("tipo", "NEW.tipo")
            for operacion in ("INSERT", "UPDATE"):
                schema_editor.execute(f"""CREATE TRIGGER agenda_{nombre}_{operacion.lower()}
                    BEFORE {operacion} ON {tabla}
                    WHEN ({nueva}) AND EXISTS (SELECT 1 FROM {tabla}
                    WHERE id != NEW.id AND tatuadora_id = NEW.tatuadora_id AND fecha = NEW.fecha
                    AND hora_inicio < NEW.hora_fin AND hora_fin > NEW.hora_inicio AND ({condicion}))
                    BEGIN SELECT RAISE(ABORT, 'agenda_intervalo_ocupado'); END""")
    elif schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        for nombre, condicion in grupos.items():
            schema_editor.execute(f"""ALTER TABLE {tabla} ADD CONSTRAINT agenda_{nombre}_exclusion
                EXCLUDE USING gist (tatuadora_id WITH =, tsrange(fecha + hora_inicio, fecha + hora_fin, '[)') WITH &&)
                WHERE ({condicion})""")


def quitar(apps, schema_editor):
    for nombre in ("ocupacion", "disponibilidad"):
        if schema_editor.connection.vendor == "sqlite":
            for operacion in ("insert", "update"):
                schema_editor.execute(f"DROP TRIGGER IF EXISTS agenda_{nombre}_{operacion}")
        elif schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(f"ALTER TABLE web_bloquehorario DROP CONSTRAINT IF EXISTS agenda_{nombre}_exclusion")


class Migration(migrations.Migration):
    dependencies = [("web", "0005_eventosolicitud_alter_bloquehorario_options_and_more")]
    operations = [migrations.RunPython(instalar, quitar)]
