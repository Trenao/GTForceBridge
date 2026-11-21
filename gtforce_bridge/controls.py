"""Estado dos controles já processado (calibração + zona morta + curva), independente de destino.

É a fronteira entre ENTRADA (volante) e SAÍDA (vJoy hoje; Xbox/teclado no futuro): o
loop calcula um ControlState e entrega a todas as saídas (ver sinks.py).
"""
from __future__ import annotations

from dataclasses import dataclass

from .curves import apply_curve, norm_pedal, norm_steering


@dataclass
class ControlState:
    steering: float = 0.0              # -1.0 .. +1.0
    throttle: float = 0.0              #  0.0 ..  1.0
    brake: float = 0.0                 #  0.0 ..  1.0
    buttons: tuple = ()                # bool por botão físico (posição 0 = botão 1)


def compute_controls(wheel, cfg) -> ControlState:
    """Lê o volante e aplica calibração/zona morta/curva conforme o config."""
    ax = cfg["axes"]
    cal = cfg["calibration"]
    steer = apply_curve(norm_steering(wheel.axis(ax["steering"]), cal["steering"]), cfg["steering"])

    if cfg["pedals_mode"] == "combined":
        raw = wheel.axis(ax["pedals"])
        if cfg["throttle"].get("invert"):
            raw = -raw
        thr, brk = max(0.0, raw), max(0.0, -raw)
    else:
        thr = norm_pedal(wheel.axis(ax["pedals"]), cal["throttle"])
        brk = norm_pedal(wheel.axis(ax["brake"]), cal["brake"])
        if cfg["throttle"].get("invert"):
            thr = 1.0 - thr
        if cfg["brake"].get("invert"):
            brk = 1.0 - brk
    thr = abs(apply_curve(thr, {**cfg["throttle"], "invert": False}))
    brk = abs(apply_curve(brk, {**cfg["brake"], "invert": False}))

    buttons = ()
    if cfg.get("buttons_map_all"):
        buttons = tuple(bool(wheel.button(i)) for i in range(min(wheel.n_buttons, 32)))
    return ControlState(steer, thr, brk, buttons)
