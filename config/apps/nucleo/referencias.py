"""Galería privada de las imágenes de referencia que recibió cada tatuadora.

Las imágenes viven en media_privado/referencias/<tatuadora>/ y se muestran con
enlaces firmados de corta duración: nunca se publican ni se sirven sin sesión.
"""
import re
from pathlib import Path

from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.almacen_referencias import CARPETA, carpeta_tatuadora
from web.models import Imagen
from .agenda import profesional
from .firmas import url_archivo

POR_PAGINA = 24


def _buscar(imagenes, texto):
    """Busca por nombre o apellido de quien envió, o por el código MT-XXXXXXXX."""
    filtro = Q(postulacion__contacto__nombres__icontains=texto) | Q(postulacion__contacto__primer_apellido__icontains=texto)
    codigo = re.sub(r"^mt-?", "", texto.strip().lower())
    if re.fullmatch(r"[0-9a-f]{4,8}", codigo):
        # La referencia es un UUID; el código corto son sus 8 primeros caracteres.
        filtro |= Q(postulacion__referencia__startswith=codigo)
    return imagenes.filter(filtro)


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def galeria(request):
    artista = profesional(request)
    imagenes = (Imagen.objects.filter(postulacion__tatuadora=artista)
                .select_related("postulacion", "postulacion__contacto")
                .order_by("-cargada_en", "-pk"))
    total = imagenes.count()
    texto = request.GET.get("q", "").strip()[:80]
    if texto:
        imagenes = _buscar(imagenes, texto)
    pagina = Paginator(imagenes, POR_PAGINA).get_page(request.GET.get("pagina"))
    raiz = Path(settings.MEDIA_ROOT).resolve()
    tarjetas = []
    for imagen in pagina:
        ruta = (raiz / imagen.url).resolve()
        disponible = raiz in ruta.parents and ruta.is_file()
        p = imagen.postulacion
        contacto = getattr(p, "contacto", None)
        tarjetas.append({
            "imagen": imagen, "postulacion": p,
            "url": url_archivo(imagen.url) if disponible else None,
            "nombre_archivo": Path(imagen.url).name,
            "cliente": f"{contacto.nombres} {contacto.primer_apellido}".strip() if contacto else "Sin contacto",
        })
    return render(request, "nucleo/referencias.html", {
        "pagina": pagina, "tarjetas": tarjetas, "total": total, "texto": texto,
        "carpeta": f"media_privado/{CARPETA}/{carpeta_tatuadora(artista)}/",
    })
