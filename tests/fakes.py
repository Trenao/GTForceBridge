"""Volante/SDL falsos para testar o FfbTranslator sem hardware: registram cada chamada ao SDL haptic."""
import sdl2


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class FakeSdl:
    """Usa structs/constantes reais do pysdl2, mas troca as chamadas ao driver por gravações."""

    def __init__(self, clock, supported=None):
        self.clock = clock
        self.calls = []              # (t, op, id, info)
        self._next = 0
        self.effects = {}            # id -> último efeito enviado
        self.autocenter = None

    def __getattr__(self, name):
        return getattr(sdl2, name)

    # --- haptic
    def SDL_HapticNumAxes(self, h): return 1
    def SDL_HapticSetGain(self, h, g): return 0
    def SDL_HapticSetAutocenter(self, h, v):
        self.autocenter = v
        return 0
    def SDL_GetError(self): return b""
    def SDL_HapticPause(self, h): return 0
    def SDL_HapticUnpause(self, h): return 0
    def SDL_HapticStopAll(self, h):
        self.calls.append((self.clock(), "stopall", None, None))
        return 0

    def _info(self, e):
        t = e.type
        if t == sdl2.SDL_HAPTIC_CONSTANT:
            return ("const", e.constant.level)
        if t in (sdl2.SDL_HAPTIC_SPRING, sdl2.SDL_HAPTIC_DAMPER,
                 sdl2.SDL_HAPTIC_FRICTION, sdl2.SDL_HAPTIC_INERTIA):
            self.last_center = e.condition.center[0]
            return ("cond", t, e.condition.right_coeff[0], e.condition.left_coeff[0])
        if t == sdl2.SDL_HAPTIC_RAMP:
            return ("ramp", e.ramp.length, e.ramp.start, e.ramp.end)
        self.last_phase = e.periodic.phase
        return ("per", t, e.periodic.magnitude, e.periodic.period)

    def SDL_HapticNewEffect(self, h, e):
        self._next += 1
        self.effects[self._next] = self._info(e)
        self.calls.append((self.clock(), "new", self._next, self._info(e)))
        return self._next

    def SDL_HapticUpdateEffect(self, h, i, e):
        self.effects[i] = self._info(e)
        self.calls.append((self.clock(), "update", i, self._info(e)))
        return 0

    def SDL_HapticRunEffect(self, h, i, n):
        self.calls.append((self.clock(), "run", i, None))
        return 0

    def SDL_HapticStopEffect(self, h, i):
        self.calls.append((self.clock(), "stop", i, None))
        return 0

    def SDL_HapticDestroyEffect(self, h, i):
        self.calls.append((self.clock(), "destroy", i, None))
        self.effects.pop(i, None)

    # --- helpers
    def ops(self, name):
        return [t for t, op, _, _ in self.calls if op == name]

    def const_levels(self):
        out = []
        for t, op, i, info in self.calls:
            if op in ("new", "update") and info and info[0] == "const":
                out.append((t, info[1]))
        return out


class FakeWheel:
    haptic = 1

    def can(self, flag):
        return True