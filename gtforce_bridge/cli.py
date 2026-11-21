"""Linha de comando: --run, --list, --monitor, --ffb-test, --ffb-autocal, --apply, --reset-autocal, --gui (sem argumentos abre a GUI). Também: --no-ffb, --ffb-dump."""
from __future__ import annotations

import argparse
import json
import sys

from .autocal import cmd_ffb_autocal
from .autocal_profile import reset_autocal
from .bridge import cmd_run
from .config import DEFAULT_CONFIG, load_config
from .diag import cmd_list, cmd_monitor
from .ffb_test import cmd_ffb_test
from .gui import launch_gui
from .logsetup import setup_logging
from .paths import CONFIG_PATH


def main():
    ap = argparse.ArgumentParser(description="Ponte GT Force -> vJoy com FFB")
    ap.add_argument("--list", action="store_true", help="lista dispositivos e capacidades de haptic")
    ap.add_argument("--monitor", action="store_true", help="mostra eixos/botões em tempo real")
    ap.add_argument("--ffb-test", action="store_true", help="testa o FFB do volante via SDL")
    ap.add_argument("--ffb-autocal", action="store_true", help="roda autocalibração de FFB (não aplica)")
    ap.add_argument("--apply", action="store_true", help="com --ffb-autocal: grava fatores em config.json")
    ap.add_argument("--reset-autocal", action="store_true", help="zera fatores e perfis de autocalibração FFB")
    ap.add_argument("--run", action="store_true", help="executa a ponte")
    ap.add_argument("--no-ffb", action="store_true", help="com --run: só entrada, sem force feedback")
    ap.add_argument("--ffb-dump", action="store_true", help="loga o que o jogo manda ao vJoy (não toca no volante)")
    ap.add_argument("--verbose", action="store_true", help="loga os pacotes FFB do jogo")
    ap.add_argument("--gui", action="store_true", help="abre a interface gráfica")
    ap.add_argument("--tray", action="store_true", help="abre a GUI já oculta na bandeja (usado pela inicialização com o Windows)")
    args = ap.parse_args()

    if args.gui or args.tray or len(sys.argv) == 1:
        launch_gui(start_hidden=args.tray); return
    if args.list:
        cmd_list(); return
    cfg = load_config()
    if args.run or args.ffb_dump or args.ffb_test or args.ffb_autocal:
        setup_logging(cfg.get("logging", {}), "ffb-dump" if args.ffb_dump else "run" if args.run else "ffb")
    if args.reset_autocal:
        reset_autocal(cfg["ffb"])
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print("Autocalibração FFB zerada; fatores padrão restaurados.")
    elif args.monitor:
        cmd_monitor(cfg)
    elif args.ffb_test:
        cmd_ffb_test(cfg)
    elif args.ffb_autocal:
        cmd_ffb_autocal(cfg, apply=args.apply, verbose=args.verbose)
    elif args.ffb_dump:
        cmd_run(cfg, True, dump=True)
    elif args.run:
        cmd_run(cfg, args.verbose, ffb=not args.no_ffb)
    else:
        launch_gui()
