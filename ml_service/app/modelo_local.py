"""Inferencia local con el preprocesamiento de cada bundle EfficientNetB0."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import threading

from PIL import Image, ImageOps

from .predictor import PredictorNoDisponible, _clave_nombre

CLASES_LOCALES = {
    "Alto contraste": "E-01", "Anime": "E-02", "Cibersigilismo": "E-03",
    "Lettering": "E-04", "Linea Fina": "E-05", "Ornamentos": "E-06",
    "Tribal-Neotribal": "E-07",
}

VERSIONES_KERAS = ("v1", "v2", "v3")
REDIMENSIONADO_V2 = "Pillow bilinear con orientación EXIF aplicada"


def ruta_pesos(directorio: Path, version: str) -> Path:
    return directorio / f"MTFlow_EfficientNetB0_{version}.keras"


def hay_pesos_keras(directorio: Path) -> bool:
    return any(ruta_pesos(directorio, version).is_file() for version in VERSIONES_KERAS)


def leer_bundle(directorio: Path):
    """Verifica metadatos y SHA-256 antes de deserializar el modelo."""
    directorio = Path(directorio)
    cfg = json.loads((directorio / "training_config.json").read_text(encoding="utf-8-sig"))
    clases = json.loads((directorio / "class_names.json").read_text(encoding="utf-8-sig"))
    if not isinstance(clases, list) or not all(isinstance(c, str) for c in clases):
        raise ValueError("class_names.json debe contener una lista de clases.")
    mapa = {_clave_nombre(nombre): codigo for nombre, codigo in CLASES_LOCALES.items()}
    codigos = [mapa.get(_clave_nombre(nombre)) for nombre in clases]
    if (clases != cfg.get("class_ids") or len(codigos) != 7
            or set(codigos) != set(CLASES_LOCALES.values())):
        raise ValueError("El bundle debe contener exactamente los siete estilos y su orden de entrenamiento.")
    version = cfg.get("model_version", "v1")
    if version not in VERSIONES_KERAS:
        raise ValueError("Versión de EfficientNetB0 no compatible.")
    resize = REDIMENSIONADO_V2 if version in ("v2", "v3") else "bilinear"
    if (cfg.get("architecture") != "EfficientNetB0" or cfg.get("image_size") != [224, 224]
            or cfg.get("input_range") != [0, 255] or cfg.get("resize") != resize
            or cfg.get("color_mode", "rgb") != "rgb"):
        raise ValueError("Preprocesamiento incompatible: se requiere EfficientNetB0, RGB 224x224, bilinear y rango 0..255.")
    ruta = ruta_pesos(directorio, version)
    with ruta.open("rb") as archivo:
        resumen = hashlib.sha256()
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            resumen.update(bloque)
        digest = resumen.hexdigest()
    if digest != (directorio / "model_sha256.txt").read_text(encoding="utf-8-sig").strip().lower():
        raise ValueError("La huella SHA-256 del modelo no coincide con el bundle.")
    return ruta, codigos, digest


def validar_puntuaciones(valores, codigos):
    if (len(valores) != len(codigos) or not all(math.isfinite(p) and 0 <= p <= 1 for p in valores)
            or not math.isclose(sum(valores), 1.0, abs_tol=1e-4)):
        raise PredictorNoDisponible("El modelo devolvió probabilidades inválidas.")
    # No redondear: 0.59999998 debe seguir por debajo de la exigencia de 0.60.
    return dict(zip(codigos, (float(p) for p in valores)))


class PredictorEfficientNetKeras:
    def __init__(self, directorio: Path):
        ruta, self.codigos, digest = leer_bundle(directorio)
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")
        os.environ.setdefault("TF_NUM_INTRAOP_THREADS", "4")
        os.environ.setdefault("TF_NUM_INTEROP_THREADS", "2")
        import tensorflow as tf

        self.tf = tf
        self.modelo = tf.keras.models.load_model(ruta, compile=False, safe_mode=True)
        if tuple(self.modelo.input_shape[1:]) != (224, 224, 3) or self.modelo.output_shape[-1] != 7:
            raise ValueError("El modelo no tiene la entrada RGB 224x224 y las siete salidas esperadas.")
        self._version_bundle = ruta.stem.rsplit("_", 1)[-1]
        self.version = f"efficientnet_b0:{self._version_bundle}:{digest}"
        from . import config
        self.detector_ood = None
        self.extractor_ood = None
        if config.OOD_ACTIVO:
            from .ood import DetectorOOD
            clases = json.loads((Path(directorio) / "class_names.json").read_text(encoding="utf-8-sig"))
            self.detector_ood = DetectorOOD(config.OOD_CALIBRACION, digest, clases)
            self.extractor_ood = tf.keras.Model(
                inputs=self.modelo.inputs,
                outputs=[self.modelo.get_layer(self.detector_ood.capa).output, self.modelo.output],
            )
            self.version += f":ood:{self.detector_ood.version[:16]}"
        self._lock = threading.Lock()

    def preparar_bytes(self, datos: bytes):
        tf = self.tf
        if self._version_bundle in ("v2", "v3"):
            import numpy as np

            with Image.open(io.BytesIO(datos)) as imagen:
                rgb = ImageOps.exif_transpose(imagen).convert("RGB")
                pixels = np.asarray(rgb.resize((224, 224), Image.Resampling.BILINEAR))
            return tf.convert_to_tensor(pixels[None, ...])

        with Image.open(io.BytesIO(datos)) as imagen:
            orientacion = imagen.getexif().get(274, 1)
        # Decodificación TensorFlow igual a la utilizada en entrenamiento y en el
        # prototipo: no convertir primero con Pillow ni volver a comprimir JPEG.
        pixels = tf.io.decode_image(datos, channels=3, expand_animations=False)
        if orientacion == 2:
            pixels = tf.image.flip_left_right(pixels)
        elif orientacion == 3:
            pixels = tf.image.rot90(pixels, 2)
        elif orientacion == 4:
            pixels = tf.image.flip_up_down(pixels)
        elif orientacion == 5:
            pixels = tf.transpose(pixels, (1, 0, 2))
        elif orientacion == 6:
            pixels = tf.image.rot90(pixels, 3)
        elif orientacion == 7:
            pixels = tf.reverse(tf.transpose(pixels, (1, 0, 2)), (0, 1))
        elif orientacion == 8:
            pixels = tf.image.rot90(pixels, 1)
        # El reescalado está dentro del modelo: SIN /255, SIN CenterCrop.
        return tf.image.resize(pixels, (224, 224), method="bilinear", antialias=False)[None, ...]

    def predecir_bytes(self, datos: bytes) -> dict[str, float]:
        return self.analizar_bytes(datos)[0]

    def analizar_bytes(self, datos: bytes):
        """Una sola pasada para las siete probabilidades y el embedding OOD."""
        try:
            with self._lock:
                batch = self.preparar_bytes(datos)
                ood = None
                if self.extractor_ood is not None:
                    embedding, probabilidades = self.extractor_ood([batch], training=False)
                    valores = probabilidades.numpy()[0].tolist()
                    ood = self.detector_ood.evaluar(embedding.numpy()[0])
                else:
                    valores = self.modelo(batch, training=False).numpy()[0].tolist()
            return validar_puntuaciones(valores, self.codigos), ood
        except (self.tf.errors.OpError, ValueError, OSError) as exc:
            raise PredictorNoDisponible("No se pudo ejecutar el modelo local.") from exc
