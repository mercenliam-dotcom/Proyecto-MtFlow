
from django.urls import path
from . import views

app_name = "web"

urlpatterns = [
    path("", views.portafolio, name="portafolio"),
    path("horarios/", views.horarios, name="horarios"),
]