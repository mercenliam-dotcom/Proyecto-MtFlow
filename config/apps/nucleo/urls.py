from django.urls import path

from . import views

app_name = "nucleo"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("archivo/<str:token>/", views.archivo, name="archivo"),
]
