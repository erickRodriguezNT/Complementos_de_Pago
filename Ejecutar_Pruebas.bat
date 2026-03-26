@echo off
chcp 65001 >nul
title AutoCFDI — Ejecución de Pruebas
cd /d "%~dp0"

if not exist "AutoCFDI.exe" (
    echo [ERROR] No se encontro AutoCFDI.exe en esta carpeta.
    pause
    exit /b 1
)

:MENU
cls
echo.
echo  ============================================================
echo    AutoCFDI — Seleccion de Escenarios
echo  ============================================================
echo.
echo   [ 1 ] ESC 01 - IVA 16
echo   [ 2 ] ESC 02 - IVA 0
echo   [ 3 ] ESC 03 - IVA 16 e IVA 0
echo   [ 4 ] ESC 04 - IEPS 0.53  IEPS 0.30  IEPS 0.265
echo   [ 5 ] ESC 05 - IVA 16 e ISR Retencion 0.15
echo   [ 6 ] ESC 06 - IVA 16 Retencion IEPS 53 IEPS 30
echo   [ 7 ] ESC 07 - IVA 16 IVA 0 IEPS 0.08
echo   [ 8 ] ESC 08 - IVA 16 IVA 0 IEPS 0.08 IEPS 0.09
echo   [ 9 ] ESC 09 - IVA 16 IVA 16 Ret ISR 0.15 Ret
echo   [10 ] ESC 10 - IVA 16 IVA 0 IEPS 0.09 Ret IVA Ret IEPS Ret ISR
echo   [11 ] ESC 11 - IVA 8 (Hyatt)
echo   [12 ] ESC 12 - IVA 8 e IVA 0 (Hyatt)
echo   [13 ] ESC 13 - IVA 16 IVA 8 e IVA 0 (Hyatt)
echo   [14 ] ESC 14 - IVA 8 IVA 0 IEPS 0.08 Ret IVA Ret IEPS ISH 8 (Hyatt)
echo   [15 ] ESC 15 - IVA 16 IEPS 0.09 IEPS 0.30 Ret IVA ISH 0.09 ISH 0.08 (Hyatt)
echo   [16 ] ESC 16 - IVA 16 IVA 8 IVA 0 IEPS 0.08 IEPS 0.53 IEPS 30 (Hyatt)
echo   [17 ] ESC 17 - IVA 8 IVA 0 IEPS 0.08 IEPS 0.53 Ret IEPS ISH 0.08 (Hyatt)
echo   [18 ] ESC 18 - IVA 16 IVA 8 IVA 0 IEPS 0.53 IEPS 0.265 Ret IEPS Ret ISR Ret ISH (Hyatt)
echo   [19 ] ESC 19 - IVA 16 USD Tipo de Cambio
echo   [20 ] ESC 20 - IVA 16 USD Tipo de Cambio v2
echo   [21 ] ESC 21 - PPD USD CMP MXN IVA16 IVA0 IEPS8 IEPS9
echo   [22 ] ESC 22 - PPD USD CMP MXN IVA16
echo.
echo   [23 ] Seleccionar escenarios especificos (ej: 1 3 5)
echo   [24 ] Correr pruebas completas (todos los escenarios)
echo    [0 ] Salir
echo.
echo  ============================================================
set /p "OPCION=  Escribe el numero de opcion y presiona ENTER: "

if "%OPCION%"=="0"  exit /b 0

REM ── Opciones individuales 1-22 ────────────────────────────────────────────
if "%OPCION%"=="1"  goto RUN_SINGLE
if "%OPCION%"=="2"  goto RUN_SINGLE
if "%OPCION%"=="3"  goto RUN_SINGLE
if "%OPCION%"=="4"  goto RUN_SINGLE
if "%OPCION%"=="5"  goto RUN_SINGLE
if "%OPCION%"=="6"  goto RUN_SINGLE
if "%OPCION%"=="7"  goto RUN_SINGLE
if "%OPCION%"=="8"  goto RUN_SINGLE
if "%OPCION%"=="9"  goto RUN_SINGLE
if "%OPCION%"=="10" goto RUN_SINGLE
if "%OPCION%"=="11" goto RUN_SINGLE
if "%OPCION%"=="12" goto RUN_SINGLE
if "%OPCION%"=="13" goto RUN_SINGLE
if "%OPCION%"=="14" goto RUN_SINGLE
if "%OPCION%"=="15" goto RUN_SINGLE
if "%OPCION%"=="16" goto RUN_SINGLE
if "%OPCION%"=="17" goto RUN_SINGLE
if "%OPCION%"=="18" goto RUN_SINGLE
if "%OPCION%"=="19" goto RUN_SINGLE
if "%OPCION%"=="20" goto RUN_SINGLE
if "%OPCION%"=="21" goto RUN_SINGLE
if "%OPCION%"=="22" goto RUN_SINGLE
if "%OPCION%"=="23" goto RUN_MULTI
if "%OPCION%"=="24" goto RUN_ALL

echo.
echo  [ERROR] Opcion no valida. Intenta de nuevo.
timeout /t 2 >nul
goto MENU

REM ── Correr un escenario individual ────────────────────────────────────────
:RUN_SINGLE
set "ESC_ID=%OPCION%"
if %ESC_ID% LSS 10 set "ESC_ID=0%OPCION%"
echo.
echo  Ejecutando ESC %OPCION%...
AutoCFDI.exe --escenario %OPCION%
goto RESULTADO

REM ── Opcion 23: elegir escenarios especificos ──────────────────────────────
:RUN_MULTI
echo.
echo  Escribe los numeros de escenario separados por espacios.
echo  Ejemplo: 1 3 5 12 19
echo.
set /p "NUMS=  Escenarios: "
if "%NUMS%"=="" goto MENU
echo.
echo  Ejecutando escenarios: %NUMS%
AutoCFDI.exe --escenarios %NUMS%
goto RESULTADO

REM ── Opcion 24: todos ───────────────────────────────────────────────────────
:RUN_ALL
echo.
echo  Ejecutando todos los escenarios (1 al 22)...
AutoCFDI.exe
goto RESULTADO

REM ── Resultado final ────────────────────────────────────────────────────────
:RESULTADO
set EXIT_CODE=%ERRORLEVEL%
echo.
echo  ============================================================
if %EXIT_CODE%==0 (
    echo    RESULTADO: Pruebas completadas exitosamente.
) else (
    echo    RESULTADO: Algunas pruebas fallaron. Revisa outputs\
)
echo  ============================================================
echo.
echo  Presiona cualquier tecla para volver al menu...
pause >nul
goto MENU
