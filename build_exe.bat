@echo off
chcp 65001 >nul
title AutoCFDI — Build del Ejecutable

REM ============================================================
REM  build_exe.bat
REM  Ejecutar UNA SOLA VEZ para generar AutoCFDI.exe
REM  Requiere Python + PyInstaller instalados en el equipo.
REM ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo   AutoCFDI — Generando ejecutable con PyInstaller
echo ============================================================
echo.

REM Verificar que Python está disponible
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado en PATH.
    echo         Instala Python 3.10+ y asegurate de marcarlo en PATH.
    pause
    exit /b 1
)

REM Instalar/actualizar dependencias de build
echo [1/4] Instalando dependencias...
pip install --quiet --upgrade pyinstaller
pip install --quiet pytest-html jinja2
pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Fallo al instalar dependencias.
    pause
    exit /b 1
)
echo       OK

REM Limpiar builds anteriores
echo [2/4] Limpiando builds anteriores...
if exist "build"  rmdir /s /q "build"
if exist "dist"   rmdir /s /q "dist"
echo       OK

REM Compilar con el spec file
echo [3/4] Compilando AutoCFDI.exe (puede tardar 2-5 minutos)...
python -m PyInstaller cfdi_auto.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller fallo. Revisa los mensajes anteriores.
    pause
    exit /b 1
)
echo       OK

REM Copiar archivos de usuario al directorio de distribución
echo [4/4] Copiando archivos de usuario a dist\AutoCFDI\...

REM config.ini
if not exist "dist\AutoCFDI\config" mkdir "dist\AutoCFDI\config"
copy /y "config\config.ini" "dist\AutoCFDI\config\config.ini" >nul

REM config.ini también en raíz (acceso directo para usuarios)
copy /y "config\config.ini" "dist\AutoCFDI\config.ini" >nul

REM pytest.ini (debe estar junto al exe para que pytest no use el del proyecto fuente)
copy /y "pytest.ini" "dist\AutoCFDI\pytest.ini" >nul

REM Carpeta data (Excels editables)
if not exist "dist\AutoCFDI\data" mkdir "dist\AutoCFDI\data"
xcopy /y /q "data\*.*" "dist\AutoCFDI\data\" >nul 2>&1

REM Carpetas de salida vacías
if not exist "dist\AutoCFDI\outputs" mkdir "dist\AutoCFDI\outputs"
if not exist "dist\AutoCFDI\logs"    mkdir "dist\AutoCFDI\logs"
if not exist "dist\AutoCFDI\reports" mkdir "dist\AutoCFDI\reports"

REM .bat de ejecución
copy /y "Ejecutar_Pruebas.bat" "dist\AutoCFDI\Ejecutar_Pruebas.bat" >nul

echo       OK
echo.
echo ============================================================
echo   BUILD EXITOSO
echo ============================================================
echo.
echo   Distribuible listo en:
echo     %~dp0dist\AutoCFDI\
echo.
echo   Estructura final:
echo     AutoCFDI\
echo     ├── AutoCFDI.exe
echo     ├── Ejecutar_Pruebas.bat
echo     ├── config.ini          ^<-- editable por usuario
echo     ├── config\config.ini   ^<-- copia de respaldo
echo     ├── data\               ^<-- Excels editables
echo     ├── outputs\            ^<-- resultados por ejecucion
echo     ├── logs\               ^<-- logs de ejecucion
echo     └── reports\            ^<-- reportes HTML
echo.
echo   Para distribuir: comprime dist\AutoCFDI\ en un ZIP y entregalo.
echo.
pause
