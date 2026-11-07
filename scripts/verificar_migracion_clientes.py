"""Ensayo con datos históricos: no abre ni modifica la base operativa."""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'config'))
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',DJANGO_DEBUG='1',DJANGO_SECRET_KEY='migration-test-only',ML_SERVICE_API_KEY='unused',DATABASE_URL='',ADMIN_DESARROLLO_HABILITADO='0')
with tempfile.TemporaryDirectory(prefix='mtflow_clientes_') as tmp:
    from django.conf import settings
    settings.DATABASES['default']['NAME']=str(Path(tmp)/'prueba.sqlite3')
    import django
    django.setup()
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.core.management import call_command
    try:
        destino=[('web','0013_horariotrabajo'),('cuentas','0005_remove_usuario_cliente_sin_privilegios_equipo_and_more')]
        ejecutor=MigrationExecutor(connection)
        ejecutor.migrate(destino)
        apps=ejecutor.loader.project_state(destino).apps
        U=apps.get_model('cuentas','Usuario')
        C,T,P,Contacto,I=[apps.get_model('web',n) for n in ('Cliente','Tatuadora','Postulacion','ContactoSolicitud','Imagen')]
        admin=U.objects.create(nombre_usuario='artista',nombre='Artista',apellido='Prueba',email='artista@example.test',rol='ADMIN',es_tatuadora=True,password='!')
        artista=T.objects.create(usuario=admin)
        u=U.objects.create(nombre_usuario='cliente',nombre='Cliente',apellido='Cuenta',email='igual@example.test',rol='USUARIO',password='!')
        anterior=C.objects.create(nombres='Identidad anterior',apellidos='Apellido compuesto intacto',correo='igual@example.test')
        solicitudes=[]
        for i in range(6):
            p=P.objects.create(tatuadora=artista,cliente=anterior if i in (0,3) else None,
                cuenta_cliente=u if i<3 else None,zona_cuerpo='brazo',alto_cm=5,ancho_cm=4,descripcion='Historia',estado='RECIBIDA')
            Contacto.objects.create(postulacion=p,nombres=f'Contacto {i}',primer_apellido='Primero',segundo_apellido='Segundo',correo='igual@example.test')
            I.objects.create(postulacion=p,url=f'postulaciones/prueba-{i}.jpg',orden=1,es_principal=True,formato='JPEG',ancho_px=300,alto_px=300,tamano_bytes=1000)
            solicitudes.append((p.pk,p.referencia))
        imagenes=list(I.objects.values_list('pk','postulacion_id','url'))
        call_command('migrate',verbosity=0,interactive=False)
        from web.models import Cliente,Postulacion,Imagen
        nuevas=[Postulacion.objects.get(pk=pk) for pk,_ in solicitudes]
        assert len({p.cliente_id for p in nuevas[:3]})==1
        assert all(p.cliente.usuario_id==u.pk for p in nuevas[:3])
        assert all(p.cliente.usuario_id is None for p in nuevas[3:])
        assert nuevas[3].cliente_id==anterior.pk
        assert len({p.cliente_id for p in nuevas[3:]})==3
        assert Cliente.objects.get(pk=anterior.pk).primer_apellido=='Apellido compuesto intacto'
        assert list(Imagen.objects.values_list('pk','postulacion_id','url'))==imagenes
        assert [(p.pk,p.referencia) for p in nuevas]==solicitudes
        assert [p.contacto.nombres for p in nuevas]==[f'Contacto {i}' for i in range(6)]
        assert not connection.cursor().execute('PRAGMA foreign_key_check').fetchall()
        print('OK: tres solicitudes comparten cliente; anónimos separados; cuentas, contactos, imágenes y referencias conservados.')
        if len(sys.argv)>1:
            from apps.cuentas.models import Usuario
            from web.models import Tatuadora
            import json
            otro=Usuario.objects.create_superuser('fixtureartista','fixtureartista@example.test','SoloPrueba2026',nombre='Artista',apellido='Dos',es_tatuadora=True)
            Tatuadora.objects.get_or_create(usuario=otro)
            call_command('loaddata',sys.argv[1],verbosity=0)
            registros=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
            uid=next(r['pk'] for r in registros if r['model']=='cuentas.usuario')
            assert Postulacion.objects.filter(cliente__usuario_id=uid).count()==3
            assert Postulacion.objects.filter(pk__in=[r['pk'] for r in registros if r['model']=='web.postulacion']).count()==20
            print('OK: JSON de 20 solicitudes cargado; tres pertenecen al mismo cliente con cuenta.')
    finally:
        connection.close()
