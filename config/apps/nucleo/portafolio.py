from pathlib import Path
import uuid
from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import transaction, DatabaseError
from django.http import FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.models import TrabajoPortafolio, Postulacion
from .agenda import profesional
from .imagenes import validar_imagen, TIPOS_ACEPTADOS_HTML
from .operaciones_agenda import bloquear_profesional


class PortafolioForm(forms.ModelForm):
    imagen = forms.FileField(required=False, label="Fotografía JPG / PNG (máximo 10 MB)", widget=forms.FileInput(attrs={"accept": TIPOS_ACEPTADOS_HTML}))
    version = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = TrabajoPortafolio
        fields = ["titulo", "tipo", "estilo", "postulacion", "visible", "en_carrusel", "autorizacion_publicacion"]
        labels = {"postulacion": "Solicitud relacionada (opcional)", "visible": "Publicar en el portafolio", "en_carrusel": "Mostrar también en el carrusel", "autorizacion_publicacion": "Tengo autorización para publicar esta fotografía"}

    def __init__(self, *args, artista, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tatuadora = artista
        self.fields["postulacion"].queryset = Postulacion.objects.filter(tatuadora=artista, estado="REALIZADA").select_related("contacto")
        self.fields["postulacion"].label_from_instance = lambda p: f"{p.contacto} · {p.referencia.hex[:8]}"
        self.fields["estilo"].label_from_instance = lambda e: e.nombre
        self.fields["imagen"].required = not self.instance.pk
        if self.instance.pk:
            self.fields["version"].required = True
            self.initial["version"] = self.instance.actualizada_en.isoformat()

    def clean_imagen(self):
        imagen = self.cleaned_data.get("imagen")
        if imagen:
            return validar_imagen(imagen).archivo
        return None


@rol_requerido(Rol.ADMIN)
@never_cache
@require_GET
def lista(request):
    artista = profesional(request)
    return render(request, "flujo/portafolio.html", {"trabajos": TrabajoPortafolio.objects.filter(tatuadora=artista).order_by("-publicado_en", "-pk")})


@transaction.non_atomic_requests
@rol_requerido(Rol.ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def editar(request, referencia=None):
    artista = profesional(request)
    trabajo = get_object_or_404(TrabajoPortafolio, referencia=referencia, tatuadora=artista) if referencia else TrabajoPortafolio(tatuadora=artista, publicado_en=timezone.localdate())
    form = PortafolioForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=trabajo, artista=artista)
    status = 200
    if request.method == "POST":
        status = 400
        if form.is_valid():
            storage = FileSystemStorage(location=settings.MEDIA_ROOT)
            ruta = None
            try:
                archivo = form.cleaned_data.get("imagen")
                if archivo:
                    ruta = storage.save(f"portafolio/{uuid.uuid4().hex}/{archivo.name}", archivo)
                with transaction.atomic(durable=True):
                    bloquear_profesional(request.user)
                    if trabajo.pk:
                        anterior = TrabajoPortafolio.objects.select_for_update().get(pk=trabajo.pk)
                        if form.cleaned_data["version"] != anterior.actualizada_en.isoformat():
                            raise ValidationError("La fotografía cambió en otra ventana. Recarga antes de guardar.")
                    if ruta:
                        trabajo.url = ruta
                    trabajo.full_clean()
                    trabajo.save()
            except (ValidationError, DatabaseError, OSError) as exc:
                if ruta:
                    storage.delete(ruta)
                form.add_error(None, " ".join(exc.messages) if isinstance(exc, ValidationError) else "No se pudo guardar. Vuelve a seleccionar la imagen e inténtalo de nuevo.")
                status = 409
            else:
                messages.success(request, "Portafolio actualizado.")
                return redirect("nucleo:portafolio")
    return render(request, "flujo/formulario.html", {"form": form, "titulo": "Editar fotografía" if referencia else "Agregar fotografía", "portafolio": True}, status=status)


@never_cache
@require_GET
def imagen(request, referencia):
    trabajo = get_object_or_404(TrabajoPortafolio, referencia=referencia)
    publico = trabajo.visible and trabajo.autorizacion_publicacion and trabajo.tatuadora.activa and trabajo.tatuadora.usuario.is_active and trabajo.tatuadora.usuario.es_tatuadora
    propio = request.user.is_authenticated and request.user.pk == trabajo.tatuadora.usuario_id and request.user.es_tatuadora
    if not publico and not propio:
        raise Http404
    raiz = Path(settings.MEDIA_ROOT).resolve()
    ruta = (raiz / trabajo.url).resolve()
    if not trabajo.url.startswith("portafolio/") or raiz not in ruta.parents or not ruta.is_file() or ruta.suffix.lower() not in (".jpg", ".jpeg", ".png"):
        raise Http404
    return FileResponse(ruta.open("rb"), content_type="image/png" if ruta.suffix.lower() == ".png" else "image/jpeg")
