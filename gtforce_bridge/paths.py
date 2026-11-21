"""Caminhos de arquivos do projeto (config, telemetria, perfis, sinal de parada, relatório de autocal)."""
from __future__ import annotations

import os
import sys

if getattr(sys, "frozen", False):
    # executável empacotado (PyInstaller): arquivos ao lado do .exe
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # raiz do projeto = pasta que contém main.py e o pacote gtforce_bridge/
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
TELEMETRY_PATH = os.path.join(BASE_DIR, "telemetry.json")
STOP_PATH = os.path.join(BASE_DIR, "bridge.stop")
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
AUTOCAL_REPORT_PATH = os.path.join(BASE_DIR, "ffb_autocal_report.json")
