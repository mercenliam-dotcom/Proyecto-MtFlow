from django.urls import path

from . import views, cotizaciones, agenda, flujo, metricas, portafolio
from . import horario_trabajo

app_name = "nucleo"

urlpatterns = [
    path("registro/", cotizaciones.registro, name="registro"),
    path("agenda/horario-trabajo/", horario_trabajo.editar, name="horario_trabajo"),
    path("cotizaciones/<uuid:referencia>/gestion/<str:accion>/", agenda.paso_gestion, name="gestion_paso"),
    path("metricas/", metricas.inicio, name="metricas"),
    path("portafolio/", portafolio.lista, name="portafolio"),
    path("portafolio/nuevo/", portafolio.editar, name="portafolio_nuevo"),
    path("portafolio/<uuid:referencia>/", portafolio.editar, name="portafolio_editar"),
    path("cotizaciones/<uuid:referencia>/flujo/<str:accion>/", flujo.editar, name="flujo"),
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
