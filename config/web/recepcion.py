"""Recepción atómica de propuestas e imágenes privadas."""
import logging
from dataclasses import dataclass
from decimal import Decimal
from time import perf_counter

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import IntegrityError, transaction

from apps.clasificacion.catalogo import ESTILOS, recomendar
from apps.clasificacion.cliente_ml import ServicioMLNoDisponible
from .models import Cliente, ContactoSolicitud, ConfianzaEstilo, Estilo, Imagen, Postulacion, Prediccion, Tatuadora
from .almacen_referencias import ruta_referencia
from .precios import estimar

log = logging.getLogger("mtflow.seguridad")


class TatuadoraNoDisponible(Exception):
    """La profesional dejó de estar habilitada durante el envío."""


class EnvioAjeno(Exception):
    """El token ya fue utilizado desde otra cuenta o sin sesión."""


def misma_cuenta(postulacion, cuenta_cliente):
    if postulacion.cuenta_cliente_id != getattr(cuenta_cliente, "pk", None):
        raise EnvioAjeno


@dataclass
class Recepcion:
    postulacion: Postulacion
    estimacion: dict | None = None
    resultado_ml: object = None
    repetida: bool = False


def recibir(datos, validada, referencia, clasificador, cuenta_cliente=None):
    anterior = Postulacion.objects.filter(referencia=referencia).first()
    if anterior:
        misma_cuenta(anterior, cuenta_cliente)
        return Recepcion(anterior, repetida=True)

    # La elección del cliente nunca se sustituye por otra profesional.
    tatuadora = Tatuadora.objects.filter(
        pk=datos["tatuadora"].pk, activa=True, usuario__is_active=True, usuario__es_tatuadora=True,
    ).first()
    if tatuadora is None:
        raise TatuadoraNoDisponible

    alto, ancho = datos["alto_cm"], datos["ancho_cm"]
    area = alto * ancho
    tamano = "pequeno" if area <= 25 else "mediano" if area <= 150 else "grande" if area <= 625 else "especial"
    estimacion = estimar({**datos, "tamano": tamano})
    validada.archivo.seek(0)
    contenido = validada.archivo.read()
    resultado = None
    tiempo_ms = None
    inicio = perf_counter()
    try:
        resultado = clasificador(
            contenido, validada.archivo.name,
            "image/jpeg" if validada.formato == "JPEG" else "image/png",
        )
    except ServicioMLNoDisponible:
        estado_ml = Postulacion.EstadoML.NO_DISPONIBLE
    else:
        estado_ml = Postulacion.EstadoML.COMPLETADO
        # Tiempo de ida y vuelta Django→ML, no tiempo puro del modelo.
        tiempo_ms = max(0, round((perf_counter() - inicio) * 1000))

    storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    # referencias/<tatuadora>/MT-XXXXXXXX_<cliente>_<fecha>.<ext> (ver almacen_referencias).
    ruta = ruta_referencia(tatuadora, referencia, f"{datos['nombre']} {datos.get('primer_apellido', '')}", validada.archivo.name)
    # Si el nombre ya existe, storage.save elige otro; solo se limpia lo que
    # escribió este intento (nunca un archivo previo con el nombre pedido).
    ocupada = storage.exists(ruta)
    try:
        validada.archivo.seek(0)
        ruta = storage.save(ruta, validada.archivo)
        ocupada = False
        # Esta transacción es dueña del commit. La vista desactiva ATOMIC_REQUESTS
        # para poder borrar el archivo también si el commit falla.
        with transaction.atomic(durable=True):
            tatuadora = Tatuadora.objects.select_for_update().filter(
                pk=tatuadora.pk, activa=True, usuario__is_active=True, usuario__es_tatuadora=True,
            ).first()
            if tatuadora is None:
                raise TatuadoraNoDisponible
            if cuenta_cliente is not None:
                perfil = getattr(cuenta_cliente, "perfil_cliente", None)
                cliente, _ = Cliente.objects.get_or_create(usuario=cuenta_cliente, defaults={
                    "nombres": cuenta_cliente.nombre, "primer_apellido": cuenta_cliente.apellido,
                    "segundo_apellido": getattr(perfil, "segundo_apellido", ""),
                    "correo": cuenta_cliente.email, "telefono": getattr(perfil, "telefono", ""),
                })
            else:
                cliente = Cliente.objects.create(nombres=datos["nombre"], primer_apellido=datos.get("primer_apellido", ""),
                    segundo_apellido=datos.get("segundo_apellido", ""), correo=datos["email"], telefono=datos["telefono"])
            postulacion = Postulacion.objects.create(
                cliente=cliente,
                referencia=referencia, tatuadora=tatuadora,
                zona_cuerpo=datos["zona"], alto_cm=alto, ancho_cm=ancho,
                descripcion=datos["idea"], color=datos["color"], nivel_detalle=datos["detalle"], cobertura=datos["cobertura"],
                estado="RECIBIDA", estado_ml=estado_ml,
                precio_sugerido=estimacion.get("minimo"),
                presupuesto_estimado=datos.get("presupuesto"), fecha_propuesta=datos.get("fecha_propuesta"), hora_propuesta=datos.get("hora_propuesta"),
                alerta_ml=recomendar(resultado.estilo_sugerido, resultado.confianza_maxima,
                                     resultado.motivo_abstencion).alerta_ml if resultado else None,
            )
            contacto = ContactoSolicitud(postulacion=postulacion, nombres=datos["nombre"], correo=datos["email"], telefono=datos["telefono"], apellidos=datos.get("primer_apellido", ""), segundo_apellido=datos.get("segundo_apellido", ""), canal_preferido=datos.get("canal_preferido") or "correo", usuario_social=datos.get("usuario_social", ""))
            contacto.full_clean()
            contacto.save()
            postulacion.full_clean()
            imagen = Imagen.objects.create(
                postulacion=postulacion, url=ruta, orden=1, es_principal=True,
                formato=validada.formato, ancho_px=validada.ancho_px, alto_px=validada.alto_px,
                tamano_bytes=len(contenido), nitidez=validada.nitidez,
            )
            if resultado:
                estilos = {}
                for codigo in set(resultado.confianzas) | {resultado.estilo_sugerido}:
                    estilos[codigo], _ = Estilo.objects.get_or_create(
                        codigo=codigo, defaults={"nombre": ESTILOS[codigo], "es_catalogo": codigo != "E-99"},
                    )
                prediccion = Prediccion.objects.create(
                    imagen=imagen, version_modelo=resultado.version_modelo,
                    estilo_sugerido=estilos[resultado.estilo_sugerido],
                    confianza_maxima=Decimal(str(resultado.confianza_maxima)), tiempo_inferencia_ms=tiempo_ms,
                    umbral_confianza=Decimal(str(resultado.umbral_confianza)),
                    ood=resultado.ood,
                    motivo_abstencion=resultado.motivo_abstencion or "",
                )
                ConfianzaEstilo.objects.bulk_create([
                    ConfianzaEstilo(prediccion=prediccion, estilo=estilos[codigo], confianza=Decimal(str(confianza)))
                    for codigo, confianza in resultado.confianzas.items()
                ])
        return Recepcion(postulacion, estimacion, resultado)
    except Exception:
        if ruta and not ocupada:
            try:
                storage.delete(ruta)
            except OSError:
                log.error("No se pudo limpiar un archivo de recepción fallida; revisar almacenamiento privado")
        raise


def recibir_una_vez(datos, validada, referencia, clasificador, cuenta_cliente=None):
    try:
        return recibir(datos, validada, referencia, clasificador, cuenta_cliente=cuenta_cliente)
    except IntegrityError:
        # Dos POST simultáneos con el mismo token: la restricción única decide.
        anterior = Postulacion.objects.filter(referencia=referencia).first()
        if anterior:
            misma_cuenta(anterior, cuenta_cliente)
            return Recepcion(anterior, repetida=True)
        raise
