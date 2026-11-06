"""Exporta metadatos de los modelos de negocio a DBML, sin leer filas ni claves."""
import json, os, sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'config'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.apps import apps
from django.db import models

NOMBRES = {
    'web.HorarioTrabajo': 'horario_trabajo',
    'cuentas.Usuario': 'usuario', 'cuentas.PerfilCliente': 'perfil_cliente',
    'web.Cliente': 'cliente', 'web.Tatuadora': 'tatuadora', 'web.BloqueHorario': 'bloque_horario',
    'web.Postulacion': 'postulacion', 'web.ContactoSolicitud': 'contacto_solicitud', 'web.Sesion': 'sesion',
    'web.Imagen': 'imagen', 'web.Estilo': 'estilo', 'web.Prediccion': 'prediccion',
    'web.ConfianzaEstilo': 'confianza_estilo', 'web.EtiquetaConsolidada': 'etiqueta_consolidada',
    'web.TatuadoraEstilo': 'tatuadora_estilo', 'web.TrabajoPortafolio': 'trabajo_portafolio',
    'web.MovimientoCobro': 'movimiento_cobro', 'web.EventoSolicitud': 'evento_solicitud',
}
NOTAS = {
    'horario_trabajo': 'Jornada semanal editable por tatuadora, lunes=0 a domingo=6. Un registro por día. Los bloques DISPONIBILIDAD sustituyen la jornada de una fecha; citas y bloqueos descuentan tiempo libre. La preferencia del cliente no reserva.',
    'usuario': 'Cuenta de acceso. ADMIN: administradora; USUARIO: cliente. Una tatuadora debe ser ADMIN. Password contiene hash, nunca texto plano. is_staff es calculado y no es una columna.',
    'perfil_cliente': 'Preferencias actuales del usuario cliente. Nombre, primer apellido y correo están en usuario; no se duplican aquí.',
    'cliente': 'Entidad heredada de identidad opcional. No equivale a una cuenta de acceso. No se fusiona por coincidencia de correo. Se conserva sin borrar registros históricos.',
    'tatuadora': 'Perfil profesional asociado 1 a 1 a una administradora. El nombre y correo actuales proceden de usuario. Nombre artístico opcional independiente.',
    'bloque_horario': 'Intervalo de una profesional: disponibilidad, cita o bloqueo personal. Se prohíben solapamientos de ocupación y de disponibilidad mediante triggers SQLite o exclusiones PostgreSQL. NO_ASISTIO conserva ocupación histórica.',
    'postulacion': 'Solicitud única: las bandejas son filtros, no tablas duplicadas. cuenta_cliente_id es opcional: envíos sin cuenta permanecen sin propietario de portal. Área, categoría de tamaño, cobro neto, saldo y estado comercial mostrado se calculan; no son columnas.',
    'contacto_solicitud': 'Instantánea del contacto declarado al enviar. Editar el perfil no altera este registro. Una relación por solicitud. Los apellidos históricos se conservaron íntegros en primer_apellido.',
    'sesion': 'Una solicitud admite varias sesiones. Cada fila vincula exactamente una cita de agenda con su solicitud. Bloque y solicitud deben pertenecer a la misma profesional. El estado y horario viven solo en bloque_horario.',
    'imagen': 'Referencia privada. url es la clave/ruta de almacenamiento, no acceso público. Una principal como máximo por solicitud: índice único condicional WHERE es_principal. Imágenes JPG/PNG de hasta 10 MiB validadas por la aplicación.',
    'estilo': 'Catálogo de estilos; E-99 representa abstención o fuera de catálogo, no una clase entrenada adicional.',
    'prediccion': 'Resultado automático conservado. La corrección profesional no sobrescribe la predicción. Confianza y umbral entre 0 y 1. Visible al equipo, no al cliente.',
    'confianza_estilo': 'Puntuación por estilo para una predicción. Cada pareja es única.',
    'etiqueta_consolidada': 'Última revisión humana de una imagen. Confirma o corrige estilo sin iniciar entrenamiento automático. El historial de revisión está en evento_solicitud.',
    'tatuadora_estilo': 'Relación entre profesional y estilo. Se conserva la pareja única; Django utiliza además una PK id.',
    'trabajo_portafolio': 'Fotografía final o del estudio, distinta de la referencia privada. Publicación y carrusel explícitos. Solicitud relacionada opcional y propia. Publicar exige autorización; una foto de tatuaje requiere estilo.',
    'movimiento_cobro': 'Pagos adicionales y devoluciones verificadas fuera del sistema. No repite el abono acumulado de postulacion. Neto = abono verificado + pagos - devoluciones. Sin pasarela de pago.',
    'evento_solicitud': 'Historial interno de decisiones y operaciones, con actor y fecha. No se expone al cliente ni sustituye las columnas monetarias.',
}
CHECKS = {
    'horario_trabajo': [("dia >= 0 AND dia <= 6", 'horario_dia_valido'), ("hora_inicio < hora_fin", 'horario_intervalo_valido')],
    'usuario': [("rol IN ('ADMIN','USUARIO')", 'usuario_rol_valido'), ("rol <> 'USUARIO' OR (NOT es_tatuadora AND NOT is_superuser)", 'usuario_cliente_sin_privilegios'), ("nombre_usuario ~ '^[a-z0-9]{4,30}$'", 'usuario_nombre_usuario_formato')],
    'bloque_horario': [("hora_inicio < hora_fin", 'bloque_intervalo_positivo'), ("(tipo = 'DISPONIBILIDAD' AND estado IN ('DISPONIBLE','CANCELADA')) OR (tipo = 'CITA' AND estado IN ('RESERVADA','REALIZADA','CANCELADA','NO_ASISTIO')) OR (tipo = 'BLOQUEO' AND estado IN ('BLOQUEADO','CANCELADA'))", 'bloque_tipo_estado_valido')],
    'postulacion': [
        ("alto_cm > 0 AND alto_cm <= 999.99 AND ancho_cm > 0 AND ancho_cm <= 999.99", 'solicitud_medidas_validas'),
        ("precio_final IS NULL OR (precio_final > 0 AND precio_final <= 100000000)", 'solicitud_precio_valido'),
        ("monto_abono IS NULL OR (monto_abono >= 0 AND monto_abono <= 100000000)", 'solicitud_abono_valido'),
        ("monto_abono IS NULL OR precio_final IS NULL OR monto_abono <= precio_final", 'abono_no_supera_precio'),
        ("abono_verificado_en IS NULL OR (monto_abono IS NOT NULL AND monto_abono > 0 AND precio_final IS NOT NULL)", 'abono_verificado_coherente'),
        ("color IS NULL OR color IN ('negro','color')", 'solicitud_color_valido'),
        ("nivel_detalle IS NULL OR nivel_detalle IN ('normal','alto')", 'solicitud_detalle_valido'),
        ("estado IN ('RECIBIDA','EN_REVISION','ACEPTADA','RESERVADA','REALIZADA','RECHAZADA')", 'solicitud_estado_valido'),
        ("abono_solicitado IS NULL OR (abono_solicitado > 0 AND abono_solicitado <= 100000000)", 'abono_solicitado_valido'),
        ("abono_solicitado IS NULL OR precio_final IS NULL OR abono_solicitado <= precio_final", 'abono_solicitado_no_supera_total'),
        ("(alto_final_cm IS NULL AND ancho_final_cm IS NULL) OR (alto_final_cm IS NOT NULL AND ancho_final_cm IS NOT NULL AND alto_final_cm > 0 AND ancho_final_cm > 0)", 'medidas_finales_coherentes'),
        ("(fecha_propuesta IS NULL AND hora_propuesta IS NULL) OR (fecha_propuesta IS NOT NULL AND hora_propuesta IS NOT NULL)", 'preferencia_fecha_hora_completa'),
        ("destino_abono IN ('PENDIENTE','REAGENDAR','RETENIDO','DEVOLVER')", 'destino_abono_valido'),
    ],
    'imagen': [("orden > 0 AND ancho_px > 0 AND alto_px > 0 AND tamano_bytes > 0", 'imagen_metadata_positiva')],
    'prediccion': [("confianza_maxima >= 0 AND confianza_maxima <= 1 AND tiempo_inferencia_ms >= 0", 'prediccion_valores_validos'), ("umbral_confianza IS NULL OR (umbral_confianza >= 0 AND umbral_confianza <= 1)", 'prediccion_umbral_valido')],
    'confianza_estilo': [("confianza >= 0 AND confianza <= 1", 'confianza_estilo_valida')],
    'movimiento_cobro': [("monto > 0 AND monto <= 100000000", 'cobro_monto_valido'), ("tipo IN ('PAGO','DEVOLUCION')", 'cobro_tipo_valido')],
}
GRUPOS = {'Acceso_y_profesionales': ['usuario','perfil_cliente','cliente','tatuadora','tatuadora_estilo'], 'Solicitudes_y_agenda':['postulacion','contacto_solicitud','sesion','horario_trabajo','bloque_horario','movimiento_cobro','evento_solicitud'], 'Imagenes_estilos_y_portafolio':['imagen','estilo','prediccion','confianza_estilo','etiqueta_consolidada','trabajo_portafolio']}

