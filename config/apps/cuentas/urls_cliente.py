from django.urls import path
from . import clientes

app_name = "clientes"
urlpatterns = [
    path("", clientes.inicio, name="inicio"),
    path("registro/", clientes.registro, name="registro"),
    path("perfil/", clientes.perfil, name="perfil"),
    path("solicitudes/<uuid:referencia>/", clientes.detalle, name="detalle"),
    path("solicitudes/<uuid:referencia>/imagen/<int:orden>/", clientes.imagen, name="imagen"),
]
