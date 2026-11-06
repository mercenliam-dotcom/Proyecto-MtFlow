from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from apps.cuentas.models import Rol, Usuario

CLAVE = "Tinta2026segura"


def crear(nombre_usuario, rol=Rol.USUARIO, activo=True, temporal=False, **extra):
    datos = dict(email=f"{nombre_usuario}@estudio.cl", nombre="Ana", apellido="Rojas")
    datos.update(extra)
    u = Usuario.objects.create_user(nombre_usuario, password=CLAVE, rol=rol, **datos)
    u.is_active = activo
    u.debe_cambiar_contrasena = temporal
    u.save()
    return u


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = crear("admin01", Rol.ADMIN)
        self.normal = crear("tatuadora1", Rol.USUARIO)

    def entrar(self, usuario):
        self.client.force_login(usuario)


class SinRegistroPublico(Base):
    def test_no_existe_ruta_de_registro(self):
        for nombre in ("cuentas:registro", "cuentas:signup", "cuentas:registrar"):
            with self.assertRaises(NoReverseMatch):
                reverse(nombre)
        for ruta in ("/cuentas/registro/", "/cuentas/registrarse/", "/registro/", "/signup/"):
            self.client.logout()
            r = self.client.get(ruta)
            self.assertIn(r.status_code, (302, 404), ruta)

    def test_anonimo_no_puede_crear_cuentas(self):
        r = self.client.post(reverse("cuentas:crear"), {"nombre_usuario": "intruso"})
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("cuentas:login"), r["Location"])
        self.assertFalse(Usuario.objects.filter(nombre_usuario="intruso").exists())


class PermisosPorRol(Base):
    def test_usuario_normal_no_ve_gestion_de_cuentas(self):
        self.entrar(self.normal)
        for url in (reverse("cuentas:lista"), reverse("cuentas:crear"),
                    reverse("cuentas:editar", args=[self.admin.uuid]),
                    reverse("cuentas:restablecer", args=[self.admin.uuid])):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_usuario_normal_no_puede_ascenderse_por_post(self):
        self.entrar(self.normal)
        r = self.client.post(reverse("cuentas:editar", args=[self.normal.uuid]),
                             {"nombre": "Ana", "apellido": "Rojas", "email": "x@x.cl",
                              "rol": "ADMIN", "is_active": "on"})
        self.assertEqual(r.status_code, 403)
        self.normal.refresh_from_db()
        self.assertEqual(self.normal.rol, Rol.USUARIO)

    def test_admin_ve_gestion(self):
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse("cuentas:lista")).status_code, 200)

    def test_menu_oculta_cuentas_a_usuario_normal(self):
        self.entrar(self.normal)
        r = self.client.get(reverse("clientes:inicio"))
        self.assertNotContains(r, reverse("cuentas:lista") + '"')

    def test_url_usa_uuid_no_id(self):
        self.entrar(self.admin)
        r = self.client.get(f"/cuentas/{self.normal.pk}/editar/")
        self.assertEqual(r.status_code, 404)

    def test_rol_invalido_lo_rechaza_la_base_de_datos(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            Usuario.objects.filter(pk=self.normal.pk).update(rol="SUPERADMIN")


class CrearCuentas(Base):
    def datos(self, **cambios):
        d = {"nombre_usuario": "maria2026", "nombre": "María José", "apellido": "Muñoz",
             "email": "maria@estudio.cl", "rol": "USUARIO",
             "password1": "Agujas!Negras77", "password2": "Agujas!Negras77"}
        d.update(cambios)
        return d

    def setUp(self):
        super().setUp()
        self.entrar(self.admin)

    def test_admin_crea_cuenta_con_clave_temporal(self):
        r = self.client.post(reverse("cuentas:crear"), self.datos())
        self.assertRedirects(r, reverse("cuentas:lista"))
        u = Usuario.objects.get(nombre_usuario="maria2026")
        self.assertEqual(u.rol, Rol.USUARIO)
        self.assertTrue(u.debe_cambiar_contrasena)
        self.assertEqual(u.creado_por, self.admin)
        self.assertTrue(u.password.startswith("argon2"))      # hash, no texto plano
        self.assertNotIn("Agujas", u.password)

    def test_admin_crea_otro_admin(self):
        self.client.post(reverse("cuentas:crear"), self.datos(rol="ADMIN"))
        self.assertEqual(Usuario.objects.get(nombre_usuario="maria2026").rol, Rol.ADMIN)

    def test_nombre_usuario_se_normaliza_a_minusculas(self):
        self.client.post(reverse("cuentas:crear"), self.datos(nombre_usuario="Maria2026"))
        self.assertTrue(Usuario.objects.filter(nombre_usuario="maria2026").exists())

    def test_nombre_usuario_con_simbolos_rechazado(self):
        for malo in ("maria.jose", "maria_jose", "maría", "ma ria", "admin'--", "<b>x</b>", "abc"):
            r = self.client.post(reverse("cuentas:crear"), self.datos(nombre_usuario=malo))
            self.assertEqual(r.status_code, 200, malo)
            self.assertTrue(r.context["form"].errors.get("nombre_usuario"), malo)

    def test_nombre_con_numeros_o_simbolos_rechazado(self):
        for malo in ("Ana3", "Ana<script>", "Ana_", "J@vier"):
            r = self.client.post(reverse("cuentas:crear"), self.datos(nombre=malo))
            self.assertTrue(r.context["form"].errors.get("nombre"), malo)

    def test_nombre_usuario_duplicado(self):
        r = self.client.post(reverse("cuentas:crear"), self.datos(nombre_usuario="tatuadora1"))
        self.assertTrue(r.context["form"].errors.get("nombre_usuario"))

    def test_correo_duplicado_sin_importar_mayusculas(self):
        r = self.client.post(reverse("cuentas:crear"), self.datos(email="TATUADORA1@estudio.cl"))
        self.assertTrue(r.context["form"].errors.get("email"))

    def test_contrasenas_no_coinciden(self):
        r = self.client.post(reverse("cuentas:crear"), self.datos(password2="OtraClave123"))
        self.assertIn("no coinciden", str(r.context["form"].errors))

    def test_contrasena_corta(self):
        r = self.client.post(reverse("cuentas:crear"), self.datos(password1="Ab1", password2="Ab1"))
        self.assertTrue(r.context["form"].errors.get("password1"))

    def test_contrasena_sin_numero(self):
        r = self.client.post(reverse("cuentas:crear"),
                             self.datos(password1="SoloLetrasLargas", password2="SoloLetrasLargas"))
        self.assertIn("número", str(r.context["form"].errors))

    def test_contrasena_solo_numeros(self):
        r = self.client.post(reverse("cuentas:crear"),
                             self.datos(password1="12345678901", password2="12345678901"))
        self.assertTrue(r.context["form"].errors.get("password1"))

    def test_contrasena_comun(self):
        r = self.client.post(reverse("cuentas:crear"),
                             self.datos(password1="password123", password2="password123"))
        self.assertTrue(r.context["form"].errors.get("password1"))

    def test_contrasena_parecida_al_usuario(self):
        r = self.client.post(reverse("cuentas:crear"),
                             self.datos(password1="maria2026x", password2="maria2026x"))
        self.assertTrue(r.context["form"].errors.get("password1"))

    def test_contrasena_con_simbolos_si_se_permite(self):
        r = self.client.post(reverse("cuentas:crear"),
                             self.datos(password1="T@tu-ajes#2026", password2="T@tu-ajes#2026"))
        self.assertEqual(r.status_code, 302)

    def test_sin_csrf_rechaza(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.admin)
        r = c.post(reverse("cuentas:crear"), self.datos())
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Usuario.objects.filter(nombre_usuario="maria2026").exists())


