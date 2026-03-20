@echo off
chcp 65001 > nul
echo ============================================================
echo   CFDI Automation - Factura PPD + Complementos de Pago
echo ============================================================
echo.

:: Go to the script's directory
cd /d "%~dp0"

:: Check Python is available
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no encontrado. Instala Python 3.10+ y agrégalo al PATH.
    pause
    exit /b 1
)

:: Install dependencies if needed
echo Verificando dependencias...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias.
    pause
    exit /b 1
)

echo.
echo Ejecutando pruebas...
echo.
python run_tests.py

echo.
echo Ejecucion finalizada. Revisa la carpeta reports\ para el Excel y el HTML.
pause
