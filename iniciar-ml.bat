@echo off
rem Lanza el servicio de clasificacion (FastAPI + uvicorn) en http://127.0.0.1:8001 con .venv-ml.
title MTFlow - Servicio ML
cd /d "%~dp0ml_service"
set "PY=%~dp0.venv-ml\Scripts\python.exe"
if not exist "%PY%" (
  echo No encuentro el entorno .venv-ml en la carpeta del proyecto.
  pause
  exit /b 1
)
if not exist ".env" (
  echo Falta ml_service\.env. Copia .env.example como .env y pon la misma ML_SERVICE_API_KEY de config\.env.
  pause
  exit /b 1
)
echo Servicio ML en http://127.0.0.1:8001   (Ctrl+C para detener)
"%PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8001
pause