class ProteccionDelUltimoAdmin(Base):
    def test_no_puede_quitarse_admin_a_si_mismo(self):
        self.entrar(self.admin)
        r = self.client.post(reverse("cuentas:editar", args=[self.admin.uuid]),
                             {"nombre": "Ana", "apellido": "Rojas", "email": self.admin.email,
                              "rol": "USUARIO", "is_active": "on"})
        self.assertEqual(r.status_code, 200)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.rol, Rol.ADMIN)

    def test_puede_desactivar_otra_cuenta(self):
        self.entrar(self.admin)
        r = self.client.post(reverse("cuentas:editar", args=[self.normal.uuid]),
                             {"nombre": "Ana", "apellido": "Rojas", "email": self.normal.email,
                              "rol": "USUARIO"})
        self.assertRedirects(r, reverse("cuentas:lista"))
        self.normal.refresh_from_db()
        self.assertFalse(self.normal.is_active)


class InicioDeSesion(Base):
    def login(self, usuario, clave, **extra):
        return self.client.post(reverse("cuentas:login"),
                                {"nombre_usuario": usuario, "password": clave, **extra})

    def test_login_correcto(self):
        r = self.login("tatuadora1", CLAVE)
        self.assertRedirects(r, reverse("clientes:inicio"))

    def test_login_ignora_mayusculas_en_usuario(self):
        self.assertEqual(self.login("TATUADORA1", CLAVE).status_code, 302)

    def test_contrasena_incorrecta(self):
        r = self.login("tatuadora1", "NoEsLaClave99")
        self.assertContains(r, "Usuario o contraseña incorrectos")

    def test_mismo_mensaje_si_usuario_no_existe(self):
        r = self.login("noexiste", "NoEsLaClave99")
        self.assertContains(r, "Usuario o contraseña incorrectos")

    def test_cuenta_desactivada_no_entra(self):
        crear("inactiva1", activo=False)
        r = self.login("inactiva1", CLAVE)
        self.assertContains(r, "Usuario o contraseña incorrectos")

    def test_contrasena_se_compara_por_hash(self):
        u = Usuario.objects.get(nombre_usuario="tatuadora1")
        self.assertTrue(u.check_password(CLAVE))
        self.assertNotEqual(u.password, CLAVE)

    @override_settings(LOGIN_MAX_INTENTOS=3)
    def test_bloqueo_tras_intentos_fallidos(self):
        for _ in range(3):
            self.login("tatuadora1", "Incorrecta123")
        r = self.login("tatuadora1", CLAVE)  # incluso con la clave correcta
        self.assertContains(r, "Demasiados intentos")
        cache.clear()
        self.assertEqual(self.login("tatuadora1", CLAVE).status_code, 302)

    def test_inyeccion_sql_en_usuario(self):
        r = self.login("' OR '1'='1", "' OR '1'='1")
        self.assertContains(r, "Usuario o contraseña incorrectos")

    def test_redireccion_externa_bloqueada(self):
        for malo in ("https://sitio-falso.com/", "//sitio-falso.com", "/\\sitio-falso.com",
                     "javascript:alert(1)", "https:sitio-falso.com"):
            cache.clear()
            r = self.login("tatuadora1", CLAVE, next=malo)
            self.assertEqual(r["Location"], reverse("clientes:inicio"), malo)
            self.client.logout()

    def test_redireccion_interna_permitida(self):
        r = self.login("tatuadora1", CLAVE, next="/mi-cuenta/perfil/")
        self.assertEqual(r["Location"], "/mi-cuenta/perfil/")

    def test_salir_solo_por_post(self):
        self.entrar(self.normal)
        self.assertEqual(self.client.get(reverse("cuentas:logout")).status_code, 405)
        self.client.post(reverse("cuentas:logout"))
        self.assertEqual(self.client.get(reverse("nucleo:inicio")).status_code, 302)

    def test_sesion_cambia_al_ingresar(self):
        self.client.get(reverse("cuentas:login"))
        self.client.cookies["sessionid"] = "sesionfijadaporelatacante"
        self.login("tatuadora1", CLAVE)
        self.assertNotEqual(self.client.cookies["sessionid"].value, "sesionfijadaporelatacante")


