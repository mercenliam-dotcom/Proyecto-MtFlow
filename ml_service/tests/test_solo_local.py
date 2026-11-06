import pytest
from app import config
from app.predictor import cargar_predictor, PredictorNoDisponible
from app.decision import construir_respuesta

@pytest.mark.parametrize('modo', ['auto', 'simulado', 'roboflow_workflow', 'local_pytorch'])
def test_rechaza_backends_retirados(monkeypatch, modo):
    monkeypatch.setattr(config, 'MODO_PREDICTOR', modo)
    with pytest.raises(ValueError, match='solo admite'):
        cargar_predictor()

def test_fallo_local_no_envia_imagen_ni_simula(monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    from PIL import Image
    import io
    from types import SimpleNamespace
    def fallo(datos):
        raise PredictorNoDisponible('Error local')
    monkeypatch.setattr(main, 'predictor', SimpleNamespace(version='efficientnet_b0:v2:test', predecir_bytes=fallo))
    contenido=io.BytesIO()
    Image.new('RGB',(224,224)).save(contenido,'PNG')
    r=TestClient(main.app).post('/clasificar',headers={'X-API-Key':config.API_KEY}, files={'imagen':('a.png',contenido.getvalue(),'image/png')})
    assert r.status_code == 503

def test_rechaza_vector_parcial():
    with pytest.raises(PredictorNoDisponible):
        construir_respuesta('efficientnet_b0:v2:test', {f'E-{i:02}':.05 for i in range(1,8)})
