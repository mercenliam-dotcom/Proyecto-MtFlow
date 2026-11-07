from django.contrib import admin
from .models import (Cliente, Tatuadora, Postulacion, ContactoSolicitud, Imagen,
                     Estilo, Prediccion, BloqueHorario, Sesion, EventoSolicitud, ConfianzaEstilo)
from .models import MovimientoCobro, TrabajoPortafolio, EtiquetaConsolidada


class RegistroOperativoAdmin(admin.ModelAdmin):
    """Los cambios pasan por el flujo que valida estados y permisos."""
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class TatuadoraAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return ("usuario",) if obj else ()


for modelo in (Postulacion, ContactoSolicitud, Imagen, Prediccion, BloqueHorario,
               Sesion, EventoSolicitud, ConfianzaEstilo, MovimientoCobro, TrabajoPortafolio, EtiquetaConsolidada):
    admin.site.register(modelo, RegistroOperativoAdmin)
@admin.register(Cliente)
class ClienteAdmin(RegistroOperativoAdmin):
    list_display = ("id", "nombres", "primer_apellido", "segundo_apellido", "usuario")
    search_fields = ("nombres", "primer_apellido", "correo")
admin.site.register(Tatuadora, TatuadoraAdmin)
admin.site.register(Estilo)
