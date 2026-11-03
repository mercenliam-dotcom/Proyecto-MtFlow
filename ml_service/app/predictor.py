"""
Predictores intercambiables.

- PredictorSimulado: devuelve probabilidades falsas pero DETERMINISTAS
  (la misma imagen siempre da el mismo resultado). Sirve para desarrollar y
  demostrar la web antes de tener el modelo entrenado.
- PredictorEfficientNet: carga los pesos entrenados (transfer learning sobre
  EfficientNet-B0) y hace la inferencia real. Se activa solo cuando existe
  el archivo de pesos.

Ambos reciben una imagen PIL ya validada y devuelven {clase: probabilidad}.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from PIL import Image

from . import config


class PredictorSimulado:
    version = "simulado-0.1"

    def predecir(self, img: Image.Image) -> dict[str, float]:
        miniatura = img.convert("RGB").resize((32, 32))
        semilla = hashlib.sha256(miniatura.tobytes()).digest()
        # Logits pseudoaleatorios a partir del hash; una clase "gana" con
        # margen para que se vean los tres estados de la recomendación.
        logits = [b / 255.0 * 3.0 for b in semilla[: len(config.CLASES)]]
        ganadora = semilla[10] % len(config.CLASES)
        logits[ganadora] += 1.5 + (semilla[11] / 255.0) * 4.0
        m = max(logits)
        exps = [math.exp(x - m) for x in logits]
        total = sum(exps)
        probs = [e / total for e in exps]
        # Redondeo que conserva la suma exacta en 1
        redondeadas = [round(p, 4) for p in probs]
        redondeadas[ganadora] = round(redondeadas[ganadora] + 1.0 - sum(redondeadas), 4)
        return dict(zip(config.CLASES, redondeadas))


class PredictorEfficientNet:
    """Inferencia real. Requiere torch y torchvision (requirements-modelo.txt)."""

    def __init__(self, ruta_pesos: Path):
        import torch
        from torchvision import models, transforms

        self.torch = torch
        modelo = models.efficientnet_b0(weights=None)
        entradas = modelo.classifier[1].in_features
        modelo.classifier[1] = torch.nn.Linear(entradas, len(config.CLASES))
        estado = torch.load(ruta_pesos, map_location="cpu", weights_only=True)
        modelo.load_state_dict(estado)
        modelo.eval()
        self.modelo = modelo
        # Mismo preprocesamiento que en validación durante el entrenamiento
        self.transformar = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self.version = f"efficientnet_b0:{ruta_pesos.name}"

    def predecir(self, img: Image.Image) -> dict[str, float]:
        x = self.transformar(img.convert("RGB")).unsqueeze(0)
        with self.torch.inference_mode():
            probs = self.torch.softmax(self.modelo(x), dim=1)[0].tolist()
        return {c: round(float(p), 6) for c, p in zip(config.CLASES, probs)}


def cargar_predictor():
    ruta = Path(config.MODELO_RUTA)
    if not config.FORZAR_STUB and ruta.is_file():
        return PredictorEfficientNet(ruta)
    return PredictorSimulado()
