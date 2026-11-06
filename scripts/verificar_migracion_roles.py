"""Ensayo de roles con cuentas históricas; solo usa SQLite temporal."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'config'))
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings', DJANGO_DEBUG='1',
                  DJANGO_SECRET_KEY='migration-test-only', ML_SERVICE_API_KEY='unused',
                  DATABASE_URL='', ADMIN_DESARROLLO_HABILITADO='0')
with tempfile.TemporaryDirectory(prefix='mtflow_roles_') as tmp:
    from django.conf import settings
    settings.DATABASES['default']['NAME'] = str(Path(tmp) / 'roles.sqlite3')
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    try:
        target = [('web', '0012_postulacion_cuenta_cliente')]
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        apps = executor.loader.project_state(target).apps
        U = apps.get_model('cuentas', 'Usuario')
        T = apps.get_model('web', 'Tatuadora')
        P = apps.get_model('web', 'Postulacion')
        F = apps.get_model('cuentas', 'PerfilCliente')
        datos = [('artista', 'USUARIO', True, False, 'ADMIN'),
                 ('cliente', 'CLIENTE', False, False, 'USUARIO'),
                 ('usuario', 'USUARIO', False, False, 'USUARIO'),
                 ('superuser', 'USUARIO', False, True, 'ADMIN'),
                 ('administradora', 'ADMIN', True, False, 'ADMIN')]
        antes = []
        for nombre, rol, artista, superuser, esperado in datos:
            u = U.objects.create(nombre_usuario=nombre, email=nombre+'@example.test',
                                 nombre='Prueba', apellido='Histórica', password='!conservar-'+nombre,
                                 rol=rol, es_tatuadora=artista, is_superuser=superuser)
            antes.append((u.pk, u.uuid, u.password, esperado))
        t = T.objects.create(usuario_id=antes[0][0])
        F.objects.create(usuario_id=antes[1][0], telefono='+56912345678')
        p = P.objects.create(tatuadora=t, cuenta_cliente_id=antes[1][0],
                             zona_cuerpo='brazo', alto_cm=5, ancho_cm=4,
                             descripcion='Referencia histórica', estado='RECIBIDA')
        call_command('migrate', verbosity=0, interactive=False)
        from apps.cuentas.models import Usuario, PerfilCliente
        from web.models import Postulacion, Tatuadora
        for pk, uuid, password, esperado in antes:
            u = Usuario.objects.get(pk=pk)
            assert (u.uuid, u.password, u.rol) == (uuid, password, esperado)
        assert Tatuadora.objects.get(pk=t.pk).usuario_id == antes[0][0]
        assert Postulacion.objects.get(pk=p.pk).cuenta_cliente_id == antes[1][0]
        assert PerfilCliente.objects.get(pk=antes[1][0]).telefono == '+56912345678'
        print('OK: cinco casos de roles; IDs, contraseñas, perfil y solicitud conservados.')
    finally:
        connection.close()
