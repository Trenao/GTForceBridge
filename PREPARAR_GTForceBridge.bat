@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Preparar GTForce Bridge
cd /d "%~dp0"

rem Uso: PREPARAR_GTForceBridge.bat [--xbox]
rem   --xbox  tambem instala requirements-xbox.txt (vgamepad, exige ViGEmBus)
rem   GTF_NOPAUSE=1 (variavel de ambiente) suprime o pause final (usado pelo compilar)

echo ==========================================
echo       PREPARACAO - GTForce Bridge
echo ==========================================
echo.

set "PYTHON_CMD="
set "WITH_XBOX="
if /i "%~1"=="--xbox" set "WITH_XBOX=1"
set "PY_CHECK=import sys,struct,tkinter,venv;sys.exit(0 if sys.version_info>=(3,10) and struct.calcsize('P')==8 else 1)"

if not exist "main.py" goto :err_main
if not exist "gtforce_bridge\" goto :err_pkg
if not exist "requirements.txt" goto :err_req

echo [1/5] Procurando Python 3.10+ 64 bits com tkinter...
call :find_python
if defined PYTHON_CMD goto :py_ok

echo Python adequado nao encontrado. Tentando instalar Python 3.12 pelo winget...
where winget >nul 2>&1
if errorlevel 1 goto :err_nopython
winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements
call :find_python
if defined PYTHON_CMD goto :py_ok
goto :err_nopython

:py_ok
echo Usando: %PYTHON_CMD%
%PYTHON_CMD% --version

echo.
echo [2/5] Ambiente virtual .venv...
if not exist ".venv\Scripts\python.exe" goto :make_venv
".venv\Scripts\python.exe" -c "%PY_CHECK%" >nul 2>&1
if not errorlevel 1 goto :venv_ok
echo .venv invalido ou quebrado - Python removido, pasta movida ou sem tkinter. Recriando...
rmdir /s /q ".venv" >nul 2>&1
if exist ".venv" goto :err_venv_locked
:make_venv
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto :err
if not exist ".venv\Scripts\python.exe" goto :err
goto :venv_done
:venv_ok
echo Ambiente virtual existente e valido; reutilizando.
:venv_done

echo.
echo [3/5] Atualizando pip, setuptools e wheel...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
if errorlevel 1 echo [AVISO] Nao foi possivel atualizar pip/setuptools/wheel - seguindo com as versoes atuais.

echo.
echo [4/5] Instalando requisitos...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :err
if not defined WITH_XBOX goto :skip_xbox
if not exist "requirements-xbox.txt" goto :skip_xbox
echo Instalando requisitos opcionais do Xbox virtual...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-xbox.txt
if errorlevel 1 goto :err
:skip_xbox

rem tk-0.1.0-py3-none-any.whl e o TensorKit (framework de deep learning), sem relacao com tkinter.
rem O projeto usa o tkinter da stdlib; o wheel nao e instalado e qualquer copia antiga e removida.
".venv\Scripts\python.exe" -m pip uninstall -y tk >nul 2>&1
if exist "tk-0.1.0-py3-none-any.whl" echo [INFO] tk-0.1.0-py3-none-any.whl ignorado: nao e usado pelo projeto.

echo.
echo [5/5] Verificando importacoes...
".venv\Scripts\python.exe" -c "import tkinter, sdl2, pystray; from PIL import Image; import gtforce_bridge.cli; print('OK: tkinter, SDL2, pystray, Pillow e gtforce_bridge carregam.')"
if errorlevel 1 goto :err

echo.
echo ==========================================
echo PREPARACAO CONCLUIDA!
echo Ambiente: .venv
echo Agora execute INICIAR_GTForceBridge.bat
echo ==========================================
if not defined GTF_NOPAUSE pause
exit /b 0

:find_python
set "PYTHON_CMD="
call :try py -3.12
call :try py -3.13
call :try py -3.11
call :try py -3.10
call :try py -3
call :try python
call :try "%LocalAppData%\Programs\Python\Python312\python.exe"
call :try "%LocalAppData%\Programs\Python\Python313\python.exe"
exit /b 0

:try
if defined PYTHON_CMD exit /b 0
%* -c "%PY_CHECK%" >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=%*"
exit /b 0

:err_main
echo [ERRO] main.py nao encontrado nesta pasta.
echo Coloque este BAT dentro da pasta do projeto - a que contem main.py.
echo O zip extrai em uma subpasta gtforce_bridge_v*; entre nela.
goto :err
:err_pkg
echo [ERRO] Pasta gtforce_bridge nao encontrada.
goto :err
:err_req
echo [ERRO] requirements.txt nao encontrado.
goto :err
:err_nopython
echo [ERRO] Nenhum Python 3.10+ 64 bits com tkinter foi encontrado e a instalacao automatica falhou.
echo Instale Python 3.12 64 bits em https://www.python.org/downloads/
echo Marque "Add Python to PATH" e mantenha "tcl/tk and IDLE" selecionado.
goto :err
:err_venv_locked
echo [ERRO] Nao foi possivel remover .venv - feche o GTForce Bridge e a bandeja e tente de novo.
goto :err

:err
echo.
echo [ERRO] A preparacao nao foi concluida.
if not defined GTF_NOPAUSE pause
exit /b 1
