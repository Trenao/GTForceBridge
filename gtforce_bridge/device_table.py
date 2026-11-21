"""Tabela de volantes Logitech conhecidos (VID 0x046D): nome, se tem motor de FFB e curso típico.

Ideia aproveitada do cp2077-wheel-mod (MIT): detectar o modelo e suas capacidades e só oferecer/mostrar
o que existe. A decisão real de FFB continua sendo a capacidade que o SDL reporta (haptic); esta tabela
é informativa (nome amigável e curso para diagnóstico).
"""
from __future__ import annotations

from typing import NamedTuple, Optional

LOGITECH_VID = 0x046D


class DeviceInfo(NamedTuple):
    pid: int
    name: str
    ffb: bool
    range_deg: int


_TABLE = [
    DeviceInfo(0xC291, "WingMan Formula Force", True, 240),
    DeviceInfo(0xC293, "WingMan Formula Force GP", True, 240),
    DeviceInfo(0xC294, "Driving Force", False, 240),
    DeviceInfo(0xC295, "Momo Force", True, 270),
    DeviceInfo(0xC298, "Driving Force Pro", True, 900),
    DeviceInfo(0xC299, "G25 Racing Wheel", True, 900),
    DeviceInfo(0xC29A, "Driving Force GT", True, 900),
    DeviceInfo(0xC29B, "G27 Racing Wheel", True, 900),
    DeviceInfo(0xC24F, "G29 Driving Force", True, 900),
    DeviceInfo(0xC260, "G29 Driving Force (modo PS)", True, 900),
    DeviceInfo(0xC262, "G920 Driving Force", True, 900),
    DeviceInfo(0xC266, "G923 (Xbox)", True, 900),
    DeviceInfo(0xC267, "G923 (PS/PC)", True, 900),
    DeviceInfo(0xCA03, "Momo Racing", True, 270),
    DeviceInfo(0xCA04, "Formula Vibration Feedback", True, 240),
]
BY_PID = {d.pid: d for d in _TABLE}


def lookup(vendor: int, product: int) -> Optional[DeviceInfo]:
    """Retorna a entrada da tabela ou None (volante desconhecido: segue funcionando normalmente)."""
    if vendor != LOGITECH_VID:
        return None
    return BY_PID.get(product)


def describe(vendor: int, product: int, haptic: bool) -> str:
    """Texto curto para logs: modelo, curso típico e coerência com o haptic reportado pelo SDL."""
    info = lookup(vendor, product)
    if info is None:
        return "modelo fora da tabela (segue com as capacidades reportadas pelo SDL)"
    txt = f"{info.name}, curso típico ~{info.range_deg}°"
    if info.ffb and not haptic:
        txt += " [aviso: deveria ter FFB mas o SDL não expôs haptic; feche G HUB/LGS/DXTweak]"
    elif not info.ffb and haptic:
        txt += " [SDL expõe haptic apesar da tabela indicar sem motor]"
    return txt
