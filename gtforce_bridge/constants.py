"""Constantes compartilhadas: nomes de eixos do vJoy e escalas de magnitude de FFB."""
from __future__ import annotations


AXIS_USAGE = {
    "X": 0x30, "Y": 0x31, "Z": 0x32,
    "RX": 0x33, "RY": 0x34, "RZ": 0x35,
    "SL0": 0x36, "SL1": 0x37,
    "SLIDER": 0x36, "SLIDER0": 0x36, "SLIDER1": 0x37,
}

SCALE_DINPUT = 10000.0
SCALE_16BIT = 32767.0
SCALE_8BIT = 255.0
SCALE_HYSTERESIS = 1.15
SCALE_SAMPLES_MIN = 3
