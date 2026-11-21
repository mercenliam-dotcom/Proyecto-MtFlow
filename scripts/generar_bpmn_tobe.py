"""Genera docs/diagramas/09_BPMN_TO-BE.svg: proceso TO-BE de MTFlow en notación BPMN 2.0.

Dibujo propio en SVG (sin dependencias): pools, carriles, eventos, tareas con
marcador (usuario/servicio), subproceso con bucle, compuertas exclusivas, flujos
de secuencia y flujos de mensaje. Para editarlo: cambiar coordenadas o textos aquí
y ejecutar `python scripts/generar_bpmn_tobe.py`; el .svg también se abre en draw.io.
"""
from pathlib import Path
from xml.sax.saxutils import escape

TINTA = "#2B2433"
SUAVE = "#6B6275"
W, H = 3240, 850
out = []


def texto(x, y, lineas, tam=12, ancla="middle", peso="normal", color=TINTA, estilo="normal"):
    if isinstance(lineas, str):
        lineas = lineas.split("\n")
    alto = tam * 1.25
    y0 = y - (len(lineas) - 1) * alto / 2
    for i, l in enumerate(lineas):
        out.append(f'<text x="{x}" y="{y0 + i * alto + tam * 0.35:.1f}" font-size="{tam}" text-anchor="{ancla}" '
                   f'font-weight="{peso}" font-style="{estilo}" fill="{color}">{escape(l)}</text>')


# ----------------------------------------------------------------- contenedores
def pool(y, alto, nombre, cerrado=False, carriles=()):
    out.append(f'<rect x="20" y="{y}" width="{W - 40}" height="{alto}" fill="white" stroke="{TINTA}" stroke-width="1.6"/>')
    if cerrado:
        texto(W / 2, y + alto / 2, nombre, 14, peso="bold")
        return
    out.append(f'<line x1="52" y1="{y}" x2="52" y2="{y + alto}" stroke="{TINTA}" stroke-width="1.6"/>')
    out.append(f'<text transform="translate(40,{y + alto / 2}) rotate(-90)" font-size="14" font-weight="bold" '
               f'text-anchor="middle" fill="{TINTA}">{escape(nombre)}</text>')
    yy = y
    for nombre_c, alto_c in carriles:
        out.append(f'<rect x="52" y="{yy}" width="{W - 72}" height="{alto_c}" fill="none" stroke="{TINTA}" stroke-width="1"/>')
        out.append(f'<line x1="82" y1="{yy}" x2="82" y2="{yy + alto_c}" stroke="{TINTA}" stroke-width="1"/>')
        out.append(f'<text transform="translate(71,{yy + alto_c / 2}) rotate(-90)" font-size="13" '
                   f'text-anchor="middle" fill="{TINTA}">{escape(nombre_c)}</text>')
        yy += alto_c


# ----------------------------------------------------------------- nodos
NODOS = {}


class Nodo:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    def p(self, lado):
        return {"izq": (self.x - self.w / 2, self.y), "der": (self.x + self.w / 2, self.y),
                "arr": (self.x, self.y - self.h / 2), "aba": (self.x, self.y + self.h / 2)}[lado]


def sobre(x, y):
    """Sobre de mensaje centrado en (x, y)."""
    out.append(f'<rect x="{x - 9}" y="{y - 6}" width="18" height="12" fill="white" stroke="{TINTA}" stroke-width="1.2"/>')
    out.append(f'<polyline points="{x - 9},{y - 6} {x},{y + 1} {x + 9},{y - 6}" fill="none" stroke="{TINTA}" stroke-width="1.2"/>')


def evento(clave, x, y, tipo, etiqueta="", mensaje=False):
    r = 18
    if tipo == "inicio":
        out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="{TINTA}" stroke-width="1.6"/>')
    elif tipo == "fin":
        out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="{TINTA}" stroke-width="4"/>')
    else:  # intermedio de captura
        out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="white" stroke="{TINTA}" stroke-width="1.4"/>')
        out.append(f'<circle cx="{x}" cy="{y}" r="{r - 4}" fill="none" stroke="{TINTA}" stroke-width="1.4"/>')
    if mensaje:
        sobre(x, y)
    if etiqueta:
        texto(x, y + r + 18, etiqueta, 11)
    NODOS[clave] = Nodo(x, y, 2 * r, 2 * r)


