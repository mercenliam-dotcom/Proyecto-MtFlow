from django.db import migrations


def instalar(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        for op in ("INSERT", "UPDATE"):
            schema_editor.execute(f"""CREATE TRIGGER sesion_coherente_{op.lower()}
                BEFORE {op} ON web_sesion
                WHEN NOT EXISTS (SELECT 1 FROM web_bloquehorario b JOIN web_postulacion p
                ON p.id = NEW.postulacion_id WHERE b.id = NEW.bloque_id
                AND b.tipo = 'CITA' AND b.tatuadora_id = p.tatuadora_id)
                BEGIN SELECT RAISE(ABORT, 'sesion_profesional_inconsistente'); END""")
        schema_editor.execute("""CREATE TRIGGER sesion_bloque_coherente BEFORE UPDATE ON web_bloquehorario
            WHEN EXISTS (SELECT 1 FROM web_sesion s JOIN web_postulacion p ON p.id=s.postulacion_id
            WHERE s.bloque_id=NEW.id AND (p.tatuadora_id != NEW.tatuadora_id OR NEW.tipo != 'CITA'))
            BEGIN SELECT RAISE(ABORT, 'sesion_profesional_inconsistente'); END""")
        schema_editor.execute("""CREATE TRIGGER sesion_solicitud_coherente BEFORE UPDATE ON web_postulacion
            WHEN EXISTS (SELECT 1 FROM web_sesion s JOIN web_bloquehorario b ON b.id=s.bloque_id
            WHERE s.postulacion_id=NEW.id AND b.tatuadora_id != NEW.tatuadora_id)
            BEGIN SELECT RAISE(ABORT, 'sesion_profesional_inconsistente'); END""")
    elif schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("""CREATE FUNCTION mtflow_sesion_coherente() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
              IF TG_TABLE_NAME = 'web_sesion' THEN
                IF NOT EXISTS (SELECT 1 FROM web_bloquehorario b JOIN web_postulacion p ON p.id=NEW.postulacion_id
                  WHERE b.id=NEW.bloque_id AND b.tipo='CITA' AND b.tatuadora_id=p.tatuadora_id) THEN
                  RAISE EXCEPTION 'sesion_profesional_inconsistente' USING ERRCODE='23514';
                END IF;
              ELSIF TG_TABLE_NAME = 'web_bloquehorario' THEN
                IF EXISTS (SELECT 1 FROM web_sesion s JOIN web_postulacion p ON p.id=s.postulacion_id
                  WHERE s.bloque_id=NEW.id AND (p.tatuadora_id<>NEW.tatuadora_id OR NEW.tipo<>'CITA')) THEN
                  RAISE EXCEPTION 'sesion_profesional_inconsistente' USING ERRCODE='23514';
                END IF;
              ELSE
                IF EXISTS (SELECT 1 FROM web_sesion s JOIN web_bloquehorario b ON b.id=s.bloque_id
                  WHERE s.postulacion_id=NEW.id AND b.tatuadora_id<>NEW.tatuadora_id) THEN
                  RAISE EXCEPTION 'sesion_profesional_inconsistente' USING ERRCODE='23514';
                END IF;
              END IF;
              RETURN NEW;
            END $$""")
        for tabla, evento in [("web_sesion", "INSERT OR UPDATE"), ("web_bloquehorario", "UPDATE"), ("web_postulacion", "UPDATE")]:
            schema_editor.execute(f"CREATE TRIGGER mtflow_sesion_coherente BEFORE {evento} ON {tabla} FOR EACH ROW EXECUTE FUNCTION mtflow_sesion_coherente()")


def quitar(apps, schema_editor):
    if schema_editor.connection.vendor == "sqlite":
        for nombre in ("sesion_coherente_insert", "sesion_coherente_update", "sesion_bloque_coherente", "sesion_solicitud_coherente"):
            schema_editor.execute(f"DROP TRIGGER IF EXISTS {nombre}")
    elif schema_editor.connection.vendor == "postgresql":
        for tabla in ("web_sesion", "web_bloquehorario", "web_postulacion"):
            schema_editor.execute(f"DROP TRIGGER IF EXISTS mtflow_sesion_coherente ON {tabla}")
        schema_editor.execute("DROP FUNCTION IF EXISTS mtflow_sesion_coherente()")


class Migration(migrations.Migration):
    dependencies = [("web", "0008_bloquehorario_bloque_tipo_estado_valido_and_more")]
    operations = [migrations.RunPython(instalar, quitar)]
