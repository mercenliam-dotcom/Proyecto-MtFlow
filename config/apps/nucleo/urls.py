from django.urls import path

from . import views, cotizaciones, agenda

app_name = "nucleo"

urlpatterns = [
    path("agenda/", agenda.inicio, name="agenda"),
    path("agenda/eventos/", agenda.eventos, name="agenda_eventos"),
    path("agenda/nuevo/", agenda.editar, name="agenda_nuevo"),
    path("agenda/<uuid:referencia>/", agenda.editar, name="agenda_editar"),
    path("agenda/<uuid:referencia>/cerrar/", agenda.cerrar, name="agenda_cerrar"),
    path("cotizaciones/<uuid:referencia>/gestion/", agenda.gestion, name="cotizacion_gestion"),
    path("", views.inicio, name="inicio"),
    path("cotizaciones/", cotizaciones.lista, name="cotizaciones"),
    path("cotizaciones/<uuid:referencia>/", cotizaciones.detalle, name="cotizacion_detalle"),
    path("equipo/cotizaciones/", cotizaciones.equipo, name="equipo_cotizaciones"),
    path("equipo/cotizaciones/<uuid:referencia>/", cotizaciones.equipo_detalle, name="equipo_cotizacion_detalle"),
    path("archivo/<str:token>/", views.archivo, name="archivo"),
]
