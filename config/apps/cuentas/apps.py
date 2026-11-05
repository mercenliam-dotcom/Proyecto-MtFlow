from django.apps import AppConfig


class CuentasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cuentas"

    def ready(self):
        from django.db.models.signals import post_migrate
        from .arranque import despues_de_migrar
        post_migrate.connect(despues_de_migrar, sender=self,
                             dispatch_uid="cuentas.admin_desarrollo", weak=False)
