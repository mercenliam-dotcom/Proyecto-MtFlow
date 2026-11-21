"""Genera config/static/css/tema-oscuro-colores.css.

Para cada regla de las hojas existentes que fija un color, escribe la misma regla
con su equivalente oscuro (misma especificidad y cargada después, así que gana).
Volver a ejecutarlo si se cambian colores en las hojas de la lista HOJAS:

    pip install tinycss2
    python scripts/generar_tema_oscuro.py config
"""
import colorsys, re, sys
from pathlib import Path
import tinycss2

RAIZ = Path(sys.argv[1])
HOJAS = ["static/css/design.css", "static/css/avisos.css", "static/css/app.css", "web/static/web/css/disponibilidad.css",
         "web/static/web/css/solicitud.css", "static/css/cuenta-navegacion.css", "static/css/pulido.css",
         "static/css/refinado.css", "static/css/validacion.css", "static/css/errores.css"]
NOMBRES = {"white": (255, 255, 255), "black": (0, 0, 0)}
FIJOS = {  # superficies principales con valor exacto
    "fffefa": "#17141f", "ffffff": "#17141f", "f6f4ef": "#0e0c13", "fcfbf8": "#17141f", "fffdf9": "#17141f",
}
TEXTO = {"color", "-webkit-text-fill-color", "caret-color"}
SOMBRA = {"box-shadow", "text-shadow", "filter"}

def a_hex(r, g, b):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in (r, g, b))

def hls(rgb):
    return colorsys.rgb_to_hls(*(v / 255 for v in rgb))

def de_hls(h, l, s):
    return tuple(v * 255 for v in colorsys.hls_to_rgb(h, max(0, min(1, l)), max(0, min(1, s))))

def morado(h, s):
    return 0.66 <= h <= 0.86 and s > 0.15

def mapear(rgb, tipo):
    h, l, s = hls(rgb)
    if tipo == "texto":
        if l >= 0.55:
            return rgb  # texto claro (sobre fondos oscuros o botones): se queda
        if morado(h, s):
            return de_hls(0.72, 0.80, 0.9)  # morado legible sobre fondo oscuro
        return de_hls(h, 0.95 - l * 0.75, min(s, 0.6))
    if tipo == "sombra":
        return None
    # fondos y bordes
    if l >= 0.80:
        return de_hls(h, 0.10 + (1 - l) * 0.6, s * (0.7 if morado(h, s) else 0.35))
    if l >= 0.55:
        return de_hls(h, 1 - l + 0.02, s * 0.8)
    if morado(h, s) and l >= 0.30:
        return de_hls(0.72, 0.62, 0.88)  # acento del mockup (#8b5cf6 aprox.)
    if l < 0.30 and s < 0.35:
        return de_hls(h, 0.055 + l * 0.35, s * 0.8)  # barras oscuras: más profundas
    return rgb

def color_de(tok):
    if tok.type == "hash":
        v = tok.value.lower()
        if len(v) in (3, 4):
            v = "".join(c * 2 for c in v[:3])
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4)), None, v[:6]
    if tok.type == "ident" and tok.lower_value in NOMBRES:
        rgb = NOMBRES[tok.lower_value]
        return rgb, None, a_hex(*rgb)[1:]
    if tok.type == "function" and tok.lower_name in ("rgb", "rgba"):
        nums = [t.value for t in tok.arguments if t.type in ("number", "percentage")]
        if len(nums) >= 3:
            alfa = nums[3] if len(nums) > 3 else None
            return tuple(nums[:3]), alfa, a_hex(*nums[:3])[1:]
    return None

def transformar(tokens, tipo):
    salida, cambio = [], False
    for tok in tokens:
        c = color_de(tok)
        if c:
            rgb, alfa, clave = c
            if tipo == "sombra":
                a = alfa if alfa is not None else 1
                nuevo = "rgba(0, 0, 0, %.2f)" % min(0.6, a * 3) if hls(rgb)[1] < 0.6 else "rgba(255, 255, 255, %.2f)" % min(0.08, a)
            elif tipo == "fondo" and clave in FIJOS and alfa is None:
                nuevo = FIJOS[clave]
            else:
                m = mapear(rgb, tipo)
                hx = a_hex(*m)
                nuevo = hx if alfa is None else "rgba(%d, %d, %d, %s)" % (*(int(hx[i:i + 2], 16) for i in (1, 3, 5)), alfa)
            salida.append(nuevo); cambio = True
        elif tok.type == "function":
            interior, c2 = transformar(tok.arguments, tipo)
            salida.append(f"{tok.name}({interior})"); cambio = cambio or c2
        else:
            salida.append(tok.serialize())
    return "".join(salida), cambio

def tipo_de(prop):
    if prop in TEXTO: return "texto"
    if prop in SOMBRA: return "sombra"
    if prop.startswith(("background", "border", "outline", "fill", "stroke", "column-rule", "text-decoration", "accent-color", "scrollbar")): return "fondo"
    if prop.startswith("--"):
        if prop.startswith(("--ink", "--muted", "--tinta")) or "text" in prop: return "texto"
        if "opacity" in prop or "radio" in prop or "fuente" in prop: return None
        return "fondo"
    return None

def reglas(lista, sangria=""):
    out = []
    for r in lista:
        if r.type == "qualified-rule":
            decls = tinycss2.parse_declaration_list(r.content, skip_whitespace=True, skip_comments=True)
            nuevas = []
            for d in decls:
                if d.type != "declaration": continue
                t = tipo_de(d.lower_name)
                if not t: continue
                crudo = tinycss2.serialize(d.value)
                if t == "texto" and re.search(r"var\(--(purple|acento|acento-oscuro)\)", crudo):
                    # El morado de fondo (#8b5cf6) no alcanza contraste como texto: se usa el tono claro.
                    nuevas.append(f"{d.name}: var(--acento-texto){' !important' if d.important else ''}")
                    continue
                valor, cambio = transformar(d.value, t)
                if cambio:
                    nuevas.append(f"{d.name}: {valor.strip()}{' !important' if d.important else ''}")
            if nuevas:
                out.append(f"{sangria}{tinycss2.serialize(r.prelude).strip()} {{ {'; '.join(nuevas)}; }}")
        elif r.type == "at-rule" and r.lower_at_keyword in ("media", "supports") and r.content:
            dentro = reglas(tinycss2.parse_rule_list(r.content, skip_whitespace=True, skip_comments=True), sangria + "  ")
            if dentro:
                out.append(f"{sangria}@{r.at_keyword} {tinycss2.serialize(r.prelude).strip()} {{\n" + "\n".join(dentro) + f"\n{sangria}}}")
    return out

partes = ["/* GENERADO: equivalentes oscuros de los colores fijos de las hojas anteriores.\n   No editar a mano; los ajustes van en tema-oscuro.css. */"]
for hoja in HOJAS:
    texto = (RAIZ / hoja).read_text()
    r = reglas(tinycss2.parse_stylesheet(texto, skip_whitespace=True, skip_comments=True))
    if r:
        partes.append(f"\n/* --- {hoja} --- */\n" + "\n".join(r))
(RAIZ / "static/css/tema-oscuro-colores.css").write_text("\n".join(partes) + "\n")
print("ok", sum(p.count("{") for p in partes))