def icono_usuario(x, y):
    out.append(f'<circle cx="{x}" cy="{y - 3}" r="4" fill="none" stroke="{TINTA}" stroke-width="1.2"/>')
    out.append(f'<path d="M{x - 7},{y + 9} q0,-8 7,-8 q7,0 7,8 z" fill="none" stroke="{TINTA}" stroke-width="1.2"/>')


def icono_servicio(x, y):
    for ang in range(0, 360, 45):
        out.append(f'<rect x="{x - 1.6}" y="{y - 8}" width="3.2" height="4" fill="{TINTA}" transform="rotate({ang} {x} {y})"/>')
    out.append(f'<circle cx="{x}" cy="{y}" r="5.5" fill="white" stroke="{TINTA}" stroke-width="1.4"/>')
    out.append(f'<circle cx="{x}" cy="{y}" r="2" fill="none" stroke="{TINTA}" stroke-width="1.2"/>')


def tarea(clave, x, y, etiqueta, tipo="usuario", w=150, h=66, subproceso=False, bucle=False, nuevo=False):
    relleno = "#E8F5E9" if nuevo else "white"
    out.append(f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="10" fill="{relleno}" '
               f'stroke="{TINTA}" stroke-width="1.5"/>')
    if tipo == "usuario":
        icono_usuario(x - w / 2 + 13, y - h / 2 + 13)
    elif tipo == "servicio":
        icono_servicio(x - w / 2 + 13, y - h / 2 + 13)
    texto(x + 4, y - (6 if subproceso else 0), etiqueta, 11.5)
    if subproceso:
        out.append(f'<rect x="{x - 7}" y="{y + h / 2 - 16}" width="14" height="14" fill="white" stroke="{TINTA}" stroke-width="1.2"/>')
        out.append(f'<path d="M{x - 4},{y + h / 2 - 9} h8 M{x},{y + h / 2 - 13} v8" stroke="{TINTA}" stroke-width="1.4"/>')
    if bucle:
        bx = x - 20 if subproceso else x
        out.append(f'<path d="M{bx + 4},{y + h / 2 - 5} a5,5 0 1,0 -4,2" fill="none" stroke="{TINTA}" stroke-width="1.3"/>')
        out.append(f'<path d="M{bx - 3},{y + h / 2 - 6} l3,4 l1,-4" fill="none" stroke="{TINTA}" stroke-width="1.3"/>')
    NODOS[clave] = Nodo(x, y, w, h)


def compuerta(clave, x, y, etiqueta="", lado_etiqueta="arr"):
    s = 25
    out.append(f'<polygon points="{x},{y - s} {x + s},{y} {x},{y + s} {x - s},{y}" fill="white" stroke="{TINTA}" stroke-width="1.5"/>')
    out.append(f'<path d="M{x - 8},{y - 8} L{x + 8},{y + 8} M{x + 8},{y - 8} L{x - 8},{y + 8}" stroke="{TINTA}" stroke-width="2.4"/>')
    if etiqueta:
        if lado_etiqueta == "der":
            texto(x + s + 8, y, etiqueta, 11, ancla="start")
        else:
            dy = -s - 20 if lado_etiqueta == "arr" else s + 20
            texto(x, y + dy, etiqueta, 11)
    NODOS[clave] = Nodo(x, y, 2 * s, 2 * s)


# ----------------------------------------------------------------- flujos
def _ruta(origen, destino, por=()):
    a = NODOS[origen[0]].p(origen[1])
    b = NODOS[destino[0]].p(destino[1])
    return [a, *por, b]


def secuencia(origen, destino, por=(), etiqueta="", pos=None):
    pts = _ruta(origen, destino, por)
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out.append(f'<polyline points="{d}" fill="none" stroke="{TINTA}" stroke-width="1.4" marker-end="url(#flecha)"/>')
    if etiqueta:
        x, y = pos if pos else ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2 - 9)
        texto(x, y, etiqueta, 11, color=SUAVE, peso="bold")


