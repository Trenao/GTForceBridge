"""Mapeamento: fontes (do ControlState) -> valores 0..1, histerese e tabela de teclas.

Fontes aceitas nos bindings:
    steering+   direção para a direita (0..1)      steering-   direção para a esquerda (0..1)
    throttle    acelerador (0..1)                  brake       freio (0..1)
    button:N    botão físico N do volante (1 = primeiro), vale 0 ou 1
"""
from __future__ import annotations


def source_value(state, source):
    """Valor 0..1 de uma fonte, ou None se a fonte for inválida/inexistente."""
    if not isinstance(source, str):
        return None
    src = source.strip().lower()
    if src == "steering+":
        return max(0.0, min(1.0, state.steering))
    if src == "steering-":
        return max(0.0, min(1.0, -state.steering))
    if src == "throttle":
        return max(0.0, min(1.0, state.throttle))
    if src == "brake":
        return max(0.0, min(1.0, state.brake))
    if src.startswith("button:"):
        try:
            n = int(src[7:])
        except ValueError:
            return None
        if n < 1:
            return None
        return 1.0 if n <= len(state.buttons) and state.buttons[n - 1] else 0.0
    return None


class Hysteresis:
    """Liga acima de 'on' e só desliga abaixo de 'off' (evita a tecla ficar piscando no limiar)."""

    def __init__(self, on=0.5, off=None):
        self.on = float(on)
        self.off = min(self.on, float(off)) if off is not None else self.on * 0.7
        self.active = False

    def update(self, value):
        if self.active:
            if value < self.off:
                self.active = False
        elif value >= self.on:
            self.active = True
        return self.active


# Scancodes (conjunto 1) -> (scancode, estendida). Scancode funciona com jogos DirectInput,
# onde códigos virtuais (VK) frequentemente são ignorados.
_LETTERS = dict(zip("abcdefghijklmnopqrstuvwxyz", [
    0x1E, 0x30, 0x2E, 0x20, 0x12, 0x21, 0x22, 0x23, 0x17, 0x24, 0x25, 0x26, 0x32,
    0x31, 0x18, 0x19, 0x10, 0x13, 0x1F, 0x14, 0x16, 0x2F, 0x11, 0x2D, 0x15, 0x2C]))
_DIGITS = dict(zip("1234567890", [0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B]))

SCANCODES = {k: (v, False) for k, v in {**_LETTERS, **_DIGITS}.items()}
SCANCODES.update({
    "space": (0x39, False), "enter": (0x1C, False), "esc": (0x01, False), "tab": (0x0F, False),
    "backspace": (0x0E, False), "shift": (0x2A, False), "rshift": (0x36, False),
    "ctrl": (0x1D, False), "alt": (0x38, False),
    "up": (0x48, True), "down": (0x50, True), "left": (0x4B, True), "right": (0x4D, True),
    "home": (0x47, True), "end": (0x4F, True), "pageup": (0x49, True), "pagedown": (0x51, True),
    "insert": (0x52, True), "delete": (0x53, True), "rctrl": (0x1D, True), "ralt": (0x38, True),
})
for _i in range(1, 11):
    SCANCODES[f"f{_i}"] = (0x3A + _i, False)
SCANCODES["f11"] = (0x57, False)
SCANCODES["f12"] = (0x58, False)


def resolve_key(name):
    """'a', 'Space', 'LEFT'... -> (scancode, estendida) ou None se não existir."""
    if not isinstance(name, str):
        return None
    return SCANCODES.get(name.strip().lower())
