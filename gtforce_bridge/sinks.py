"""Saídas (sinks): recebem o ControlState e o publicam em algum lugar.

Hoje só existe VJoySink. Para emular um controle Xbox (ViGEm) ou teclado, crie outra
subclasse de OutputSink e acrescente-a à lista de saídas em bridge.cmd_run: o resto
(leitura do volante, calibração, FFB, GUI) não precisa mudar.
"""
from __future__ import annotations

import ctypes
import sys
import time

from .curves import to_vjoy, to_vjoy_pedal
from .mapping import Hysteresis, resolve_key, source_value


class OutputSink:
    name = "saída"

    def send(self, state) -> None:           # publica um ControlState
        raise NotImplementedError

    def neutral(self) -> None:               # volta ao neutro (volante sumiu / encerrando)
        pass

    def close(self) -> None:
        pass


class VJoySink(OutputSink):
    """Publica eixos/botões num device vJoy. Falhas do vJoy NÃO derrubam a ponte:
    registra (com limite de frequência) e tenta readquirir o device a cada ~1 s."""

    name = "vJoy"
    LOG_EVERY_S = 5.0
    RETRY_EVERY_S = 1.0

    def __init__(self, vjoy, cfg, log=print, clock=time.monotonic):
        self.vjoy, self.cfg, self.log, self.clock = vjoy, cfg, log, clock
        self.failures = 0
        self._last_log = -1e9
        self._last_retry = -1e9
        self._broken = False

    def send(self, st) -> None:
        if not self.cfg.get("outputs", {}).get("vjoy", {}).get("enabled", True):
            return
        va = self.cfg["vjoy_axes"]
        try:
            self.vjoy.set_axis(va["steering"], to_vjoy(st.steering))
            self.vjoy.set_axis(va["throttle"], to_vjoy_pedal(st.throttle))
            self.vjoy.set_axis(va["brake"], to_vjoy_pedal(st.brake))
            for i, pressed in enumerate(st.buttons[:32]):
                self.vjoy.set_button(i + 1, pressed)
        except RuntimeError as exc:
            self._fail(exc)
            return
        if self._broken:
            self._broken = False
            self.log("[vjoy] device recuperado.")

    def _fail(self, exc) -> None:
        self.failures += 1
        self._broken = True
        now = self.clock()
        if now - self._last_log >= self.LOG_EVERY_S:
            self._last_log = now
            self.log(f"[vjoy] falha ao enviar ({exc}); tentando readquirir o device…")
        if now - self._last_retry >= self.RETRY_EVERY_S:
            self._last_retry = now
            reacquire = getattr(self.vjoy, "reacquire", None)
            if reacquire is not None and reacquire():
                self.log("[vjoy] device readquirido.")

    def neutral(self) -> None:
        va = self.cfg["vjoy_axes"]
        try:
            self.vjoy.set_axis(va["steering"], to_vjoy(0.0))
            self.vjoy.set_axis(va["throttle"], to_vjoy_pedal(0.0))
            self.vjoy.set_axis(va["brake"], to_vjoy_pedal(0.0))
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.vjoy.close()
        except Exception as exc:
            self.log(f"[cleanup] falha ao liberar vJoy: {exc}")


# ───────────────────────────── teclado (SendInput) ─────────────────────────────
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_KEYBOARD = 1