def mensaje(a, b, etiqueta="", lado="der", y_etiqueta=None):
    """Flujo de mensaje recto vertical entre dos puntos (x, y)."""
    (x1, y1), (x2, y2) = a, b
    out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{TINTA}" stroke-width="1.2" '
               f'stroke-dasharray="7,5" marker-start="url(#origen)" marker-end="url(#abierta)"/>')
    if etiqueta:
        ym = y_etiqueta or ((y1 + y2) / 2 if abs(y2 - y1) < 200 else min(y1, y2) + 60)
        texto(x1 + (8 if lado == "der" else -8), ym, etiqueta, 10.5, ancla="start" if lado == "der" else "end", estilo="italic")


# ================================================================= dibujo
Y_CLI, Y_EST, Y_ML = 20, 130, 730
CARRIL_T, CARRIL_S = 300, 300
pool(Y_CLI, 80, "Cliente", cerrado=True)
pool(Y_EST, CARRIL_T + CARRIL_S, "Maldita Ternura Estudio — MTFlow", carriles=(("Tatuadora", CARRIL_T), ("Sistema MTFlow", CARRIL_S)))
pool(Y_ML, 80, "Servicio de clasificación (FastAPI · EfficientNetB0 v3)", cerrado=True)
YT = Y_EST + 150          # fila principal de la tatuadora
YT_ARR = Y_EST + 58       # fila superior (rechazo, inasistencia)
YS = Y_EST + CARRIL_T + 120   # fila principal del sistema
YS_ARR = YS - 62
YS_ABA = YS + 92
CLI_ABAJO, ML_ARRIBA = Y_CLI + 80, Y_ML

# --- Sistema: recepción
evento("ini", 130, YS, "inicio", "Solicitud\nenviada", mensaje=True)
tarea("validar", 260, YS, "Validar datos y\nrevisar dominio\ndel correo", "servicio", nuevo=True)
compuerta("g_datos", 395, YS, "¿Datos\nválidos?")
tarea("errores", 395, YS_ABA, "Mostrar errores;\nconservar datos\ne imagen", "servicio", w=140, nuevo=True)
evento("reenvio", 175, YS_ABA, "intermedio", "Corrección\nrecibida", mensaje=True)
tarea("clasificar", 530, YS, "Clasificar imagen\nde referencia", "servicio", w=140)
compuerta("g_conf", 665, YS, "¿Estilo con\nconfianza\nsuficiente\ny sin OOD?", lado_etiqueta="der")
tarea("sugerir", 800, YS_ARR, "Sugerir estilo", "servicio", w=130, h=56)
tarea("e99", 800, YS_ABA - 20, "Marcar revisión\nespecial (E-99)", "servicio", w=130, h=56)
compuerta("g_une", 925, YS)
tarea("registrar", 1065, YS, "Calcular rango de\nprecio y registrar\nla solicitud", "servicio", w=150, nuevo=True)

secuencia(("ini", "der"), ("validar", "izq"))
secuencia(("validar", "der"), ("g_datos", "izq"))
secuencia(("g_datos", "aba"), ("errores", "arr"), etiqueta="No", pos=(410, YS + 45))
secuencia(("errores", "izq"), ("reenvio", "der"))
secuencia(("reenvio", "izq"), ("validar", "aba"), por=((150, YS_ABA), (150, YS + 50), (260, YS + 50)))
secuencia(("g_datos", "der"), ("clasificar", "izq"), etiqueta="Sí")
secuencia(("clasificar", "der"), ("g_conf", "izq"))
secuencia(("g_conf", "arr"), ("sugerir", "izq"), por=((665, YS_ARR),), etiqueta="Sí", pos=(680, YS_ARR - 12))
secuencia(("g_conf", "aba"), ("e99", "izq"), por=((665, YS_ABA - 20),), etiqueta="No", pos=(680, YS_ABA - 32))
secuencia(("sugerir", "der"), ("g_une", "arr"), por=((925, YS_ARR),))
secuencia(("e99", "der"), ("g_une", "aba"), por=((925, YS_ABA - 20),))
secuencia(("g_une", "der"), ("registrar", "izq"))

