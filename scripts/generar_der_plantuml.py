"""Genera docs/diagramas/04_DER.puml (notación IE / pata de gallo) desde los modelos Django.

Lee solo metadatos (campos, claves, relaciones); no lee filas ni secretos.
Uso, desde la carpeta del proyecto con el entorno activo:
    python scripts/generar_der_plantuml.py
    java -jar plantuml.jar -tsvg docs/diagramas/04_DER.puml   (o pegar en plantuml.com)
"""
import os, sys
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / "config"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.apps import apps
sys.path.insert(0, str(repo / "scripts"))

NOMBRES = {
    "cuentas.Usuario": "usuario", "cuentas.IdentidadSocial": "identidad_social", "cuentas.PerfilCliente": "perfil_cliente",
    "web.Cliente": "cliente", "web.Tatuadora": "tatuadora", "web.TatuadoraEstilo": "tatuadora_estilo",
    "web.Postulacion": "postulacion", "web.ContactoSolicitud": "contacto_solicitud", "web.Consentimiento": "consentimiento",
    "web.Sesion": "sesion", "web.HorarioTrabajo": "horario_trabajo", "web.BloqueHorario": "bloque_horario",
    "web.MovimientoCobro": "movimiento_cobro", "web.EventoSolicitud": "evento_solicitud",
    "web.Imagen": "imagen", "web.Estilo": "estilo", "web.Prediccion": "prediccion", "web.ConfianzaEstilo": "confianza_estilo",
    "web.EtiquetaConsolidada": "etiqueta_consolidada", "web.TrabajoPortafolio": "trabajo_portafolio",
}
GRUPOS = [
    ("Cuentas y profesionales", "#EDE7F6", ["usuario", "identidad_social", "perfil_cliente", "cliente", "tatuadora", "tatuadora_estilo"]),
    ("Solicitudes, agenda y cobros", "#FFF3E0", ["postulacion", "contacto_solicitud", "consentimiento", "sesion", "horario_trabajo", "bloque_horario", "movimiento_cobro", "evento_solicitud"]),
    ("Imágenes, clasificación y portafolio", "#E3F2FD", ["imagen", "estilo", "prediccion", "confianza_estilo", "etiqueta_consolidada", "trabajo_portafolio"]),
]
NUEVO = {"consentimiento": "nueva", "postulacion": "precio_sugerido_maximo"}
TIPOS = {"BigAutoField": "bigint", "AutoField": "int", "BigIntegerField": "bigint", "IntegerField": "int", "PositiveIntegerField": "int",
         "SmallIntegerField": "smallint", "PositiveSmallIntegerField": "smallint", "UUIDField": "uuid", "BooleanField": "bool",
         "FloatField": "float", "DateTimeField": "timestamptz", "DateField": "date", "TimeField": "time", "TextField": "text",
         "JSONField": "jsonb", "FileField": "varchar", "ImageField": "varchar"}


def tipo(f):
    if f.is_relation:
        return tipo(f.target_field)
    t = f.get_internal_type()
    if t == "DecimalField":
        return f"numeric({f.max_digits},{f.decimal_places})"
    if t in ("CharField", "EmailField"):
        return f"varchar({f.max_length})"
    return TIPOS[t]


modelos = {NOMBRES[l]: apps.get_model(l) for l in NOMBRES}
L = ["@startuml 04_DER", "' GENERADO por scripts/generar_der_plantuml.py desde los modelos Django. No editar a mano.",
     "' Notación IE (pata de gallo). * = obligatorio (NOT NULL). PK/FK/UQ = clave primaria, foránea, única.",
     "skinparam linetype ortho", "skinparam shadowing false", "skinparam roundcorner 6", "skinparam defaultFontName Arial",
     "skinparam entity {", "  BackgroundColor white", "  BorderColor #4A3B5C", "  FontSize 12", "}", "skinparam ArrowColor #4A3B5C",
     "hide circle", "left to right direction",
     "title MTFlow — Diagrama entidad-relación (modelo físico vigente, noviembre 2026)", ""]
for titulo, color, tablas in GRUPOS:
    L.append(f'package "{titulo}" {color} {{')
    for n in tablas:
        m = modelos[n]
        cab = f'entity "{n}" as {n}'
        if NUEVO.get(n) == "nueva":
            cab += " #E8F5E9"
        L.append(f"  {cab} {{")
        pks = [f for f in m._meta.local_fields if f.primary_key]
        for f in pks:
            marca = "PK, FK" if f.is_relation else "PK"
            L.append(f"    * **{f.column}** : {tipo(f)} <<{marca}>>")
        L.append("    --")
        for f in m._meta.local_fields:
            if f.primary_key or f.column == "password":
                continue
            marcas = []
            if f.is_relation:
                marcas.append("FK")
            if f.unique:
                marcas.append("UQ")
            sufijo = f" <<{', '.join(marcas)}>>" if marcas else ""
            nuevo = " <color:#2E7D32>(nuevo)</color>" if NUEVO.get(n) == f.name else ""
            L.append(f"    {'*' if not f.null else ''} {f.column} : {tipo(f)}{sufijo}{nuevo}")
        if n == "usuario":
            L.append("    * password : varchar(128) <<hash>>")
        L.append("  }")
    L.append("}")
    L.append("")

for n, m in modelos.items():
    for f in m._meta.local_fields:
        if not f.is_relation:
            continue
        destino = NOMBRES[f.remote_field.model._meta.label]
        lado_padre = "||" if not f.null else "|o"
        if f.one_to_one or f.unique:
            L.append(f"{destino} {lado_padre}--o| {n}")
        else:
            L.append(f"{destino} {lado_padre}--o{{ {n}")
L += ["", "legend right",
      "  <b>Cambios de la entrega final</b>",
      "  <back:#E8F5E9>consentimiento</back>: tabla nueva (1 a 1 con postulacion),",
      "  ficha de salud del cliente + declaración de la tatuadora.",
      "  postulacion.<b>precio_sugerido_maximo</b>: máximo de la estimación",
      "  entregada al cliente (antes solo se guardaba el mínimo).",
      "  identidad_social: tabla preparada para el acceso con",
      "  Google/Facebook, que está desactivado (no se usa).",
      "  Área, saldo, total cobrado y estado comercial mostrado",
      "  se calculan: no son columnas.",
      "endlegend", "@enduml", ""]
salida = repo / "docs" / "diagramas" / "04_DER.puml"
salida.write_text("\n".join(L), encoding="utf-8")
print(salida, len(modelos), "tablas")