# Tipos de tamanho FIXO (LONG/DWORD do Windows = 32 bits; ULONG_PTR = tamanho do ponteiro):
# assim o layout é o do Windows e pode ser conferido nos testes em qualquer sistema.
_LONG, _DWORD, _WORD, _ULONG_PTR = ctypes.c_int32, ctypes.c_uint32, ctypes.c_uint16, ctypes.c_size_t


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", _LONG), ("dy", _LONG), ("mouseData", _DWORD),
                ("dwFlags", _DWORD), ("time", _DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", _WORD), ("wScan", _WORD), ("dwFlags", _DWORD),
                ("time", _DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _INPUT_UNION(ctypes.Union):
    # o MOUSEINPUT precisa estar na união: define o tamanho correto da struct INPUT
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", _DWORD), ("u", _INPUT_UNION)]


def make_key_input(code, down):
    """INPUT do SendInput para (scancode, estendida) apertando/soltando."""
    scan, ext = code
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if ext else 0) | (0 if down else KEYEVENTF_KEYUP)
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = _KEYBDINPUT(0, scan, flags, 0, 0)
    return inp


class WinKeyInjector:
    """Injeta teclas no Windows via SendInput (por scancode)."""

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("saída de teclado só funciona no Windows")
        self._send = ctypes.windll.user32.SendInput

    def key(self, code, down):
        inp = make_key_input(code, down)
        if self._send(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
            raise OSError("SendInput falhou (janela com privilégio maior? execute a ponte como administrador)")


class KeyboardSink(OutputSink):
    """Converte o ControlState em teclas, conforme outputs.keyboard.bindings.

    Cada binding: {"source": "steering-", "key": "left", "on": 0.35, "off": 0.25}.
    Várias fontes na mesma tecla = OU. Ao desligar a saída, perder o volante ou
    encerrar, todas as teclas seguradas são SOLTAS (nunca fica tecla presa).
    """

    name = "teclado"

    def __init__(self, cfg, log=print, injector_factory=WinKeyInjector):
        self.cfg, self.log, self._factory = cfg, log, injector_factory
        self._inj = None
        self._inj_failed = False
        self._held = {}            # (scan, ext) -> True enquanto pressionada
        self._hyst = {}            # índice do binding -> (on, off, Hysteresis)
        self._warned = set()

    def _warn(self, key, msg):
        if key not in self._warned:
            self._warned.add(key)
            self.log(f"[teclado] {msg}")

    def _injector(self):
        if self._inj is None and not self._inj_failed:
            try:
                self._inj = self._factory()
            except Exception as exc:
                self._inj_failed = True
                self.log(f"[teclado] indisponível: {exc}")
        return self._inj

    def _release_all(self):
        if self._inj is None:
            return
        for code, down in list(self._held.items()):
            if down:
                try:
                    self._inj.key(code, False)
                except Exception:
                    pass
                self._held[code] = False

    def send(self, st) -> None:
        conf = self.cfg.get("outputs", {}).get("keyboard", {})
        if not conf.get("enabled"):
            self._release_all()
            return
        inj = self._injector()
        if inj is None:
            return
        wanted = {}
        for i, b in enumerate(conf.get("bindings") or []):
            code = resolve_key(b.get("key"))
            val = source_value(st, b.get("source"))
            if code is None:
                self._warn(("key", i), f"tecla desconhecida no binding {i + 1}: {b.get('key')!r} (ignorado)")
                continue
            if val is None:
                self._warn(("src", i), f"fonte desconhecida no binding {i + 1}: {b.get('source')!r} (ignorado)")
                continue
            on = float(b.get("on", 0.5))
            off = b.get("off")
            cached = self._hyst.get(i)
            if cached is None or cached[0] != on or cached[1] != off:
                cached = (on, off, Hysteresis(on, off))
                self._hyst[i] = cached
            wanted[code] = wanted.get(code, False) or cached[2].update(val)
        try:
            for code, on in wanted.items():
                if on != self._held.get(code, False):
                    inj.key(code, on)
                    self._held[code] = on
            for code in [c for c, d in self._held.items() if d and c not in wanted]:
                inj.key(code, False)       # binding removido do config com a tecla segurada
                self._held[code] = False
        except Exception as exc:
            self._warn(("send", str(exc)), f"falha ao enviar tecla: {exc}")

    def neutral(self) -> None:
        self._release_all()

    def close(self) -> None:
        self._release_all()


# ───────────────────────────── controle Xbox 360 (ViGEm) ─────────────────────────────
XBOX_BUTTON_NAMES = ("A", "B", "X", "Y", "LB", "RB", "BACK", "START", "L3", "R3", "GUIDE",
                     "UP", "DOWN", "LEFT", "RIGHT")


class VGamepadPad:
    """Adaptador para o pacote `vgamepad` (MIT; exige o driver ViGEmBus instalado).

    O `import vgamepad` já conecta ao driver: se ele não estiver instalado, levanta exceção
    (tratada pelo XboxSink como 'indisponível')."""

    def __init__(self):
        import vgamepad as vg
        B = vg.XUSB_BUTTON
        self._buttons = {
            "A": B.XUSB_GAMEPAD_A, "B": B.XUSB_GAMEPAD_B, "X": B.XUSB_GAMEPAD_X, "Y": B.XUSB_GAMEPAD_Y,
            "LB": B.XUSB_GAMEPAD_LEFT_SHOULDER, "RB": B.XUSB_GAMEPAD_RIGHT_SHOULDER,
            "BACK": B.XUSB_GAMEPAD_BACK, "START": B.XUSB_GAMEPAD_START,
            "L3": B.XUSB_GAMEPAD_LEFT_THUMB, "R3": B.XUSB_GAMEPAD_RIGHT_THUMB, "GUIDE": B.XUSB_GAMEPAD_GUIDE,
            "UP": B.XUSB_GAMEPAD_DPAD_UP, "DOWN": B.XUSB_GAMEPAD_DPAD_DOWN,
            "LEFT": B.XUSB_GAMEPAD_DPAD_LEFT, "RIGHT": B.XUSB_GAMEPAD_DPAD_RIGHT,
        }
        self._pad = vg.VX360Gamepad()

    def stick(self, x, y):
        self._pad.left_joystick_float(x_value_float=x, y_value_float=y)

    def triggers(self, lt, rt):
        self._pad.left_trigger_float(value_float=lt)
        self._pad.right_trigger_float(value_float=rt)

    def button(self, name, pressed):
        (self._pad.press_button if pressed else self._pad.release_button)(button=self._buttons[name])

    def update(self):
        self._pad.update()

    def reset(self):
        self._pad.reset()
        self._pad.update()


class XboxSink(OutputSink):
    """Controle Xbox 360 virtual: direção -> analógico esquerdo X, acelerador -> RT, freio -> LT,
    botões físicos -> botões do controle (outputs.xbox.buttons: {"1": "A", ...}).

    Observação: o Xbox 360 não tem FFB de volante; para FFB real no jogo use o vJoy.
    """

    name = "xbox"

    def __init__(self, cfg, log=print, pad_factory=VGamepadPad):
        self.cfg, self.log, self._factory = cfg, log, pad_factory
        self._pad = None
        self._failed = False
        self._last = None
        self._warned = set()

    def _get_pad(self):
        if self._pad is None and not self._failed:
            try:
                self._pad = self._factory()
                self.log("[xbox] controle virtual criado.")
            except Exception as exc:
                self._failed = True
                self.log(f"[xbox] indisponível ({exc}). Instale `pip install vgamepad` e o driver ViGEmBus.")
        return self._pad

    def send(self, st) -> None:
        conf = self.cfg.get("outputs", {}).get("xbox", {})
        if not conf.get("enabled"):
            if self._pad is not None and self._last is not None:
                self.neutral()
            return
        pad = self._get_pad()
        if pad is None:
            return
        pressed = set()
        for num, name in (conf.get("buttons") or {}).items():
            if not name:
                continue                          # "" = sem mapeamento
            name = str(name).upper()
            if name not in XBOX_BUTTON_NAMES:
                if ("btn", name) not in self._warned:
                    self._warned.add(("btn", name))
                    self.log(f"[xbox] botão desconhecido: {name!r} (use {', '.join(XBOX_BUTTON_NAMES)})")
                continue
            try:
                i = int(num) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(st.buttons) and st.buttons[i]:
                pressed.add(name)
        lx = max(-1.0, min(1.0, st.steering))
        snap = (round(lx, 4), round(st.brake, 3), round(st.throttle, 3), tuple(sorted(pressed)))
        if snap == self._last:
            return                                # nada mudou: não manda ao driver
        try:
            pad.stick(lx, 0.0)
            pad.triggers(st.brake, st.throttle)
            for name in XBOX_BUTTON_NAMES:
                pad.button(name, name in pressed)
            pad.update()
            self._last = snap
        except Exception as exc:
            if ("send", str(exc)) not in self._warned:
                self._warned.add(("send", str(exc)))
                self.log(f"[xbox] falha ao enviar: {exc}")

    def neutral(self) -> None:
        if self._pad is not None:
            try:
                self._pad.reset()
            except Exception:
                pass
        self._last = None

    def close(self) -> None:
        self.neutral()


def build_sinks(cfg, vjoy, log=print):
    """Todas as saídas. Cada uma consulta `outputs.<nome>.enabled` a cada envio (vale no hot reload);
    teclado e Xbox só criam seus recursos (SendInput / controle virtual) quando ligados."""
    return [VJoySink(vjoy, cfg, log=log), KeyboardSink(cfg, log=log), XboxSink(cfg, log=log)]
