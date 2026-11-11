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
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from apps.cuentas.models import Rol
from apps.cuentas.permisos import rol_requerido
from web.models import TrabajoPortafolio, Postulacion
from .agenda import profesional
from .imagenes import validar_imagen, TIPOS_ACEPTADOS_HTML
from .operaciones_agenda import bloquear_profesional


MAX_FOTOS_POR_ENVIO = 10


class VariasImagenesInput(forms.FileInput):
    allow_multiple_selected = True


class VariasImagenesField(forms.FileField):
    """Acepta uno o varios archivos y devuelve siempre una lista."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", VariasImagenesInput(attrs={"accept": TIPOS_ACEPTADOS_HTML, "multiple": True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        unico = super().clean
        if isinstance(data, (list, tuple)):
            archivos = [unico(d, initial) for d in data if d]
            if self.required and not archivos:
                raise ValidationError(self.error_messages["required"], code="required")
            return archivos
        archivo = unico(data, initial)
        return [archivo] if archivo else []


class PortafolioForm(forms.ModelForm):
    imagen = VariasImagenesField(required=False, label="Fotografías JPG / PNG (máximo 10 MB cada una)")
    version = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = TrabajoPortafolio
        fields = ["titulo", "tipo", "estilo", "postulacion", "visible", "en_carrusel", "autorizacion_publicacion"]
        labels = {"postulacion": "Solicitud relacionada (opcional)", "visible": "Publicar en el portafolio", "en_carrusel": "Mostrar también en el carrusel", "autorizacion_publicacion": "Tengo autorización para publicar esta fotografía"}

    def __init__(self, *args, artista, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.tatuadora = artista
        # Trabajos terminados o con al menos una sesión realizada (aunque no se haya cerrado el trabajo).
        from django.db.models import Q
        relacionables = Postulacion.objects.filter(Q(estado="REALIZADA") | Q(vinculos_sesiones__bloque__estado="REALIZADA"), tatuadora=artista).select_related("contacto").distinct().order_by("-realizada_en", "-creada_en")
        if self.instance.postulacion_id:
            relacionables = (relacionables | Postulacion.objects.filter(pk=self.instance.postulacion_id)).distinct()
        self.fields["postulacion"].queryset = relacionables
        self.fields["postulacion"].label_from_instance = lambda p: f"{p.contacto} · {(p.zona_cuerpo or '').capitalize()} · " + (f"terminado el {p.realizada_en:%d/%m/%Y}" if p.realizada_en else "sesión realizada") + f" · {p.codigo}"
        self.fields["postulacion"].help_text = ("Aparecen los trabajos con al menos una sesión realizada." if relacionables.exists()
            else "Aún no tienes trabajos con sesiones realizadas. Aparecerán aquí cuando marques una sesión como realizada.")
        self.fields["estilo"].label_from_instance = lambda e: e.nombre
        self.fields["imagen"].required = not self.instance.pk
        if self.instance.pk:
            # Al editar se reemplaza una sola fotografía.
            self.fields["imagen"].label = "Reemplazar fotografía (JPG / PNG, máximo 10 MB)"
            self.fields["imagen"].widget.attrs.pop("multiple", None)
            self.fields["version"].required = True
            self.initial["version"] = self.instance.actualizada_en.isoformat()

    def clean_imagen(self):
        archivos = self.cleaned_data.get("imagen") or []
        limite = 1 if self.instance.pk else MAX_FOTOS_POR_ENVIO
        if len(archivos) > limite:
            raise ValidationError(f"Puedes subir hasta {limite} fotografía{'s' if limite > 1 else ''} a la vez.")
        validadas, errores = [], []
        for archivo in archivos:
            try:
                validadas.append(validar_imagen(archivo).archivo)
            except ValidationError as exc:
                errores.append(f"{archivo.name}: {' '.join(exc.messages)}")
        if errores:
            raise ValidationError(errores)
        return validadas


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
            rutas = []
            try:
                for archivo in form.cleaned_data.get("imagen") or []:
                    rutas.append(storage.save(f"portafolio/{uuid.uuid4().hex}/{archivo.name}", archivo))
                with transaction.atomic(durable=True):
                    bloquear_profesional(request.user)
                    if trabajo.pk:
                        anterior = TrabajoPortafolio.objects.select_for_update().get(pk=trabajo.pk)
                        if form.cleaned_data["version"] != anterior.actualizada_en.isoformat():
                            raise ValidationError("La fotografía cambió en otra ventana. Recarga antes de guardar.")
                    if trabajo.pk or len(rutas) <= 1:
                        if rutas:
                            trabajo.url = rutas[0]
                        trabajo.full_clean()
                        trabajo.save()
                    else:
                        # Varias a la vez: una fotografía independiente por archivo, con los mismos datos.
                        total = len(rutas)
                        for numero, ruta in enumerate(rutas, start=1):
                            nueva = TrabajoPortafolio(
                                tatuadora=artista, publicado_en=trabajo.publicado_en, tipo=trabajo.tipo, estilo=trabajo.estilo,
                                postulacion=trabajo.postulacion, visible=trabajo.visible, en_carrusel=trabajo.en_carrusel,
                                autorizacion_publicacion=trabajo.autorizacion_publicacion,
                                titulo=f"{trabajo.titulo} ({numero}/{total})"[:120], url=ruta)
                            nueva.full_clean()
                            nueva.save()
            except (ValidationError, DatabaseError, OSError) as exc:
                for ruta in rutas:
                    storage.delete(ruta)
                form.add_error(None, " ".join(exc.messages) if isinstance(exc, ValidationError) else "No se pudo guardar. Vuelve a seleccionar la imagen e inténtalo de nuevo.")
                status = 409
            else:
                cantidad = len(form.cleaned_data.get("imagen") or [])
                messages.success(request, f"Se agregaron {cantidad} fotografías al portafolio." if cantidad > 1 and not referencia else "Portafolio actualizado.")
                return redirect("nucleo:portafolio")
    return render(request, "flujo/portafolio_form.html", {"form": form, "titulo": "Editar fotografía" if referencia else "Agregar fotografía", "portafolio": True}, status=status)


@transaction.non_atomic_requests
@rol_requerido(Rol.ADMIN)
@require_POST
def eliminar(request, referencia):
    """Quita la fotografía del portafolio (y de la página pública) y borra su archivo."""
    artista = profesional(request)
    trabajo = get_object_or_404(TrabajoPortafolio, referencia=referencia, tatuadora=artista)
    if request.POST.get("confirmar") != "si":
        messages.error(request, "Confirma que quieres quitar la fotografía.")
        return redirect("nucleo:portafolio_editar", referencia=referencia)
    ruta = trabajo.url
    try:
        with transaction.atomic(durable=True):
            bloquear_profesional(request.user)
            TrabajoPortafolio.objects.filter(pk=trabajo.pk, tatuadora=artista).delete()
    except DatabaseError:
        messages.error(request, "No se pudo quitar la fotografía. Inténtalo de nuevo.")
        return redirect("nucleo:portafolio_editar", referencia=referencia)
    raiz = Path(settings.MEDIA_ROOT).resolve()
    archivo = (raiz / ruta).resolve()
    if ruta.startswith("portafolio/") and raiz in archivo.parents and not TrabajoPortafolio.objects.filter(url=ruta).exists():
        try:
            archivo.unlink(missing_ok=True)
        except OSError:
            pass  # el registro ya no existe; un archivo huérfano no se publica
    messages.success(request, "Fotografía quitada del portafolio.")
    return redirect("nucleo:portafolio")


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
