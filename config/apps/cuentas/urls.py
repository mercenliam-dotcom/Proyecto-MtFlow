from django.urls import path

from . import views
from . import perfil
from . import social

app_name = "cuentas"

# El registro público de clientes está separado en /mi-cuenta/registro/.
urlpatterns = [
    path("social/conexiones/", social.conexiones, name="social_conexiones"),
    path("social/completar/", social.completar, name="social_completar"),
    path("social/<str:proveedor>/iniciar/", social.iniciar, name="social_iniciar"),
    path("social/<str:proveedor>/callback/", social.callback, name="social_callback"),
    path("perfil/", perfil.propio, name="perfil"),
    path("ingresar/", views.ingresar, name="login"),
    path("salir/", views.salir, name="logout"),
    path("mi-contrasena/", views.mi_contrasena, name="mi_contrasena"),
    path("", views.lista, name="lista"),
    path("nueva/", views.crear, name="crear"),
    path("<uuid:uuid>/editar/", views.editar, name="editar"),
    path("<uuid:uuid>/contrasena/", views.restablecer, name="restablecer"),
]
