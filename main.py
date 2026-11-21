#!/usr/bin/env python3
"""Ponto de entrada: python main.py [--run|--list|--monitor|--ffb-test|--ffb-autocal|--gui ...]
Sem argumentos abre a interface gráfica."""
import sys

from gtforce_bridge.cli import main

if __name__ == "__main__":
    sys.exit(main())
