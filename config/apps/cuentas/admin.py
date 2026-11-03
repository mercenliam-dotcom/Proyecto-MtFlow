from django.contrib import admin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    """Vista de consulta en el admin de Django. La gestión se hace desde el panel propio."""
    list_display = ("nombre_usuario", "nombre", "apellido", "email", "rol", "is_active", "creado_en")
    list_filter = ("rol", "is_active")
    search_fields = ("nombre_usuario", "nombre", "apellido", "email")
    readonly_fields = ("uuid", "password", "creado_en", "creado_por", "last_login")
    exclude = ("groups", "user_permissions")

    def has_delete_permission(self, request, obj=None):
        return False  # las cuentas se desactivan, no se borran
