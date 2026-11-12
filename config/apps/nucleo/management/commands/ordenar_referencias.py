"""Mueve las imágenes de referencia antiguas a la carpeta ordenada por tatuadora.

    python manage.py ordenar_referencias --simular   # solo muestra lo que haría
    python manage.py ordenar_referencias             # mueve y actualiza la base

Antes:   media_privado/postulaciones/<uuid>/<uuid>/<archivo>
Después: media_privado/referencias/<tatuadora>/MT-XXXXXXXX_<cliente>_<fecha>.<ext>

Es seguro repetirlo: lo que ya está en referencias/ no se toca. Si un archivo no
existe en disco, se informa y se deja su registro como estaba.
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from web.almacen_referencias import CARPETA, ruta_referencia
from web.models import Imagen


class Command(BaseCommand):
    help = "Ordena las imágenes de referencia en media_privado/referencias/<tatuadora>/."

    def add_arguments(self, parser):
        parser.add_argument("--simular", action="store_true", help="No mueve nada; solo lista los cambios.")

    def handle(self, *args, simular=False, **opciones):
        raiz = Path(settings.MEDIA_ROOT).resolve()
        pendientes = (Imagen.objects.exclude(url__startswith=CARPETA + "/")
                      .select_related("postulacion__tatuadora__usuario", "postulacion__contacto", "postulacion__cliente")
                      .order_by("pk"))
        movidas = faltan = 0
        carpetas_viejas = set()
        for imagen in pendientes:
            origen = (raiz / imagen.url).resolve()
            if raiz not in origen.parents or not origen.is_file():
                faltan += 1
                self.stdout.write(self.style.WARNING(f"  · No está en disco, se omite: {imagen.url}"))
                continue
            p = imagen.postulacion
            contacto = getattr(p, "contacto", None)
            nombre = f"{contacto.nombres} {contacto.primer_apellido}" if contacto else f"{p.cliente.nombres} {p.cliente.primer_apellido}"
            fecha = timezone.localtime(p.creada_en).date()
            nueva = ruta_referencia(p.tatuadora, p.referencia, nombre, origen.name, fecha)
            if imagen.orden > 1:  # imágenes adicionales de la misma solicitud
                base, ext = os.path.splitext(nueva)
                nueva = f"{base}_{imagen.orden}{ext}"
            destino = raiz / nueva
            n = 2
            while destino.exists() or Imagen.objects.filter(url=destino.relative_to(raiz).as_posix()).exists():
                base, ext = os.path.splitext(nueva)
                destino = raiz / f"{base}-{n}{ext}"
                n += 1
            relativa = destino.relative_to(raiz).as_posix()
            self.stdout.write(f"  {imagen.url}  →  {relativa}")
            if simular:
                movidas += 1
                continue
            destino.parent.mkdir(parents=True, exist_ok=True)
            os.replace(origen, destino)
            try:
                with transaction.atomic():
                    Imagen.objects.filter(pk=imagen.pk).update(url=relativa)
            except Exception:
                os.replace(destino, origen)  # deja todo como estaba
                raise
            carpetas_viejas.add(origen.parent)
            movidas += 1
        # Limpia las carpetas antiguas que quedaron vacías.
        for carpeta in sorted(carpetas_viejas, key=lambda c: len(c.parts), reverse=True):
            while carpeta != raiz and raiz in carpeta.parents:
                try:
                    carpeta.rmdir()
                except OSError:
                    break
                carpeta = carpeta.parent
        verbo = "Se moverían" if simular else "Movidas"
        self.stdout.write(self.style.SUCCESS(f"{verbo}: {movidas} imagen(es). Sin archivo en disco: {faltan}. Carpeta: {raiz / CARPETA}"))
