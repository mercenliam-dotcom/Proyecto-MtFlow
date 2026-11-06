
from django.urls import path
from . import views
from .disponibilidad import calendario_publico
from apps.nucleo.portafolio import imagen

app_name = "web"

urlpatterns = [
    path("cotizacion/disponibilidad/", calendario_publico, name="disponibilidad"),
    path("portafolio/imagen/<uuid:referencia>/", imagen, name="imagen_portafolio"),
    path("", views.portafolio, name="portafolio"),
    path("horarios/", views.horarios, name="horarios"),
    path("cotizacion/", views.cotizacion, name="cotizacion"),
    path("cotizacion/analizar/", views.analizar_referencia, name="analizar_referencia"),
]
