from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "MTFlow · administración interna"
admin.site.site_title = "MTFlow"

urlpatterns = [
    path("mi-cuenta/", include("apps.cuentas.urls_cliente")),
    path(settings.DJANGO_ADMIN_URL, admin.site.urls),
    path("cuentas/", include("apps.cuentas.urls")),
    path("clasificacion/", include("apps.clasificacion.urls")),
    path("panel/", include("apps.nucleo.urls")),   # área privada del equipo
    path("", include("web.urls")),                 # sitio público del estudio
]

handler400 = "apps.nucleo.errores.error_400"
handler403 = "apps.nucleo.errores.error_403"
handler404 = "apps.nucleo.errores.error_404"
handler500 = "apps.nucleo.errores.error_500"