# --- Tatuadora: decisión y acuerdo
tarea("revisar", 1225, YT, "Revisar solicitud y\nconfirmar o corregir\nel estilo", "usuario", w=150)
compuerta("g_acepta", 1365, YT, "¿Acepta?", lado_etiqueta="aba")
tarea("rechazar", 1365, YT_ARR, "Rechazar con motivo", "usuario", w=140, h=52)
evento("fin_rechazo", 1470, YT_ARR, "fin", "Solicitud\nrechazada")
tarea("acuerdo", 1515, YT, "Registrar acuerdo:\nprecio desde el rango,\nabono 30–40 %", "usuario", w=160, nuevo=True)
evento("abono", 1650, YT, "intermedio", "Abono pagado\n(fuera del sistema)", mensaje=True)
tarea("verificar", 1775, YT, "Verificar y\nregistrar abono", "usuario", w=130)

secuencia(("registrar", "der"), ("revisar", "aba"), por=((1225, YS),))
secuencia(("revisar", "der"), ("g_acepta", "izq"))
secuencia(("g_acepta", "arr"), ("rechazar", "aba"), etiqueta="No", pos=(1380, YT - 50))
secuencia(("rechazar", "der"), ("fin_rechazo", "izq"))
secuencia(("g_acepta", "der"), ("acuerdo", "izq"), etiqueta="Sí")
secuencia(("acuerdo", "der"), ("abono", "izq"))
secuencia(("abono", "der"), ("verificar", "izq"))

# --- Agenda, consentimiento y sesiones
tarea("agendar", 1905, YS, "Agendar sesión\nsin solapamiento", "servicio", w=140)
tarea("consent", 2040, YT, "Firmar consentimiento:\nficha del cliente y\ndeclaración", "usuario", w=160, nuevo=True)
tarea("sesion", 2190, YT, "Realizar sesión\nde tatuaje", None, w=130, subproceso=True)
compuerta("g_asistio", 2320, YT, "¿Asistió?", lado_etiqueta="aba")
tarea("inasist", 2320, YT_ARR, "Registrar inasistencia\ny destino del abono", "usuario", w=160, h=52)
compuerta("g_mas", 2450, YT, "¿Faltan\nsesiones?", lado_etiqueta="arr")

secuencia(("verificar", "der"), ("agendar", "arr"), por=((1905, YT),))
secuencia(("agendar", "der"), ("consent", "aba"), por=((2040, YS),))
secuencia(("consent", "der"), ("sesion", "izq"))
secuencia(("sesion", "der"), ("g_asistio", "izq"))
secuencia(("g_asistio", "arr"), ("inasist", "aba"), etiqueta="No", pos=(2335, YT - 50))
secuencia(("inasist", "izq"), ("agendar", "arr"), por=((1950, YT_ARR), (1950, YS - 120), (1905, YS - 120)),
          etiqueta="Reagendar", pos=(1990, YT_ARR - 10))
secuencia(("g_asistio", "der"), ("g_mas", "izq"), etiqueta="Sí")
secuencia(("g_mas", "aba"), ("agendar", "aba"), por=((2450, YS + 60 + 75), (1905, YS + 60 + 75)), etiqueta="Sí", pos=(2465, YT + 60))

# --- Pago final y cierre
tarea("pago", 2585, YT, "Registrar pago final", "usuario", w=130, h=56)
tarea("cierre", 2720, YS, "Verificar saldo = 0 y\nconsentimiento\ncompleto", "servicio", w=150, nuevo=True)
compuerta("g_cumple", 2860, YS, "¿Cumple?", lado_etiqueta="aba")
tarea("cerrar", 2990, YS, "Cerrar solicitud\n(solo consulta)", "servicio", w=130, nuevo=True)
tarea("portafolio", 3060, YT, "Publicar en portafolio\n(opcional, con\nautorización)", "usuario", w=150)
evento("fin", 3170, YT, "fin", "Trabajo\nterminado")

