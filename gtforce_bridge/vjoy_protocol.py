"""Protocolo FFB do vJoy: tipo do callback, constantes de pacote/efeito e structs ctypes."""
from __future__ import annotations

import ctypes
import math
from ctypes import Structure, c_int, c_int32, c_ubyte, c_uint, c_ushort, c_void_p


WINFUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
FFB_CB = WINFUNCTYPE(None, c_void_p, c_void_p)

PT_EFFREP, PT_ENVREP, PT_CONDREP, PT_PRIDREP, PT_CONSTREP, PT_RAMPREP = 0x01, 0x02, 0x03, 0x04, 0x05, 0x06
PT_EFOPREP, PT_BLKFRREP, PT_CTRLREP, PT_GAINREP = 0x0A, 0x0B, 0x0C, 0x0D
PT_NEWEFREP, PT_BLKLDREP = 0x11, 0x12

ET_NONE, ET_CONST, ET_RAMP, ET_SQR, ET_SINE, ET_TRI, ET_STUP, ET_STDN = 0, 1, 2, 3, 4, 5, 6, 7
ET_SPRNG, ET_DMPR, ET_INRT, ET_FRCTN, ET_CSTM = 8, 9, 10, 11, 12

EFF_START, EFF_SOLO, EFF_STOP = 1, 2, 3

CTRL_ENACT, CTRL_DISACT, CTRL_STOPALL, CTRL_DEVRST, CTRL_DEVPAUSE, CTRL_DEVCONT = 1, 2, 3, 4, 5, 6

ET_NAMES = {0: "NONE", 1: "CONST", 2: "RAMP", 3: "SQR", 4: "SINE", 5: "TRI", 6: "STUP", 7: "STDN",
            8: "SPRING", 9: "DAMPER", 10: "INERTIA", 11: "FRICTION", 12: "CUSTOM"}


class FFB_EFF_REPORT(Structure):
    """Layout do vJoy 2.2.x (njz3), conforme vjoyinterface.h: tem StartDelay e
    AxesEnabledDirection; Direction/DirY são WORD (polar 0x0000-0x7FFF = 0-360 graus)."""
    _fields_ = [("EffectBlockIndex", c_ubyte), ("EffectType", c_int),
                ("Duration", c_ushort), ("TrigerRpt", c_ushort),
                ("SamplePrd", c_ushort), ("StartDelay", c_ushort),
                ("Gain", c_ubyte), ("TrigerBtn", c_ubyte),
                ("AxesEnabledDirection", c_ubyte), ("Polar", c_int),
                ("Direction", c_ushort), ("DirY", c_ushort)]


class FFB_EFF_REPORT_LEGACY(Structure):
    """Layout do vJoy 2.1.x (shauleiz): sem StartDelay; Direction/DirY são BYTE (0-255 = 0-360 graus)."""
    _fields_ = [("EffectBlockIndex", c_ubyte), ("EffectType", c_int),
                ("Duration", c_ushort), ("TrigerRpt", c_ushort),
                ("SamplePrd", c_ushort), ("Gain", c_ubyte),
                ("TrigerBtn", c_ubyte), ("Polar", c_int),
                ("Direction", c_ubyte), ("DirY", c_ubyte)]


DIR_MAX_NEW = 0x7FFF   # vjoyinterface.h: "Polar direction: (0x00-0x7FFF correspond to 0-360°)"
DIR_MAX_LEGACY = 255   # PID 1.0: Direction 0-255 -> 0-360 graus


def uses_new_layout(dll):
    """vJoy 2.2.x exporta Ffb_h_EffectBlockIndex/Ffb_h_CreateNewEffect (ausentes no 2.1.x)."""
    return hasattr(dll, "Ffb_h_EffectBlockIndex") or hasattr(dll, "Ffb_h_CreateNewEffect")


def report_class(dll):
    return FFB_EFF_REPORT if uses_new_layout(dll) else FFB_EFF_REPORT_LEGACY