def texto(s):
    return "'"+str(s).replace('\\','\\\\').replace("'","\\'").replace('\n',' ') + "'"

def tipo(f):
    if f.is_relation:
        return tipo(f.target_field)
    t=f.get_internal_type()
    if t in ('BigAutoField','BigIntegerField'): return 'bigint'
    if t in ('AutoField','IntegerField','PositiveIntegerField'): return 'integer'
    if t in ('SmallIntegerField','PositiveSmallIntegerField'): return 'smallint'
    if t=='UUIDField': return 'uuid'
    if t=='BooleanField': return 'boolean'
    if t=='DecimalField': return f'numeric({f.max_digits},{f.decimal_places})'
    if t=='FloatField': return '"double precision"'
    if t=='DateTimeField': return 'timestamptz'
    if t=='DateField': return 'date'
    if t=='TimeField': return 'time'
    if t=='TextField': return 'text'
    if t in ('CharField','EmailField'): return f'varchar({f.max_length})'
    raise ValueError(t)

def generar(fisico=False):
    modelos={label:apps.get_model(label) for label in NOMBRES}
    nombres={label:m._meta.db_table if fisico else NOMBRES[label] for label,m in modelos.items()}
    lineas=["// MTFlow: DER vigente. Referencia: DER del informe, imagen14.jpg.","// Esquema de negocio, no script de migración. Tipos PostgreSQL para el destino final; hoy se ejecuta en SQLite.","// Omite tablas técnicas Django (sesiones web, permisos, grupos, migraciones y admin log).", "// Las reglas de on_delete se ejecutan mediante Django; triggers/exclusiones no se exportan como SQL aquí.","Project MTFlow {", "  database_type: 'PostgreSQL'", "  Note: 'Dos roles: ADMIN (administradora) y USUARIO (cliente). Campos, PK, nulabilidad y FK derivados de los modelos vigentes. No incluye datos personales.'", "}",""]
    refs=[]
    manifiesto=[]
    for label,m in modelos.items():
        n=NOMBRES[label]
        nombre=nombres[label]
        lineas += [f'Table {nombre} {{', '  Note: '+texto(NOTAS[n]+f' Tabla física Django: {m._meta.db_table}.')]
        for f in m._meta.local_fields:
            opciones=['not null' if not f.null else 'null']
            if f.primary_key: opciones.insert(0,'pk')
            if isinstance(f, (models.AutoField,models.BigAutoField)): opciones.append('increment')
            if f.unique and not f.primary_key: opciones.append('unique')
            notas=[]
            if f.choices: notas.append('Valores de aplicación: '+', '.join(str(v) for v,_ in f.choices))
            if f.has_default():
                notas.append('Valor inicial en Django: '+ ('generado por aplicación' if callable(f.default) else str(f.default)))
            if getattr(f,'auto_now',False) or getattr(f,'auto_now_add',False): notas.append('Fecha asignada por Django')
            if f.is_relation:
                destino=f.remote_field.model._meta.label
                assert destino in nombres, (label,f.name,destino)
                notas.append('Al eliminar referente: '+f.remote_field.on_delete.__name__+' en Django')
                if f.one_to_one:
                    refs.append(f'Ref: {nombres[destino]}.{f.target_field.column} - {nombre}.{f.column}')
                else:
                    refs.append(f'Ref: {nombre}.{f.column} > {nombres[destino]}.{f.target_field.column}')
            if notas: opciones.append('note: '+texto('; '.join(notas)))
            lineas.append(f'  {f.column} {tipo(f)} [{", ".join(opciones)}]')
        indices=[]
        for campos in m._meta.unique_together:
            indices.append('    ('+', '.join(m._meta.get_field(c).column for c in campos)+') [unique]')
        for indice in m._meta.indexes:
            indices.append('    ('+', '.join(m._meta.get_field(c).column for c in indice.fields)+') [name: '+texto(indice.name)+']')
        if indices: lineas+=['  indexes {',*indices,'  }']
        checks=CHECKS.get(n,[])
        reales={c.name for c in m._meta.constraints if isinstance(c,models.CheckConstraint)}
        assert reales=={nombre for _,nombre in checks}, (n,reales)
        if checks: lineas+=['  checks {',*[f'    `{sql}` [name: {texto(nom)}]' for sql,nom in checks],'  }']
        lineas+=['}','']
        manifiesto.append({'modelo':label,'tabla_der':n,'tabla_fisica':m._meta.db_table,'columnas':[f.column for f in m._meta.local_fields],'fk':[f.column for f in m._meta.local_fields if f.is_relation]})
    lineas+=refs+['']
    for grupo,tablas in GRUPOS.items():
        equivalencias={NOMBRES[label]:nombre for label,nombre in nombres.items()}
        lineas += [f'TableGroup {grupo} {{', *['  '+equivalencias[t] for t in tablas], '}','']
    return '\n'.join(lineas),manifiesto,len(refs)

salida=repo/'docs/der'
salida.mkdir(parents=True,exist_ok=True)
for fisico,archivo in [(False,'MTFlow_DER_actualizado.dbml'),(True,'MTFlow_esquema_fisico.dbml')]:
    contenido,manifiesto,relaciones=generar(fisico)
    (salida/archivo).write_text(contenido,encoding='utf-8')
(salida/'correspondencia_modelos.json').write_text(json.dumps(manifiesto,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'tablas':len(manifiesto),'columnas':sum(len(m['columnas']) for m in manifiesto),'relaciones':relaciones,'directorio':str(salida)},ensure_ascii=False))
