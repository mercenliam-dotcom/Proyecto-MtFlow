"""
Modelo de usuario de MTFlow.

Decisiones (ADR-0008):
  - No existe registro público. Las cuentas las crea un ADMINISTRADOR desde
    el panel. El cliente del estudio no tiene cuenta (decisión #1 del modelo).
  - Dos roles: ADMIN y USUARIO. El rol es un campo, no un grupo, porque el
    sistema solo tiene dos y la regla debe ser evidente en la base de datos.
  - Las cuentas no se borran: se desactivan. Así se conserva quién hizo qué.
  - En las URLs nunca aparece el id numérico (adivinable: /cuentas/1, /2, /3...);
    se usa un UUID aleatorio.
"""
import uuid

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone

from .validadores import validar_nombre_persona, validar_nombre_usuario


class Rol(models.TextChoices):
    ADMIN = "ADMIN", "Administrador"
    USUARIO = "USUARIO", "Usuario"


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, nombre_usuario, email, password, **extra):
        if not nombre_usuario:
            raise ValueError("El nombre de usuario es obligatorio.")
        usuario = self.model(
            nombre_usuario=nombre_usuario.strip().lower(),
            email=self.normalize_email(email).lower(),
            **extra,
        )
        usuario.set_password(password)
        usuario.full_clean(exclude=["password"])
        usuario.save(using=self._db)
        return usuario

    def create_user(self, nombre_usuario, email, password=None, **extra):
        extra.setdefault("rol", Rol.USUARIO)
        extra["is_superuser"] = False
        return self._crear(nombre_usuario, email, password, **extra)

    def create_superuser(self, nombre_usuario, email, password=None, **extra):
        extra["rol"] = Rol.ADMIN
        extra["is_superuser"] = True
        extra.setdefault("debe_cambiar_contrasena", False)
        return self._crear(nombre_usuario, email, password, **extra)

    def get_by_natural_key(self, nombre_usuario):
        return self.get(nombre_usuario__iexact=nombre_usuario)


class Usuario(AbstractBaseUser, PermissionsMixin):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nombre_usuario = models.CharField(
        "nombre de usuario", max_length=30, unique=True,
        validators=[validar_nombre_usuario],
    )
    email = models.EmailField("correo electrónico", max_length=254, unique=True)
    nombre = models.CharField(max_length=60, validators=[validar_nombre_persona])
    apellido = models.CharField(max_length=60, validators=[validar_nombre_persona])
    rol = models.CharField(max_length=10, choices=Rol.choices, default=Rol.USUARIO)
    is_active = models.BooleanField("activa", default=True)
    creado_en = models.DateTimeField(default=timezone.now, editable=False)
    creado_por = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="cuentas_creadas", editable=False,
    )
    debe_cambiar_contrasena = models.BooleanField(
        default=True,
        help_text="Se obliga a cambiar la contraseña temporal en el primer ingreso.",
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "nombre_usuario"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email", "nombre", "apellido"]

    class Meta:
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["nombre", "apellido"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rol__in=[r.value for r in Rol]),
                name="usuario_rol_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(nombre_usuario__regex=r"^[a-z0-9]{4,30}$"),
                name="usuario_nombre_usuario_formato",
            ),
        ]

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.nombre_usuario})"

    @property
    def es_admin(self) -> bool:
        return self.is_active and self.rol == Rol.ADMIN

    @property
    def is_staff(self) -> bool:
        # Acceso al admin de Django solo para administradores.
        return self.es_admin

    def clean(self):
        super().clean()
        if self.nombre_usuario:
            self.nombre_usuario = self.nombre_usuario.strip().lower()
        if self.email:
            self.email = self.email.strip().lower()

    def get_full_name(self):
        return f"{self.nombre} {self.apellido}"

    def get_short_name(self):
        return self.nombre