secuencia(("g_mas", "der"), ("pago", "izq"), etiqueta="No")
secuencia(("pago", "der"), ("cierre", "arr"), por=((2720, YT),))
secuencia(("cierre", "der"), ("g_cumple", "izq"))
secuencia(("g_cumple", "arr"), ("pago", "aba"), por=((2860, YS - 95), (2585, YS - 95)), etiqueta="No", pos=(2875, YS - 50))
secuencia(("g_cumple", "der"), ("cerrar", "izq"), etiqueta="Sí")
secuencia(("cerrar", "der"), ("portafolio", "aba"), por=((3060, YS),))
secuencia(("portafolio", "der"), ("fin", "izq"))

# --- Flujos de mensaje
mensaje((130, CLI_ABAJO), (130, YS - 18))
texto(184, 300, "solicitud + imagen;\ncorrección de datos", 10.5, ancla="start", estilo="italic")
mensaje((345, YS_ABA - 33), (345, CLI_ABAJO), "errores en español", "der")
mensaje((175, CLI_ABAJO), (175, YS_ABA - 18), "", "der")
mensaje((505, YS + 33), (505, ML_ARRIBA), "imagen", "izq", y_etiqueta=ML_ARRIBA - 22)
mensaje((555, ML_ARRIBA), (555, YS + 33), "7 confianzas + OOD", "der", y_etiqueta=ML_ARRIBA - 22)
mensaje((1065, YS - 33), (1065, CLI_ABAJO), "código y estimación\n(rango mín.–máx.)", "der")
mensaje((1365, YT_ARR - 26), (1365, CLI_ABAJO), "motivo", "der", y_etiqueta=122)
mensaje((1515, YT - 33), (1515, CLI_ABAJO), "acuerdo y abono", "der")
mensaje((1650, CLI_ABAJO), (1650, YT - 18), "comprobante", "der")
mensaje((2040, CLI_ABAJO), (2040, YT - 33), "ficha firmada", "der")
mensaje((2585, CLI_ABAJO), (2585, YT - 28), "pago final", "der")

# --- leyenda
lx, ly = 2380, Y_ML + 8
out.append(f'<rect x="{lx}" y="{ly}" width="820" height="64" fill="white" stroke="{SUAVE}" stroke-width="1"/>')
out.append(f'<rect x="{lx + 12}" y="{ly + 12}" width="26" height="16" rx="4" fill="#E8F5E9" stroke="{TINTA}"/>')
texto(lx + 46, ly + 20, "Tarea nueva o modificada en la entrega final", 11, ancla="start")
icono_usuario(lx + 25, ly + 44)
texto(lx + 46, ly + 46, "Tarea de usuario", 11, ancla="start")
icono_servicio(lx + 190, ly + 46)
texto(lx + 205, ly + 46, "Tarea de servicio (automática)", 11, ancla="start")
out.append(f'<line x1="{lx + 430}" y1="{ly + 46}" x2="{lx + 480}" y2="{ly + 46}" stroke="{TINTA}" stroke-dasharray="7,5" '
           f'marker-start="url(#origen)" marker-end="url(#abierta)"/>')
texto(lx + 490, ly + 46, "Flujo de mensaje", 11, ancla="start")
out.append(f'<line x1="{lx + 610}" y1="{ly + 46}" x2="{lx + 660}" y2="{ly + 46}" stroke="{TINTA}" marker-end="url(#flecha)"/>')
texto(lx + 670, ly + 46, "Flujo de secuencia", 11, ancla="start")

defs = f'''<defs>
<marker id="flecha" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{TINTA}"/></marker>
<marker id="abierta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="white" stroke="{TINTA}"/></marker>
<marker id="origen" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7"><circle cx="5" cy="5" r="4" fill="white" stroke="{TINTA}"/></marker>
</defs>'''
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, Helvetica, sans-serif">'
       f'{defs}<rect width="{W}" height="{H}" fill="white"/>'
       f'<text x="20" y="{H - 12}" font-size="12" fill="{SUAVE}">MTFlow — Proceso TO-BE (BPMN 2.0), actualizado a la implementación de noviembre de 2026. Pagos y comprobantes ocurren fuera del sistema; MTFlow solo los registra.</text>'
       + "".join(out) + "</svg>")
destino = Path(__file__).resolve().parents[1] / "docs" / "diagramas" / "09_BPMN_TO-BE.svg"
destino.write_text(svg, encoding="utf-8")
print(destino)
