"""Curvas de entrada: normalização de calibração, zona morta, expo/ganho e conversão para o range do vJoy."""
from __future__ import annotations


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def norm_steering(raw, cal):
    lo, c, hi = cal.get("min", -1.0), cal.get("center", 0.0), cal.get("max", 1.0)
    span = max((hi - c) if raw >= c else (c - lo), 0.05)
    return clamp((raw - c) / span, -1.0, 1.0)


def norm_pedal(raw, cal):
    lo, hi = cal.get("min", -1.0), cal.get("max", 1.0)
    span = hi - lo
    if abs(span) < 0.05:
        span = 0.05 if span >= 0 else -0.05
    return clamp((raw - lo) / span, 0.0, 1.0)


def apply_curve(x, p):
    if p.get("invert"):
        x = -x
    s = 1.0 if x >= 0 else -1.0
    a = abs(x)
    dz = clamp(p.get("deadzone", 0.0), 0.0, 0.95)
    if a <= dz:
        return 0.0
    a = (a - dz) / (1.0 - dz)
    expo = clamp(p.get("expo", 0.0), 0.0, 1.0)
    a = (1.0 - expo) * a + expo * a ** 3
    a = min(1.0, a * p.get("gain", 1.0))
    return s * a


def to_vjoy(v):
    return int(clamp((v + 1.0) * 0.5 * 32768, 1, 32768))


def to_vjoy_pedal(v):
    return int(clamp(v * 32768, 1, 32768))
