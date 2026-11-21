from django.urls import path
from . import clientes, recuperar

app_name = "clientes"
urlpatterns = [
    path("", clientes.inicio, name="inicio"),
    path("registro/", clientes.registro, name="registro"),
    path("perfil/", clientes.perfil, name="perfil"),
    path("recuperar/", recuperar.PedirEnlace.as_view(), name="recuperar"),
    path("recuperar/enviado/", recuperar.EnlaceEnviado.as_view(), name="recuperar_enviado"),
    path("recuperar/<uidb64>/<token>/", recuperar.DefinirContrasena.as_view(), name="recuperar_nueva"),
    path("recuperar/listo/", recuperar.ContrasenaLista.as_view(), name="recuperar_listo"),
    path("solicitudes/<uuid:referencia>/", clientes.detalle, name="detalle"),
    path("solicitudes/<uuid:referencia>/imagen/<int:orden>/", clientes.imagen, name="imagen"),
]
