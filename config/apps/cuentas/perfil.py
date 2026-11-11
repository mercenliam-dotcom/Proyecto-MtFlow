"""Edición de la cuenta propia, sin campos de permisos ni identificadores ajenos."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from web.models import Tatuadora, Postulacion, TrabajoPortafolio
from .forms_cliente import DatosClienteForm


class ContactoArtistaForm(forms.ModelForm):
    class Meta:
        model = Tatuadora
        fields = ['telefono']
        labels = {'telefono': 'Teléfono de contacto'}


def resumen_perfil(user):
    """Cifras breves para el encabezado del perfil (solo lectura)."""
    if user.es_tatuadora:
        mias = Postulacion.objects.filter(tatuadora__usuario=user)
        return [
            {"etiqueta": "Por decidir", "valor": mias.filter(estado__in=["RECIBIDA", "EN_REVISION"]).count(), "url": reverse("nucleo:cotizaciones"), "detalle": "Solicitudes nuevas o en revisión"},
            {"etiqueta": "Sesiones agendadas", "valor": mias.filter(estado="RESERVADA").count(), "url": reverse("nucleo:registro") + "?bandeja=agendadas", "detalle": "Por realizar"},
            {"etiqueta": "Trabajos terminados", "valor": mias.filter(estado="REALIZADA").count(), "url": reverse("nucleo:registro") + "?bandeja=terminadas", "detalle": "En total"},
            {"etiqueta": "Fotos publicadas", "valor": TrabajoPortafolio.objects.filter(tatuadora__usuario=user, visible=True, autorizacion_publicacion=True).count(), "url": reverse("nucleo:portafolio"), "detalle": "En tu portafolio"},
        ]
    if user.es_cliente:
        mias = Postulacion.objects.filter(cliente__usuario=user)
        return [
            {"etiqueta": "Solicitudes enviadas", "valor": mias.count(), "url": reverse("clientes:inicio"), "detalle": "Desde tu cuenta"},
            {"etiqueta": "En curso", "valor": mias.exclude(estado__in=["REALIZADA", "RECHAZADA"]).count(), "url": reverse("clientes:inicio"), "detalle": "Esperando respuesta o sesión"},
            {"etiqueta": "Terminadas", "valor": mias.filter(estado="REALIZADA").count(), "url": reverse("clientes:inicio"), "detalle": "Tatuajes realizados"},
        ]
    return []


@login_required
@never_cache
@sensitive_post_parameters('datos-actual')
@require_http_methods(['GET', 'POST'])
def propio(request):
    if request.user.es_cliente:
        return redirect('clientes:perfil')
    artista = get_object_or_404(Tatuadora, usuario=request.user) if request.user.es_tatuadora else None
    post = request.POST if request.method == 'POST' else None
    datos = DatosClienteForm(post, instance=request.user, prefix='datos')
    preferencias = ContactoArtistaForm(post, instance=artista, prefix='contacto') if artista else None
    status = 200
    if request.method == 'POST':
        status = 400
        validos = [datos.is_valid()]
        if preferencias is not None:
            validos.append(preferencias.is_valid())
        if all(validos):
            try:
                with transaction.atomic():
                    datos.instance.save(update_fields=['nombre', 'apellido', 'email'])
                    if preferencias is not None:
                        preferencias.instance.save(update_fields=['telefono'])
            except IntegrityError:
                datos.add_error(None, 'No se guardaron los cambios. Revisa si el correo ya está en uso.')
                status = 409
            else:
                messages.success(request, 'Tu perfil se actualizó.')
                return redirect('cuentas:perfil')
    return render(request, 'clientes/perfil.html', {'datos': datos, 'preferencias': preferencias, 'resumen': resumen_perfil(request.user)}, status=status)
