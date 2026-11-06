"""Carga e inferencia HTTP reales, sin guardar solicitudes ni enviar datos fuera."""
import io
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ml_service'))
os.environ['ML_PREDICTOR']='local'
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app import config

assert config.API_KEY, 'Configurar ML_SERVICE_API_KEY antes de probar.'
with TestClient(app) as cliente:
    salud=cliente.get('/salud').json()
    assert salud['version_modelo'].startswith('efficientnet_b0:v2:')
    datos=io.BytesIO()
    Image.new('RGB',(300,300),(150,80,40)).save(datos,'PNG')
    respuesta=cliente.post('/clasificar',headers={'X-API-Key':config.API_KEY},files={'imagen':('prueba.png',datos.getvalue(),'image/png')})
    assert respuesta.status_code==200, respuesta.status_code
    resultado=respuesta.json()
    assert len(resultado['confianzas'])==7
    assert abs(sum(resultado['confianzas'].values())-1)<1e-4
    assert resultado['umbral_confianza']==.6
    print('OK: carga de EfficientNetB0 v2 e inferencia real con siete probabilidades; umbral 60 %.')
    print('Imagen sintetica: comprueba ejecucion, no exactitud del clasificador.')
