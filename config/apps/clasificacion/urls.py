from django.urls import path

from . import views

app_name = "clasificacion"

urlpatterns = [
    path("probar/", views.probar, name="probar"),
]
