"""Genera docs/diagramas/03_clases_dominio.puml desde los modelos Django (vista de dominio).

A diferencia del DER, omite columnas técnicas (claves foráneas, id) y muestra las
asociaciones con su multiplicidad y las enumeraciones de estado.
Uso: python scripts/generar_clases_plantuml.py
"""
import os, sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / "config"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.apps import apps

MODELOS = ["cuentas.Usuario", "cuentas.IdentidadSocial", "cuentas.PerfilCliente", "web.Cliente", "web.Tatuadora",
           "web.TatuadoraEstilo", "web.Estilo", "web.Postulacion", "web.ContactoSolicitud", "web.Consentimiento",
           "web.Sesion", "web.HorarioTrabajo", "web.BloqueHorario", "web.MovimientoCobro", "web.EventoSolicitud",
           "web.Imagen", "web.Prediccion", "web.ConfianzaEstilo", "web.EtiquetaConsolidada", "web.TrabajoPortafolio"]
OMITIR = {"password", "last_login", "is_superuser", "es_admin_desarrollo", "uuid", "referencia", "actualizada_en",
          "actualizado_en", "creado_en", "creada_en", "ciclo_de_vida", "vista_en"}
TIPOS = {"BigAutoField": "Entero", "AutoField": "Entero", "IntegerField": "Entero", "PositiveIntegerField": "Entero",
         "SmallIntegerField": "Entero", "PositiveSmallIntegerField": "Entero", "BigIntegerField": "Entero",
         "BooleanField": "Booleano", "FloatField": "Real", "DecimalField": "Decimal", "DateTimeField": "FechaHora",
         "DateField": "Fecha", "TimeField": "Hora", "TextField": "Texto", "CharField": "Texto", "EmailField": "Correo",
         "UUIDField": "UUID", "JSONField": "JSON", "FileField": "Archivo", "ImageField": "Archivo"}
NUEVAS = {"Consentimiento"}

L = ["@startuml 03_clases_dominio", "' GENERADO por scripts/generar_clases_plantuml.py desde los modelos Django.",
     "!include _estilo.iuml", "skinparam classAttributeIconSize 0", "skinparam class {", "  BackgroundColor white",
     "  BorderColor #4A3B5C", "}", "hide empty methods", "left to right direction",
     "title MTFlow — Diagrama de clases del dominio (vigente)", ""]
for label in MODELOS:
    m = apps.get_model(label)
    n = m.__name__
    L.append(f"class {n}{' #E8F5E9' if n in NUEVAS else ''} {{")
    for f in m._meta.local_fields:
        if f.is_relation or f.primary_key or f.name in OMITIR:
            continue
        t = "Estado" + n if f.name == "estado" and n == "Postulacion" else TIPOS[f.get_internal_type()]
        nuevo = " <color:#2E7D32>«nuevo»</color>" if (n, f.name) == ("Postulacion", "precio_sugerido_maximo") else ""
        L.append(f"  {f.name} : {t}{' [0..1]' if f.null else ''}{nuevo}")
    if n == "Postulacion":
        L += ["  --", "  area_cm2() : Decimal", "  total_cobrado() : Entero", "  saldo_pendiente() : Entero", "  estado_comercial() : Texto"]
    if n == "Consentimiento":
        L += ["  --", "  completo() : Booleano"]
    L.append("}")
L += ["", "enum EstadoPostulacion {", "  RECIBIDA", "  EN_REVISION", "  ACEPTADA", "  RESERVADA", "  REALIZADA", "  RECHAZADA", "}",
      "enum Rol {", "  ADMIN", "  USUARIO", "}", ""]

vistos = set()
for label in MODELOS:
    m = apps.get_model(label)
    for f in m._meta.local_fields:
        if not f.is_relation:
            continue
        destino = f.remote_field.model.__name__
        lado_hijo = "0..1" if (f.one_to_one or f.unique) else "*"
        lado_padre = "0..1" if f.null else "1"
        rol = f.name
        if f.one_to_one and f.primary_key:  # parte dependiente: composición
            L.append(f'{destino} "1" *-- "{lado_hijo}" {m.__name__} : {rol}')
        else:
            L.append(f'{destino} "{lado_padre}" -- "{lado_hijo}" {m.__name__} : {rol}')
L += ["Postulacion ..> EstadoPostulacion", "Usuario ..> Rol", "",
      "note \"Consentimiento: nueva en la entrega final (1 a 1 con Postulacion).\\nprecio_sugerido_maximo: máximo de la estimación entregada.\\nIdentidadSocial: preparada para Google/Facebook, desactivado (no se usa).\" as N1",
      "N1 .. Consentimiento", "@enduml", ""]
(repo / "docs/diagramas/03_clases_dominio.puml").write_text("\n".join(L), encoding="utf-8")
print("ok")
