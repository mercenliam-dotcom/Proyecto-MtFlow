@echo off
rem Abre el servicio ML y Django en dos ventanas y luego el navegador.
start "MTFlow - Servicio ML" cmd /k ""%~dp0iniciar-ml.bat""
timeout /t 3 /nobreak >nul
start "MTFlow - Django" cmd /k ""%~dp0iniciar-django.bat""
timeout /t 6 /nobreak >nul
start "" "http://127.0.0.1:8000/"
