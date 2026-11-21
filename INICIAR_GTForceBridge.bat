@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Argumentos opcionais sao repassados ao main.py, ex.: INICIAR_GTForceBridge.bat --gui --tray

set "VPY=%~dp0.venv\Scripts\python.exe"
set "VPYW=%~dp0.venv\Scripts\pythonw.exe"
set "CHECK_LOG=%TEMP%\gtforce_start_check.txt"

if not exist "%VPYW%" goto :no_env
if not exist "%~dp0main.py" goto :no_main

rem UTF-8 no processo e nos filhos (a GUI le o stdout da ponte como UTF-8; sem isso os acentos viram lixo).
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

rem pythonw nao mostra erro de import; valida antes com python.exe.
"%VPY%" -c "import tkinter, sdl2, pystray; from PIL import Image; import gtforce_bridge.cli" 2>"%CHECK_LOG%"
if errorlevel 1 goto :broken
del "%CHECK_LOG%" >nul 2>&1

rem pythonw.exe inicia a interface sem console vinculado.
start "" "%VPYW%" "%~dp0main.py" %*
exit /b 0

:no_env
echo Ambiente virtual nao encontrado.
echo Execute PREPARAR_GTForceBridge.bat primeiro.
pause
exit /b 1

:no_main
echo main.py nao encontrado em %~dp0
pause
exit /b 1

:broken
echo [ERRO] O ambiente virtual nao carrega as dependencias. Detalhe:
echo.
type "%CHECK_LOG%"
echo.
echo Execute PREPARAR_GTForceBridge.bat para reparar o ambiente.
pause
exit /b 1
