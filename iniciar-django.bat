@echo off
rem Lanza Django en http://127.0.0.1:8000 usando el entorno .venv (no hace falta activarlo).
title MTFlow - Django
cd /d "%~dp0config"
set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo No encuentro el entorno .venv en la carpeta del proyecto.
  pause
  exit /b 1
)
echo Aplicando migraciones pendientes...
"%PY%" manage.py migrate --noinput
if errorlevel 1 (
  echo Las migraciones fallaron. Revisa el mensaje de arriba.
  pause
  exit /b 1
)
echo.
echo Django en http://127.0.0.1:8000   (Ctrl+C para detener)
"%PY%" manage.py runserver 127.0.0.1:8000
pause
