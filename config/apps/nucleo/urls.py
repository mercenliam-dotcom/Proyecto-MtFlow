from django.urls import path

from . import views, cotizaciones

app_name = "nucleo"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("cotizaciones/", cotizaciones.lista, name="cotizaciones"),
    path("cotizaciones/<uuid:referencia>/", cotizaciones.detalle, name="cotizacion_detalle"),
    path("equipo/cotizaciones/", cotizaciones.equipo, name="equipo_cotizaciones"),
    path("equipo/cotizaciones/<uuid:referencia>/", cotizaciones.equipo_detalle, name="equipo_cotizacion_detalle"),
    path("archivo/<str:token>/", views.archivo, name="archivo"),
]