class ContrasenaTemporal(Base):
    def test_obliga_a_cambiarla(self):
        u = crear("nueva01", temporal=True)
        self.entrar(u)
        r = self.client.get(reverse("clasificacion:probar"))
        self.assertRedirects(r, reverse("cuentas:mi_contrasena"))

    def test_cambio_exige_contrasena_actual(self):
        u = crear("nueva01", temporal=True)
        self.entrar(u)
        r = self.client.post(reverse("cuentas:mi_contrasena"),
                             {"actual": "Equivocada99", "password1": "NuevaClave2026",
                              "password2": "NuevaClave2026"})
        self.assertTrue(r.context["form"].errors.get("actual"))

    def test_cambio_correcto_libera_el_acceso(self):
        u = crear("nueva01", temporal=True)
        self.entrar(u)
        r = self.client.post(reverse("cuentas:mi_contrasena"),
                             {"actual": CLAVE, "password1": "NuevaClave2026", "password2": "NuevaClave2026"})
        self.assertRedirects(r, reverse("clientes:inicio"))
        u.refresh_from_db()
        self.assertFalse(u.debe_cambiar_contrasena)
        self.assertTrue(u.check_password("NuevaClave2026"))

    def test_admin_restablece_y_queda_temporal(self):
        self.entrar(self.admin)
        r = self.client.post(reverse("cuentas:restablecer", args=[self.normal.uuid]),
                             {"password1": "Temporal2026x", "password2": "Temporal2026x"})
        self.assertRedirects(r, reverse("cuentas:lista"))
        self.normal.refresh_from_db()
        self.assertTrue(self.normal.debe_cambiar_contrasena)
        self.assertTrue(self.normal.check_password("Temporal2026x"))


class Modelo(TestCase):
    def test_create_superuser_es_admin(self):
        u = Usuario.objects.create_superuser("raiz2026", "r@e.cl", CLAVE, nombre="Ana", apellido="Rojas")
        self.assertEqual(u.rol, Rol.ADMIN)
        self.assertTrue(u.is_staff)

    def test_manager_valida_formato(self):
        with self.assertRaises(ValidationError):
            Usuario.objects.create_user("x!", "x@e.cl", CLAVE, nombre="Ana", apellido="Rojas")
