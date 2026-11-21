@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Compilar GTForce Bridge
cd /d "%~dp0"

echo ==========================================
echo       COMPILADOR - GTForce Bridge
echo ==========================================
echo.

if not exist "main.py" goto :err_main
if not exist "gtforce_bridge\" goto :err_pkg
if not exist "requirements.txt" goto :err_req

rem exe em execucao trava a limpeza de dist\ (PermissionError no PyInstaller)
tasklist /fi "imagename eq GTForceBridge.exe" /nh 2>nul | find /i "GTForceBridge.exe" >nul
if not errorlevel 1 goto :err_running

set "PY=.venv\Scripts\python.exe"
set "PY_CHECK=import tkinter, sdl2, pystray; from PIL import Image; import gtforce_bridge.cli"
set "HOOK=%~dp0_gtforce_rthook.py"

echo [1/5] Verificando ambiente .venv...
if not exist "%PY%" goto :prepare
"%PY%" -c "%PY_CHECK%" >nul 2>&1
if not errorlevel 1 goto :env_ok
:prepare
echo Ambiente ausente ou incompleto. Executando PREPARAR_GTForceBridge.bat...
if not exist "PREPARAR_GTForceBridge.bat" goto :err_noprep
set "GTF_NOPAUSE=1"
call "PREPARAR_GTForceBridge.bat"
set "PREP_RC=%errorlevel%"
set "GTF_NOPAUSE="
if not "%PREP_RC%"=="0" goto :erro
if not exist "%PY%" goto :erro
:env_ok

echo.
echo [2/5] Instalando/atualizando PyInstaller...
"%PY%" -m pip install --disable-pip-version-check --upgrade pyinstaller
if errorlevel 1 echo [AVISO] Nao foi possivel atualizar o PyInstaller - usando a versao instalada.
"%PY%" -c "import PyInstaller" >nul 2>&1
if errorlevel 1 goto :erro

rem Pacotes opcionais so entram no build se estiverem instalados no .venv.
set "EXTRA="
"%PY%" -c "import sdl2dll" >nul 2>&1
if not errorlevel 1 set "EXTRA=%EXTRA% --collect-all sdl2dll"
if errorlevel 1 echo [AVISO] sdl2dll ausente - SDL2.dll nao sera empacotada.
"%PY%" -c "import vgamepad" >nul 2>&1
if not errorlevel 1 set "EXTRA=%EXTRA% --collect-all vgamepad"

echo.
echo [3/5] Gerando runtime hook UTF-8 e stdout em linha...
rem O exe e reexecutado pela GUI como subprocesso com stdout em pipe. Sem este hook: acentos
rem saem em cp1252 (a GUI le UTF-8) e o stdout fica em bloco, atrasando o log na tela.
> "%HOOK%" echo(import os, sys
>> "%HOOK%" echo(os.environ.setdefault("PYTHONUTF8", "1")
>> "%HOOK%" echo(os.environ.setdefault("PYTHONIOENCODING", "utf-8")
>> "%HOOK%" echo(def _fix(name, fd):
>> "%HOOK%" echo(    s = getattr(sys, name, None)
>> "%HOOK%" echo(    try:
>> "%HOOK%" echo(        if s is None:
>> "%HOOK%" echo(            setattr(sys, name, open(fd, "w", encoding="utf-8", errors="replace", buffering=1, closefd=False))
>> "%HOOK%" echo(        else:
>> "%HOOK%" echo(            s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
>> "%HOOK%" echo(    except Exception:
>> "%HOOK%" echo(        pass
>> "%HOOK%" echo(_fix("stdout", 1)
>> "%HOOK%" echo(_fix("stderr", 2)
if not exist "%HOOK%" goto :erro

echo.
echo [4/5] Gerando executavel...
"%PY%" -m PyInstaller ^
 --noconfirm ^
 --clean ^
 --onedir ^
 --windowed ^
 --name "GTForceBridge" ^
 --paths "." ^
 --runtime-hook "%HOOK%" ^
 --collect-all gtforce_bridge ^
 --collect-all sdl2 ^
 --collect-all pystray ^
 --collect-all PIL ^
 %EXTRA% ^
 "main.py"
set "BUILD_RC=%errorlevel%"
del "%HOOK%" >nul 2>&1
if not "%BUILD_RC%"=="0" goto :erro

echo.
echo [5/5] Verificando saida...
if not exist "dist\GTForceBridge\GTForceBridge.exe" goto :erro
where /r "dist\GTForceBridge" SDL2.dll >nul 2>&1
if errorlevel 1 echo [AVISO] SDL2.dll nao encontrada em dist\GTForceBridge - o volante nao sera detectado.

echo.
echo ==========================================
echo BUILD CONCLUIDO!
echo Executavel: dist\GTForceBridge\GTForceBridge.exe
echo config.json, profiles e logs ficam ao lado do exe.
echo vJoy e HidHide continuam sendo instalados a parte.
echo ==========================================
echo.
pause
exit /b 0

:err_main
echo [ERRO] main.py nao encontrado.
echo Coloque este BAT na raiz do projeto - a pasta gtforce_bridge_v* extraida do zip.
goto :erro
:err_pkg
echo [ERRO] Pasta gtforce_bridge nao encontrada.
goto :erro
:err_req
echo [ERRO] requirements.txt nao encontrado.
goto :erro
:err_running
echo [ERRO] GTForceBridge.exe esta em execucao. Feche a janela e a bandeja e tente de novo.
goto :erro
:err_noprep
echo [ERRO] PREPARAR_GTForceBridge.bat nao encontrado na mesma pasta.
goto :erro

:erro
if exist "%HOOK%" del "%HOOK%" >nul 2>&1
echo.
echo [ERRO] A compilacao falhou. Verifique as mensagens acima.
pause
exit /b 1
