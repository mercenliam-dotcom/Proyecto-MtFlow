"""Reevalúa test/OOD congelados y perturbaciones sin ajustar pesos ni umbrales."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CASOS = ("original", "lado_512", "jpeg_40", "luz_70", "luz_130", "giro_5", "flujo_web")


def leer_csv(ruta):
    with Path(ruta).open(encoding="utf-8-sig", newline="") as archivo:
        return list(csv.DictReader(archivo))


def huella(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def wilson(correctos, n):
    if not n:
        return None
    z, p = 1.959963984540054, correctos / n
    centro = (p + z*z/(2*n)) / (1 + z*z/n)
    radio = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / (1 + z*z/n)
    return [centro-radio, centro+radio]


def transformar(datos, caso):
    if caso == "original":
        return datos
    with Image.open(io.BytesIO(datos)) as origen:
        imagen = ImageOps.exif_transpose(origen).convert("RGB")
    try:
        cambio = imagen
        if caso == "lado_512":
            imagen.thumbnail((512, 512), Image.Resampling.LANCZOS)
        elif caso == "luz_70":
            cambio = ImageEnhance.Brightness(imagen).enhance(.7)
        elif caso == "luz_130":
            cambio = ImageEnhance.Brightness(imagen).enhance(1.3)
        elif caso == "giro_5":
            cambio = imagen.rotate(5, resample=Image.Resampling.BICUBIC, fillcolor="white")
        try:
            with io.BytesIO() as buffer:
                cambio.save(buffer, format="JPEG" if caso == "jpeg_40" else "PNG", **({"quality": 40} if caso == "jpeg_40" else {}))
                return buffer.getvalue()
        finally:
            if cambio is not imagen:
                cambio.close()
    finally:
        imagen.close()


def resumir(filas, clases):
    id_total = [r for r in filas if r["grupo"] == "ID"]
    ood_total = [r for r in filas if r["grupo"] == "OOD"]
    id_ = [r for r in id_total if r["estado"] == "evaluada"]
    ood = [r for r in ood_total if r["estado"] == "evaluada"]
    automaticas = [r for r in id_ if r["sugerencia"] != "E-99"]
    matriz = np.zeros((7, 7), dtype=int)
    for r in id_:
        matriz[clases.index(r["real"]), clases.index(r["ganador"])] += 1
    f1, por_clase = [], []
    for i, clase in enumerate(clases):
        tp, reales, asignadas = int(matriz[i, i]), int(matriz[i].sum()), int(matriz[:, i].sum())
        score = 2*tp/(reales+asignadas) if reales+asignadas else 0
        f1.append(score)
        propias = [r for r in id_ if r["real"] == clase]
        auto = [r for r in propias if r["sugerencia"] != "E-99"]
        por_clase.append(dict(clase=clase, n=reales, aciertos=tp, f1=score,
            automaticas=len(auto), errores_automaticos=sum(not r["correcta"] for r in auto)))
    aciertos = sum(r["correcta"] for r in id_)
    auto_aciertos = sum(r["correcta"] for r in automaticas)
    rechazos = sum(r["fuera_distribucion"] for r in ood)
    auroc = None
    if id_ and ood:
        diferencias = np.array([r["distancia"] for r in ood])[:, None] - np.array([r["distancia"] for r in id_])[None, :]
        auroc = float(((diferencias > 0) + .5*(diferencias == 0)).mean())
    return dict(id_n=len(id_total), id_evaluadas=len(id_), id_bloqueadas_entrada=len(id_total)-len(id_),
        aciertos=aciertos, accuracy=aciertos/len(id_) if id_ else None, accuracy_ic95=wilson(aciertos, len(id_)),
        macro_f1=float(np.mean(f1)), automaticas=len(automaticas),
        cobertura=len(automaticas)/len(id_total), auto_aciertos=auto_aciertos,
        precision_automatica=auto_aciertos/len(automaticas) if automaticas else None,
        precision_automatica_ic95=wilson(auto_aciertos, len(automaticas)),
        errores_automaticos=len(automaticas)-auto_aciertos,
        errores_confianza_90=sum(not r["correcta"] and r["confianza"] >= .9 for r in automaticas),
        id_rechazadas_ood=sum(r["fuera_distribucion"] for r in id_),
        id_revision_baja_confianza=sum(r["motivo"] == "confianza_insuficiente" for r in id_),
        ood_n=len(ood_total), ood_evaluadas=len(ood), ood_bloqueadas_entrada=len(ood_total)-len(ood),
        ood_rechazadas=rechazos, ood_rechazo=rechazos/len(ood) if ood else None,
        ood_rechazo_ic95=wilson(rechazos, len(ood)),
        ood_sugerencias_incorrectas=sum(r["sugerencia"] != "E-99" for r in ood),
        auroc_ood=auroc, matriz_confusion=matriz.tolist(), por_clase=por_clase)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--ood", type=Path, required=True, help="Colección con fuentes_licencias.csv")
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    args.salida.mkdir(parents=True, exist_ok=True)
    bundle = ROOT / "ml_service/modelos/efficientnet_b0_v3"
    os.environ.update(ML_PREDICTOR="local", MTFLOW_MODEL_DIR=str(bundle), MTFLOW_OOD_ENABLED="1",
        MTFLOW_OOD_CALIBRATION=str(bundle / "ood/calibracion_ood_v3.json"))
    sys.path[:0] = [str(ROOT / "ml_service"), str(ROOT / "config")]
    manifest = leer_csv(bundle / "dataset_manifest.csv")
    test = [r for r in manifest if r["split"] == "test"]
    ajuste = [r for r in manifest if r["split"] in ("train", "valid")]
    assert len(test) == 80
    for campo in ("sha256_bytes", "sha256_input224"):
        assert not {r[campo] for r in test} & {r[campo] for r in ajuste}, f"Solapamiento {campo}"
    fuentes = leer_csv(args.ood / "fuentes_licencias.csv")
    assert len(fuentes) == 80
    muestras = [dict(id=r["source_id"], grupo="ID", real=r["class"], ruta=str(args.dataset / r["path"]),
        sha256=r["sha256_bytes"], categoria=r["class"]) for r in test]
    muestras += [dict(id=r["id"], grupo="OOD", real="OOD", ruta=str(args.ood / r["path"]),
        sha256=r["sha256_bytes"], categoria=r["category"]) for r in fuentes]
    for muestra in muestras:
        assert huella(muestra["ruta"]) == muestra["sha256"], f"Imagen modificada: {muestra['id']}"
    clases = json.loads((bundle / "class_names.json").read_text(encoding="utf-8-sig"))
    codigos = {f"E-{i+1:02}": c for i, c in enumerate(clases)}
    plan = dict(creada_utc=datetime.now(timezone.utc).isoformat(), casos=CASOS,
        imagenes_originales=160, combinaciones_previstas=160*len(CASOS),
        pesos_sha256=huella(bundle / "MTFlow_EfficientNetB0_v3.keras"),
        calibracion_sha256=huella(bundle / "ood/calibracion_ood_v3.json"),
        manifest_sha256=huella(bundle / "dataset_manifest.csv"),
        umbral_confianza=.6, umbral_ood=.4379139110950403,
        origen_reutilizado=True, ajuste_de_umbrales=False,
        sin_solapamiento_exacto_ni_input224_con_train_valid=True,
        codigo={p.name: huella(p) for p in (ROOT / "ml_service/app").glob("*.py")}, muestras=muestras)
    (args.salida / "plan_congelado.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    from app.predictor import cargar_predictor
    from app.decision import construir_respuesta
    predictor = cargar_predictor()
    from django.conf import settings
    if not settings.configured:
        settings.configure(IMAGEN_MAX_BYTES=10*1024*1024, IMAGEN_MAX_PIXELES=40_000_000,
            IMAGEN_LADO_MIN_PX=224, IMAGEN_LADO_MAX_PX=8000, IMAGEN_NITIDEZ_MIN=40)
    from django.core.exceptions import ValidationError
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.nucleo.imagenes import validar_imagen
    filas, resumentotal = [], {}
    base_resultados = {}
    inicio = time.monotonic()
    campos = ["id", "grupo", "real", "categoria", "caso", "estado", "ganador", "correcta",
        "confianza", "sugerencia", "motivo", "fuera_distribucion", "distancia", "latencia_ms",
        "cambia_ganador", "cambia_decision", *codigos]
    with (args.salida / "predicciones.csv").open("w", encoding="utf-8-sig", newline="") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=campos)
        writer.writeheader()
        for caso in CASOS:
            propias = []
            for i, muestra in enumerate(muestras, 1):
                datos = Path(muestra["ruta"]).read_bytes()
                fila = {k: muestra[k] for k in ("id", "grupo", "real", "categoria")}
                fila.update(caso=caso, estado="evaluada")
                if caso == "flujo_web":
                    try:
                        v = validar_imagen(SimpleUploadedFile("foto.jpg", datos, content_type="image/jpeg"))
                        datos = v.archivo.read()
                    except ValidationError as error:
                        fila.update(estado="bloqueada_entrada", motivo=error.code)
                else:
                    datos = transformar(datos, caso)
                if fila["estado"] == "evaluada":
                    t0 = time.monotonic()
                    vector, ood = predictor.analizar_bytes(datos)
                    respuesta = construir_respuesta(predictor.version, vector, ood)
                    ganador = max(vector, key=vector.get)
                    fila.update(ganador=codigos[ganador], correcta=codigos[ganador] == muestra["real"],
                        confianza=respuesta["confianza_maxima"], sugerencia=respuesta["estilo_sugerido"],
                        motivo=respuesta["motivo_abstencion"] or "", fuera_distribucion=ood["fuera_distribucion"],
                        distancia=ood["distancia"], latencia_ms=1000*(time.monotonic()-t0), **vector)
                    if caso == "original":
                        base_resultados[muestra["id"]] = fila.copy()
                    original = base_resultados[muestra["id"]]
                    fila.update(cambia_ganador=fila["ganador"] != original["ganador"],
                        cambia_decision=fila["sugerencia"] != original["sugerencia"])
                writer.writerow(fila)
                filas.append(fila)
                propias.append(fila)
                if i % 40 == 0:
                    archivo.flush()
                    print(f"{caso}: {i}/160; total {len(filas)}/{plan['combinaciones_previstas']}; {time.monotonic()-inicio:.1f} s", flush=True)
            resumen = resumir(propias, clases)
            evaluadas = [r for r in propias if r["estado"] == "evaluada"]
            resumen["cambios_ganador_id"] = sum(r["cambia_ganador"] for r in evaluadas if r["grupo"] == "ID")
            resumen["cambios_decision_id"] = sum(r["cambia_decision"] for r in evaluadas if r["grupo"] == "ID")
            resumentotal[caso] = resumen
            (args.salida / "resumen.json").write_text(json.dumps(resumentotal, indent=2, ensure_ascii=False), encoding="utf-8")
    errores = [r for r in filas if r["grupo"] == "ID" and r["estado"] == "evaluada" and not r["correcta"]]
    with (args.salida / "errores.csv").open("w", encoding="utf-8-sig", newline="") as archivo:
        writer = csv.DictWriter(archivo, fieldnames=campos)
        writer.writeheader()
        writer.writerows(errores)
    print(json.dumps(resumentotal["original"], ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
