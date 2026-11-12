
from django.urls import path
from django.views.generic import RedirectView
from . import views
from .disponibilidad import calendario_publico
from apps.nucleo.portafolio import imagen

app_name = "web"

urlpatterns = [
    path("cotizacion/disponibilidad/", calendario_publico, name="disponibilidad"),
    path("portafolio/imagen/<uuid:referencia>/", imagen, name="imagen_portafolio"),
    # Direcciones incompletas: llevan a la página que corresponde en vez de un error.
    path("portafolio/imagen/", RedirectView.as_view(pattern_name="web:catalogo")),
    path("portafolio/", RedirectView.as_view(pattern_name="web:portafolio")),
    path("", views.portafolio, name="portafolio"),
    path("catalogo/", views.catalogo, name="catalogo"),
    path("horarios/", views.horarios, name="horarios"),
    path("cotizacion/", views.cotizacion, name="cotizacion"),
    path("cotizacion/analizar/", views.analizar_referencia, name="analizar_referencia"),
]
