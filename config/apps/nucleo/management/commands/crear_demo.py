"""Datos de demostración: solicitudes repartidas entre dos tatuadoras, un cliente con
cuenta y visitantes sin cuenta. Usa los mismos servicios que la aplicación (recepción,
gestión, agenda y cobros), por lo que respeta todas sus reglas.

    python manage.py crear_demo                       # 50 solicitudes
    python manage.py crear_demo --sin-ml              # sin llamar al servicio de ML
    python manage.py crear_demo --tatuadoras ana,bea --cliente clientedemo
    python manage.py crear_demo --solo-borrar         # quita lo creado por este comando

Las solicitudes de demostración se reconocen por el dominio de correo @demo.mtflow.cl.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
import random

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

DOMINIO = "@demo.mtflow.cl"
CARPETA = Path(settings.BASE_DIR) / "demo" / "referencias"

# imagen -> (color, idea que acompaña la solicitud)
IMAGENES = {
    "pagoda_roja_color.jpg": ("color", "Pagoda japonesa con cerezos rojos y una luna detrás, estilo ilustrado."),
    "rosa_negro_grises.jpg": ("negro", "Rosa realista en negro y grises con hojas y filigranas finas."),
    "reloj_azul_dorado.jpg": ("color", "Reloj antiguo con números romanos rodeado de olas azules y detalles dorados."),
    "reloj_engranajes_fuego.jpg": ("color", "Reloj con engranajes y llamas naranjas, mucho movimiento."),
    "reloj_cobre_turquesa.jpg": ("color", "Reloj de cobre con engranajes y remolinos turquesa."),
    "reloj_ola_roja.jpg": ("color", "Reloj envuelto en una ola turquesa con salpicaduras rojas."),
    "pagoda_luna_tinta.jpg": ("negro", "Pagoda bajo una luna creciente, en tinta negra con toques rosados."),
    "pagoda_arco_tinta.jpg": ("negro", "Torre oriental con arco y árboles secos, estilo tinta china."),
    "pagoda_nubes_tinta.jpg": ("negro", "Templo entre nubes con puente, en grises suaves."),
    "pagoda_escalera_tinta.jpg": ("negro", "Pagoda con escalera y árboles nevados, trazo fino."),
    "pagoda_cascada_color.jpg": ("color", "Templo sobre rocas con cascada y árboles de otoño."),
    "pagoda_cerezos_color.jpg": ("color", "Pagoda negra con cerezos, cascada y luna, colores pastel."),
}
NOMBRES = ["Camila", "Javiera", "Fernanda", "Constanza", "Catalina", "Valentina", "Antonia", "Martina", "Isidora", "Josefa",
           "Ignacio", "Benjamín", "Matías", "Tomás", "Diego", "Joaquín", "Vicente", "Agustín", "Florencia", "Trinidad"]
APELLIDOS = ["González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Martínez", "Sepúlveda",
             "Morales", "Rodríguez", "López", "Fuentes", "Araya", "Torres", "Espinoza", "Valenzuela", "Castillo", "Reyes"]
ZONAS = ["brazo", "antebrazo", "pierna", "espalda", "pecho"]
CANALES = ["correo", "whatsapp", "instagram"]
# Reparto por cada 25 solicitudes de una tatuadora
PLAN = (["RECIBIDA"] * 7 + ["EN_REVISION"] * 3 + ["ACEPTADA"] * 2 + ["POR_AGENDAR"] * 2
        + ["RESERVADA"] * 4 + ["REALIZADA"] * 5 + ["RECHAZADA"] * 2)
ANTIGUEDAD = {"RECIBIDA": (0, 6), "EN_REVISION": (3, 10), "ACEPTADA": (6, 15), "POR_AGENDAR": (6, 15),
              "RESERVADA": (8, 20), "REALIZADA": (6, 55), "RECHAZADA": (2, 40)}


class Command(BaseCommand):
    help = "Crea solicitudes de demostración repartidas entre dos tatuadoras, un cliente con cuenta y visitantes."

    def add_arguments(self, parser):
        parser.add_argument("--cantidad", type=int, default=50)
        parser.add_argument("--tatuadoras", help="Nombres de usuario separados por coma (por defecto, las dos primeras activas).")
        parser.add_argument("--cliente", default="clientedemo", help="Cuenta de cliente; se crea si no existe.")
        parser.add_argument("--sin-ml", action="store_true", help="No llama al servicio de clasificación.")
        parser.add_argument("--solo-borrar", action="store_true", help="Borra las solicitudes de demostración y termina.")
        parser.add_argument("--semilla", type=int, default=2026)

    # ------------------------------------------------------------------ util
    def handle(self, *args, **o):
        if not CARPETA.is_dir() or not any(CARPETA.glob("*.jpg")):
            raise CommandError(f"No encuentro las imágenes de demostración en {CARPETA}.")
        borradas = self.borrar()
        if borradas:
            self.stdout.write(f"Se borraron {borradas} solicitudes de demostración anteriores.")
        if o["solo_borrar"]:
            return
        self.rnd = random.Random(o["semilla"])
        plan = PLAN[:]
        random.Random(o["semilla"]).shuffle(plan)
        self.hoy = timezone.localdate()
        tatuadoras = self.tatuadoras(o["tatuadoras"])
        cliente = self.cliente(o["cliente"])
        clasificador = self.sin_ml if o["sin_ml"] else None
        imagenes = sorted(CARPETA.glob("*.jpg"))
        self.slots_futuros = {t.pk: self.generar_slots(t, adelante=True) for t in tatuadoras}
        self.slots_pasados = {t.pk: self.generar_slots(t, adelante=False) for t in tatuadoras}
        creadas, fallas = 0, 0
        for i in range(o["cantidad"]):
            tatuadora = tatuadoras[i % len(tatuadoras)]
            estado = plan[(i // len(tatuadoras)) % len(plan)]
            con_cuenta = (i // len(tatuadoras)) % 2 == 0
            imagen = imagenes[i % len(imagenes)]
            self.dias = self.rnd.randint(*ANTIGUEDAD[estado])
            try:
                p = self.recibir(tatuadora, cliente if con_cuenta else None, imagen, clasificador)
                self.avanzar(p, tatuadora, estado)
                self.fechar(p, estado)
                creadas += 1
            except (ValidationError, CommandError) as exc:
                fallas += 1
                mensaje = " ".join(getattr(exc, "messages", [str(exc)]))
                self.stderr.write(f"  Solicitud {i + 1} ({estado}) no se completó: {mensaje}")
        self.stdout.write(self.style.SUCCESS(f"Listo: {creadas} solicitudes de demostración creadas" + (f", {fallas} con problemas." if fallas else ".")))
        for t in tatuadoras:
            self.stdout.write(f"  · {t.usuario.nombre_usuario}: {t.postulacion_set.filter(contacto__correo__endswith=DOMINIO).count()} solicitudes")
        self.stdout.write(f"  · Cliente con cuenta «{cliente.nombre_usuario}»: {cliente.cliente_registro.solicitudes.count() if hasattr(cliente, 'cliente_registro') else 0} solicitudes")
        if not cliente.has_usable_password():
            self.stdout.write(self.style.WARNING(f"La cuenta «{cliente.nombre_usuario}» no tiene contraseña. Para entrar con ella: python manage.py changepassword {cliente.nombre_usuario}"))

    @staticmethod
    def sin_ml(*args, **kwargs):
        from apps.clasificacion.cliente_ml import ServicioMLNoDisponible
        raise ServicioMLNoDisponible("Demostración creada con --sin-ml")

    def tatuadoras(self, nombres):
        from web.models import Tatuadora
        activas = Tatuadora.objects.filter(activa=True, usuario__is_active=True, usuario__es_tatuadora=True).select_related("usuario").order_by("pk")
        if nombres:
            lista = [n.strip().lower() for n in nombres.split(",") if n.strip()]
            elegidas = [t for t in activas if t.usuario.nombre_usuario in lista]
            faltan = set(lista) - {t.usuario.nombre_usuario for t in elegidas}
            if faltan:
                raise CommandError("No encuentro estas tatuadoras activas: " + ", ".join(sorted(faltan)))
            return elegidas
        elegidas = list(activas[:2])
        if not elegidas:
            raise CommandError("No hay cuentas de tatuadora activas.")
        return elegidas

    def cliente(self, nombre):
        from apps.cuentas.models import Usuario, Rol
        usuario = Usuario.objects.filter(nombre_usuario__iexact=nombre).first()
        if usuario:
            if usuario.rol != Rol.USUARIO:
                raise CommandError(f"La cuenta «{nombre}» no es de cliente.")
            return usuario
        usuario = Usuario.objects.create_user(nombre, "cliente.demo" + DOMINIO, None, nombre="Valentina", apellido="Soto", rol=Rol.USUARIO)
        self.stdout.write(f"Cuenta de cliente «{usuario.nombre_usuario}» creada (sin contraseña).")
        return usuario

    def generar_slots(self, tatuadora, adelante):
        """Horarios libres de 2 h, de lunes a sábado, para reservar sin choques."""
        slots = []
        dias = range(2, 40) if adelante else range(-60, -1)
        for dia in dias:
            fecha = self.hoy + timedelta(days=dia)
            if fecha.weekday() != 6:
                slots += [(fecha, time(h), time(h + 2)) for h in (10, 13, 16)]
        return slots

    # ------------------------------------------------------------- recepción
    def recibir(self, tatuadora, cuenta, imagen, clasificador):
        from web.forms import CotizacionForm, token_envio
        from web.recepcion import recibir_una_vez
        from apps.clasificacion.cliente_ml import clasificar
        color, idea = IMAGENES.get(imagen.name, ("negro", "Diseño de la imagen de referencia."))
        nombre, apellido = self.rnd.choice(NOMBRES), self.rnd.choice(APELLIDOS)
        if cuenta:
            nombre, apellido, correo = cuenta.nombre, cuenta.apellido, cuenta.email
        else:
            correo = f"{nombre}.{apellido}.{self.rnd.randint(10, 99)}".lower().translate(str.maketrans("áéíóúñ", "aeioun")) + DOMINIO
        alto = self.rnd.choice([6, 8, 10, 12, 15, 18, 22, 25])
        datos = {
            "envio": token_envio(), "nombre": nombre, "primer_apellido": apellido, "email": correo,
            "telefono": f"+569{self.rnd.randint(10000000, 99999999)}", "canal_preferido": self.rnd.choice(CANALES),
            "tatuadora": str(tatuadora.pk), "zona": self.rnd.choice(ZONAS), "alto_cm": str(alto),
            "ancho_cm": str(max(5, int(alto * self.rnd.choice([0.6, 0.75, 1.0])))),
            "color": color, "detalle": self.rnd.choice(["normal", "alto"]), "idea": idea,
        }
        archivo = SimpleUploadedFile(imagen.name, imagen.read_bytes(), content_type="image/jpeg")
        form = CotizacionForm(datos, {"imagen": archivo})
        if not form.is_valid():
            raise CommandError(form.errors.as_text())
        recepcion = recibir_una_vez(form.cleaned_data, form.validada, form.cleaned_data["envio"], clasificador or clasificar, cuenta_cliente=cuenta)
        return recepcion.postulacion

    # --------------------------------------------------------------- estados
    def avanzar(self, p, tatuadora, estado):
        from apps.nucleo.operaciones_agenda import gestionar, rango_abono
        user = tatuadora.usuario
        ref = p.referencia
        if estado == "RECIBIDA":
            return
        if estado == "EN_REVISION":
            gestionar(user, ref, {"accion": "revisar"})
            return
        if estado == "RECHAZADA":
            gestionar(user, ref, {"accion": "rechazar", "motivo": self.rnd.choice([
                "El diseño no corresponde a mi estilo de trabajo.", "La zona elegida no permite ese nivel de detalle.",
                "No tengo agenda disponible en las fechas que necesita."])})
            return
        area = float(p.alto_cm * p.ancho_cm)
        precio = int(round((40000 + area * 180 * (1.4 if p.color == "color" else 1)) / 5000) * 5000)
        minimo, maximo = rango_abono(precio)
        abono = max(minimo, min(maximo, round(precio * 0.35 / 1000) * 1000))
        gestionar(user, ref, {"accion": "aceptar", "precio_final": precio, "abono_solicitado": abono,
                              "alto_final_cm": p.alto_cm, "ancho_final_cm": p.ancho_cm})
        if estado == "ACEPTADA":
            return
        gestionar(user, ref, {"accion": "abono", "monto_abono": abono, "verificado": True, "motivo": "Transferencia verificada"})
        if estado == "POR_AGENDAR":
            return
        bloque = self.reservar(tatuadora, p, self.slots_futuros[tatuadora.pk])
        if estado == "RESERVADA":
            return
        self.realizar(tatuadora, p, bloque, precio - abono)

    def reservar(self, tatuadora, p, slots):
        from apps.nucleo.operaciones_agenda import guardar_bloque
        from web.disponibilidad import intervalos_trabajo
        from web.models import Postulacion
        while slots:
            fecha, inicio, fin = slots.pop(0)
            if not any(a <= inicio and b >= fin for a, b in intervalos_trabajo(tatuadora, fecha)):
                try:
                    guardar_bloque(tatuadora.usuario, dict(tipo="DISPONIBILIDAD", fecha=fecha, hora_inicio=time(10), hora_fin=time(19), nota="Demostración"))
                except ValidationError:
                    continue
            try:
                return guardar_bloque(tatuadora.usuario, dict(tipo="CITA", fecha=fecha, hora_inicio=inicio, hora_fin=fin, nota="",
                                                              postulacion=Postulacion.objects.get(pk=p.pk)))
            except ValidationError:
                continue
        raise CommandError("No quedaron horarios libres para reservar.")

    def realizar(self, tatuadora, p, bloque, saldo):
        from apps.nucleo.operaciones_agenda import cerrar_bloque
        from apps.nucleo.flujo import aplicar
        from web.models import BloqueHorario, Postulacion
        user = tatuadora.usuario
        # Primera hora libre al menos 3 días después de recibir la solicitud
        pasados = self.slots_pasados[tatuadora.pk]
        minimo = self.hoy - timedelta(days=self.dias - 3)
        indice = next((n for n, slot in enumerate(pasados) if slot[0] >= minimo), None)
        if indice is None:
            raise CommandError("No quedaron horarios pasados libres para la sesión realizada.")
        fecha, inicio, fin = pasados.pop(indice)
        BloqueHorario.objects.filter(pk=bloque.pk).update(fecha=fecha, hora_inicio=inicio, hora_fin=fin)
        bloque.refresh_from_db()
        cerrar_bloque(user, bloque.referencia, "realizar", "", bloque.actualizada_en.isoformat())
        p = Postulacion.objects.get(pk=p.pk)
        if saldo > 0:
            aplicar(user, p.referencia, "cobro", {"version": p.actualizada_en.isoformat(), "tipo": "PAGO", "monto": saldo,
                                                  "verificado": True, "detalle": "Pago del saldo al terminar la sesión"})
            p.refresh_from_db()
        aplicar(user, p.referencia, "terminar", {"version": p.actualizada_en.isoformat(), "confirmado": True})
        self.fecha_sesion = fecha

    def fechar(self, p, estado):
        """Reparte las fechas en los últimos dos meses para que las métricas tengan historia."""
        from web.models import Postulacion, EventoSolicitud, MovimientoCobro
        dias = self.dias
        creada = timezone.make_aware(datetime.combine(self.hoy - timedelta(days=dias), time(self.rnd.randint(9, 21), self.rnd.randint(0, 59))))
        creada = min(creada, timezone.now() - timedelta(minutes=5))
        cambios = {"creada_en": creada}
        # Las recibidas de los últimos 2 días quedan sin leer (campana); el resto, leídas.
        cambios["vista_en"] = None if (estado == "RECIBIDA" and dias <= 2) else creada + timedelta(hours=2)
        if estado == "REALIZADA":
            fin = timezone.make_aware(datetime.combine(self.fecha_sesion, time(19)))
            cambios["realizada_en"] = fin
        Postulacion.objects.filter(pk=p.pk).update(**cambios)
        for n, evento in enumerate(EventoSolicitud.objects.filter(postulacion_id=p.pk).order_by("pk")):
            EventoSolicitud.objects.filter(pk=evento.pk).update(creado_en=creada + timedelta(days=min(n * 2, max(dias - 1, 0)), hours=n))
        MovimientoCobro.objects.filter(postulacion_id=p.pk).update(creado_en=cambios.get("realizada_en", creada))

    # ---------------------------------------------------------------- borrar
    @transaction.atomic
    def borrar(self):
        from web.models import (Postulacion, Cliente, ContactoSolicitud, Sesion, BloqueHorario, Imagen, Prediccion,
                                ConfianzaEstilo, EtiquetaConsolidada, MovimientoCobro, EventoSolicitud, TrabajoPortafolio)
        ids = list(Postulacion.objects.filter(contacto__correo__endswith=DOMINIO).values_list("pk", flat=True))
        if not ids:
            return 0
        clientes = list(Postulacion.objects.filter(pk__in=ids).values_list("cliente_id", flat=True))
        TrabajoPortafolio.objects.filter(postulacion_id__in=ids).update(postulacion=None)
        MovimientoCobro.objects.filter(postulacion_id__in=ids).delete()
        EventoSolicitud.objects.filter(postulacion_id__in=ids).delete()
        bloques = list(Sesion.objects.filter(postulacion_id__in=ids).values_list("bloque_id", flat=True))
        Sesion.objects.filter(postulacion_id__in=ids).delete()
        BloqueHorario.objects.filter(pk__in=bloques).delete()
        BloqueHorario.objects.filter(tipo="DISPONIBILIDAD", nota="Demostración", sesion__isnull=True).delete()
        imagenes = Imagen.objects.filter(postulacion_id__in=ids)
        rutas = list(imagenes.values_list("url", flat=True))
        EtiquetaConsolidada.objects.filter(imagen__in=imagenes).delete()
        ConfianzaEstilo.objects.filter(prediccion__imagen__in=imagenes).delete()
        Prediccion.objects.filter(imagen__in=imagenes).delete()
        imagenes.delete()
        ContactoSolicitud.objects.filter(postulacion_id__in=ids).delete()
        Postulacion.objects.filter(pk__in=ids).delete()
        Cliente.objects.filter(pk__in=clientes, usuario__isnull=True, solicitudes__isnull=True).delete()
        raiz = Path(settings.MEDIA_ROOT).resolve()
        for ruta in rutas:
            archivo = (raiz / ruta).resolve()
            if raiz in archivo.parents and archivo.is_file():
                archivo.unlink()
        return len(ids)
