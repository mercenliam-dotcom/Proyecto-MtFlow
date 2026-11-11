"""OOD ligado al modelo: KNN v3 y lectura compatible de centroides v2."""
import hashlib
import json
from pathlib import Path

import numpy as np


class DetectorOOD:
    def __init__(self, ruta: Path, modelo_sha256: str, clases: list[str]):
        ruta = Path(ruta)
        datos = ruta.read_bytes()
        cfg = json.loads(datos.decode("utf-8-sig"))
        self.metodo = cfg.get("metodo")
        if (self.metodo not in ("centroides_train_coseno_valid", "knn_coseno_train_valid_v1")
                or cfg.get("modelo_sha256") != modelo_sha256 or cfg.get("clases") != clases
                or cfg.get("capa") != "global_average_pooling2d"):
            raise ValueError("La calibración OOD no corresponde al modelo, clases o método actual.")
        self.capa = cfg["capa"]
        self.version = hashlib.sha256(datos).hexdigest()
        self.umbral = cfg.get("umbral_distancia")
        if (isinstance(self.umbral, bool) or not isinstance(self.umbral, (int, float))
                or not np.isfinite(self.umbral) or not 0 <= self.umbral <= 2):
            raise ValueError("Umbral OOD inválido.")
        if self.metodo == "centroides_train_coseno_valid":
            self.centroides = np.asarray(cfg["centroides"], dtype=np.float32)
            if (self.centroides.shape != (7, 1280) or not np.isfinite(self.centroides).all()
                    or not np.allclose(np.linalg.norm(self.centroides, axis=1), 1, atol=1e-4)):
                raise ValueError("Centroides OOD inválidos.")
            return
        if (cfg.get("model_version") != "v3" or cfg.get("embedding_dimension") != 1280
                or cfg.get("preprocessing") != {"image_size": [224, 224], "input_range": [0, 255],
                    "resize": "Pillow bilinear con orientación EXIF aplicada"}):
            raise ValueError("Configuración KNN incompatible con el modelo v3.")
        referencia = ruta.with_name("referencias_knn_v3.npz")
        if hashlib.sha256(referencia.read_bytes()).hexdigest() != cfg.get("referencias_sha256"):
            raise ValueError("La huella SHA-256 de las referencias OOD no coincide.")
        self.k, cantidad = cfg.get("k"), cfg.get("n_train")
        if (type(self.k) is not int or type(cantidad) is not int
                or not 1 <= self.k <= cantidad):
            raise ValueError("Cantidad de vecinos KNN inválida.")
        with np.load(referencia, allow_pickle=False) as archivo:
            referencias = np.asarray(archivo["embeddings"], dtype=np.float64)
            etiquetas, rutas = archivo["labels"], archivo["paths"]
            if (referencias.shape != (cantidad, 1280) or not np.isfinite(referencias).all()
                    or etiquetas.shape != (cantidad,) or etiquetas.dtype.kind not in "iu"
                    or set(etiquetas.tolist()) != set(range(7))
                    or rutas.shape != (cantidad,) or rutas.dtype.kind not in "US"
                    or len(set(rutas.tolist())) != cantidad):
                raise ValueError("Referencias KNN inválidas.")
        normas = np.linalg.norm(referencias, axis=1, keepdims=True)
        if not np.isfinite(normas).all() or np.any(normas <= 0):
            raise ValueError("Referencias KNN de norma cero o inválida.")
        # Misma normalización float64 y referencias float32 serializadas que Colab.
        self.referencias = referencias / normas

    def evaluar(self, embedding):
        tipo = np.float32 if self.metodo == "centroides_train_coseno_valid" else np.float64
        e = np.asarray(embedding, dtype=tipo)
        norma = np.linalg.norm(e)
        if e.shape != (1280,) or not np.isfinite(e).all() or not np.isfinite(norma) or norma <= 0:
            raise ValueError("Embedding OOD inválido.")
        if self.metodo == "centroides_train_coseno_valid":
            distancia = float(np.clip(1 - np.max((e / norma) @ self.centroides.T), 0, 2))
        else:
            distancias = np.clip(1 - (e / norma) @ self.referencias.T, 0, 2)
            distancia = float(np.partition(distancias, self.k - 1)[self.k - 1])
        return {"version": self.version, "distancia": distancia, "umbral": self.umbral,
                "fuera_distribucion": distancia > self.umbral}