def direction_to_byte(direction, new_layout):
    """Normaliza a direção polar para a escala 0-255 usada pelo tradutor."""
    if new_layout:
        return int(round(max(0, min(DIR_MAX_NEW, int(direction))) * 255.0 / DIR_MAX_NEW))
    return int(direction) & 0xFF


def cartesian_x(raw, new_layout):
    """Componente X quando Polar=0 (vjoyinterface.h: DirX positivo = direita; negativos em complemento de 2)."""
    raw = int(raw)
    bits = 16 if new_layout else 8
    raw &= (1 << bits) - 1
    return raw - (1 << bits) if raw >= (1 << (bits - 1)) else raw


def s16(v):
    """Estende o sinal de um valor de 16 bits que o vJoy entrega SEM sinal.

    Capturas reais (Assetto Corsa Rally, Wreckfest 2): `Magnitude` (LONG, -10000..10000 no header) chega como 0..10000
    para o lado positivo e 55536..65535 para o negativo (= valor int16 lido como unsigned), nunca como negativo.
    Faixa legítima é ±10000, então 32768..65535 só pode ser um int16 negativo: v - 65536."""
    v = int(v)
    return v - 65536 if 32768 <= v <= 65535 else v


def direction_ambiguous(polar, direction_byte, polar_zero="east"):
    """True se a direção polar cai perto do eixo Y sob a convenção escolhida (lado indefinido => sinal fixo +1)."""
    if not polar:
        return False
    ang = direction_byte / 255.0 * 2.0 * math.pi
    return abs(math.sin(ang) if polar_zero == "north" else math.cos(ang)) < 0.1


def direction_sign(polar, direction_byte, dirx, polar_zero="east"):
    """Lado (+1 = direita, -1 = esquerda) que a DIREÇÃO do efeito indica. Única fonte da regra: tradutor e --ffb-dump.

    Polar: só o hemisfério X decide; perto do eixo Y (|componente| < 0.1) a direção é indefinida e vale +1.
    polar_zero "east" = ângulo medido a partir de +X (cos); "north" = convenção DirectInput (0° = norte, 90° = leste; sen).
    Cartesiano (Polar=0): DirX negativo = esquerda (vjoyinterface.h)."""
    if polar:
        ang = direction_byte / 255.0 * 2.0 * math.pi
        comp = math.sin(ang) if polar_zero == "north" else math.cos(ang)
        return 1.0 if abs(comp) < 0.1 else (-1.0 if comp < 0.0 else 1.0)
    return -1.0 if (dirx is not None and dirx < 0) else 1.0


DURATION_INFINITE = 0xFFFF   # vjoyinterface.h: "Value in milliseconds. 0xFFFF means infinite"
LOOP_INFINITE = 255          # PID 1.0: Loop Count 255 = repetir sem parar


class FFB_EFF_CONSTANT(Structure):
    _fields_ = [("EffectBlockIndex", c_ubyte), ("Magnitude", c_int32)]


class FFB_EFF_RAMP(Structure):
    _fields_ = [("EffectBlockIndex", c_ubyte), ("Start", c_int32), ("End", c_int32)]


class FFB_EFF_COND(Structure):
    _fields_ = [("EffectBlockIndex", c_ubyte), ("isY", c_int),
                ("CenterPointOffset", c_int32), ("PosCoeff", c_int32),
                ("NegCoeff", c_int32), ("PosSatur", c_uint),
                ("NegSatur", c_uint), ("DeadBand", c_int32)]


class FFB_EFF_PERIOD(Structure):
    _fields_ = [("EffectBlockIndex", c_ubyte), ("Magnitude", c_uint),
                ("Offset", c_int32), ("Phase", c_uint), ("Period", c_uint)]


class FFB_EFF_OP(Structure):
    _fields_ = [("EffectBlockIndex", c_ubyte), ("EffectOp", c_int),
                ("LoopCount", c_ubyte)]
