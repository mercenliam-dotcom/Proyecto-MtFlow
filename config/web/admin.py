from django.contrib import admin
from .models import Cliente, Tatuadora, Postulacion, Imagen, Estilo, Prediccion

admin.site.register(Cliente)
admin.site.register(Tatuadora)
admin.site.register(Postulacion)
admin.site.register(Imagen)
admin.site.register(Estilo)
admin.site.register(Prediccion)