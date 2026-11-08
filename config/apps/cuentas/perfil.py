"""Edición de la cuenta propia, sin campos de permisos ni identificadores ajenos."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods
from web.models import Tatuadora
from .forms_cliente import DatosClienteForm


class ContactoArtistaForm(forms.ModelForm):
    class Meta:
        model = Tatuadora
        fields = ['telefono']
        labels = {'telefono': 'Teléfono de contacto'}


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
    return render(request, 'clientes/perfil.html', {'datos': datos, 'preferencias': preferencias}, status=status)
