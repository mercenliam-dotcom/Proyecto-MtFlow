"""Tarifa ficticia v1 para prototipo. No es un tarifario aprobado ni un modelo ML."""
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

VERSION_TARIFA = "demo-2026-11-v1"
BASES_CLP = {"pequeno": (35000, 60000), "mediano": (65000, 110000), "grande": (110000, 190000)}


def estimar(datos):
    if datos["cobertura"] or datos["tamano"] == "especial" or datos["zona"] == "otra":
        return {"manual": True, "version": VERSION_TARIFA,
                "motivo": "Por el tamaño, la zona o la cobertura, necesitamos una revisión de la tatuadora."}
    minimo, maximo = BASES_CLP[datos["tamano"]]
    factor = Decimal("1")
    motivos = ["Tamaño solicitado"]
    if datos["color"] == "color":
        factor += Decimal("0.20")
        motivos.append("Color: ajuste provisional de 20 %")
    if datos["detalle"] == "alto":
        factor += Decimal("0.25")
        motivos.append("Detalle alto declarado: ajuste provisional de 25 %")
    if datos["zona"] in ("costillas", "pecho"):
        factor += Decimal("0.15")
        motivos.append("Zona: ajuste provisional de 15 %")
    # Redondear hacia fuera evita fingir precisión. Dinero calculado sin float.
    bajo = int((Decimal(minimo) * factor / 5000).to_integral_value(rounding=ROUND_FLOOR)) * 5000
    alto = int((Decimal(maximo) * factor / 5000).to_integral_value(rounding=ROUND_CEILING)) * 5000
    return {"manual": False, "minimo": bajo, "maximo": alto,
            "minimo_texto": f"{bajo:,}".replace(",", "."),
            "maximo_texto": f"{alto:,}".replace(",", "."),
            "motivos": motivos, "version": VERSION_TARIFA}
