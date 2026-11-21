"""Volante via SDL2: inicialização, flags de haptic e leitura de eixos/botões."""
from __future__ import annotations

from .curves import clamp


def init_sdl():
    import sdl2
    sdl2.SDL_SetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")
    sdl2.SDL_SetHint(b"SDL_JOYSTICK_HIDAPI", b"0")
    sdl2.SDL_SetHint(b"SDL_JOYSTICK_RAWINPUT", b"0")
    if sdl2.SDL_Init(sdl2.SDL_INIT_JOYSTICK | sdl2.SDL_INIT_HAPTIC) != 0:
        raise RuntimeError("SDL_Init falhou: " + sdl2.SDL_GetError().decode())
    return sdl2


def haptic_flags(sdl2):
    return [
        ("CONSTANT", sdl2.SDL_HAPTIC_CONSTANT), ("SINE", sdl2.SDL_HAPTIC_SINE),
        ("TRIANGLE", sdl2.SDL_HAPTIC_TRIANGLE), ("SAWUP", sdl2.SDL_HAPTIC_SAWTOOTHUP),
        ("SAWDOWN", sdl2.SDL_HAPTIC_SAWTOOTHDOWN), ("RAMP", sdl2.SDL_HAPTIC_RAMP),
        ("SPRING", sdl2.SDL_HAPTIC_SPRING), ("DAMPER", sdl2.SDL_HAPTIC_DAMPER),
        ("INERTIA", sdl2.SDL_HAPTIC_INERTIA), ("FRICTION", sdl2.SDL_HAPTIC_FRICTION),
        ("GAIN", sdl2.SDL_HAPTIC_GAIN),
    ]


class Wheel:
    def __init__(self, sdl2, match, pids=None):
        self.sdl2 = sdl2
        self.joy = None
        self.haptic = None
        self.name = ""
        self.vendor = 0
        self.product = 0
        self.index = -1
        match_l = (match or "").lower()
        pids = [int(p) for p in (pids or []) if p]
        for i in range(sdl2.SDL_NumJoysticks()):
            name = (sdl2.SDL_JoystickNameForIndex(i) or b"").decode(errors="replace")
            if match_l and match_l in name.lower() and "vjoy" not in name.lower():
                self.joy = sdl2.SDL_JoystickOpen(i)
                self.name = name
                self.index = i
                break
        if not self.joy and pids:
            for i in range(sdl2.SDL_NumJoysticks()):
                name = (sdl2.SDL_JoystickNameForIndex(i) or b"").decode(errors="replace")
                if "vjoy" in name.lower():
                    continue
                try:
                    vid = sdl2.SDL_JoystickGetDeviceVendor(i)
                    pid = sdl2.SDL_JoystickGetDeviceProduct(i)
                except AttributeError:
                    continue
                if vid == 0x046D and pid in pids:
                    self.joy = sdl2.SDL_JoystickOpen(i)
                    self.name = name
                    self.index = i
                    self.vendor, self.product = vid, pid
                    break
        if not self.joy:
            raise RuntimeError(f"Volante contendo '{match}' não encontrado. Use --list.")
        try:
            if not self.vendor:
                self.vendor = sdl2.SDL_JoystickGetDeviceVendor(self.index)
            if not self.product:
                self.product = sdl2.SDL_JoystickGetDeviceProduct(self.index)
        except AttributeError:
            pass
        self.n_axes = sdl2.SDL_JoystickNumAxes(self.joy)
        self.n_buttons = sdl2.SDL_JoystickNumButtons(self.joy)
        self.supported = 0
        if sdl2.SDL_JoystickIsHaptic(self.joy):
            self.haptic = sdl2.SDL_HapticOpenFromJoystick(self.joy)
            if self.haptic:
                self.supported = sdl2.SDL_HapticQuery(self.haptic)

    def update(self):
        self.sdl2.SDL_JoystickUpdate()

    def axis(self, idx):
        if idx is None or idx < 0 or idx >= self.n_axes:
            return 0.0
        return clamp(self.sdl2.SDL_JoystickGetAxis(self.joy, idx) / 32768.0, -1.0, 1.0)

    def button(self, idx):
        return bool(self.sdl2.SDL_JoystickGetButton(self.joy, idx))

    def attached(self):
        """False se o volante foi desconectado (ou já foi fechado)."""
        if not self.joy:
            return False
        try:
            return bool(self.sdl2.SDL_JoystickGetAttached(self.joy))
        except Exception:
            return True

    def capabilities(self):
        """O que o driver do volante (via DirectInput/SDL) diz suportar. Só dados consultados, nada presumido."""
        if getattr(self, "_caps", None) is not None:
            return self._caps
        sd = self.sdl2
        caps = {"effects": [nm for nm, fl in haptic_flags(sd) if self.supported & fl],
                "num_effects": None, "num_playing": None, "axes": None}
        if self.haptic:
            for key, fn in (("num_effects", "SDL_HapticNumEffects"),
                            ("num_playing", "SDL_HapticNumEffectsPlaying"),
                            ("axes", "SDL_HapticNumAxes")):
                try:
                    v = getattr(sd, fn)(self.haptic)
                    caps[key] = int(v) if v >= 0 else None
                except Exception:
                    pass
        self._caps = caps
        return caps

    def can(self, flag):
        return bool(self.supported & flag)

    def close(self):
        try:
            if self.haptic:
                self.sdl2.SDL_HapticClose(self.haptic)
                self.haptic = None
        finally:
            if self.joy:
                self.sdl2.SDL_JoystickClose(self.joy)
                self.joy = None
