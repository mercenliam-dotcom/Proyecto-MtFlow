from django.urls import path

from . import views

app_name = "cuentas"

# No existe ruta de registro público: las cuentas solo las crea un administrador.
urlpatterns = [
    path("ingresar/", views.ingresar, name="login"),
    path("salir/", views.salir, name="logout"),
    path("mi-contrasena/", views.mi_contrasena, name="mi_contrasena"),
    path("", views.lista, name="lista"),
    path("nueva/", views.crear, name="crear"),
    path("<uuid:uuid>/editar/", views.editar, name="editar"),
    path("<uuid:uuid>/contrasena/", views.restablecer, name="restablecer"),
]
