"""Teste de FFB direto no volante via SDL, sem o jogo (--ffb-test)."""
from __future__ import annotations

import time

from .wheel import Wheel, init_sdl


def cmd_ffb_test(cfg):
    sdl2 = init_sdl()
    w = Wheel(sdl2, cfg["device_match"], cfg.get("device_pids"))
    if not w.haptic:
        print("O volante não expõe haptic pelo SDL. O FFB não vai funcionar por este caminho.")
        return
    print(f"Testando FFB em '{w.name}'. Segure o volante.")
    sdl2.SDL_HapticSetGain(w.haptic, 100) if w.can(sdl2.SDL_HAPTIC_GAIN) else None

    def run(effect, secs, label):
        eid = sdl2.SDL_HapticNewEffect(w.haptic, effect)
        if eid < 0:
            print(f"  {label}: não suportado ({sdl2.SDL_GetError().decode()})")
            return
        print(f"  {label}...")
        sdl2.SDL_HapticRunEffect(w.haptic, eid, 1)
        time.sleep(secs)
        sdl2.SDL_HapticStopEffect(w.haptic, eid)
        sdl2.SDL_HapticDestroyEffect(w.haptic, eid)

    if w.can(sdl2.SDL_HAPTIC_SPRING):
        e = sdl2.SDL_HapticEffect()
        e.type = sdl2.SDL_HAPTIC_SPRING
        c = e.condition
        c.type = sdl2.SDL_HAPTIC_SPRING
        c.direction.type = sdl2.SDL_HAPTIC_STEERING_AXIS
        c.length = sdl2.SDL_HAPTIC_INFINITY
        c.right_sat[0] = c.left_sat[0] = 0xFFFF
        c.right_coeff[0] = c.left_coeff[0] = 20000
        run(e, 4, "mola centralizadora (4s)")
    if w.can(sdl2.SDL_HAPTIC_CONSTANT):
        for level, label in ((12000, "puxa para um lado"), (-12000, "puxa para o outro")):
            e = sdl2.SDL_HapticEffect()
            e.type = sdl2.SDL_HAPTIC_CONSTANT
            c = e.constant
            c.type = sdl2.SDL_HAPTIC_CONSTANT
            c.direction.type = sdl2.SDL_HAPTIC_STEERING_AXIS
            c.length = sdl2.SDL_HAPTIC_INFINITY
            c.level = level
            run(e, 2, f"força constante: {label} (2s)")
    if w.can(sdl2.SDL_HAPTIC_RAMP):
        for s, e_lvl, label in ((8000, -8000, "rampa caindo"), (-8000, 8000, "rampa subindo")):
            e = sdl2.SDL_HapticEffect()
            e.type = sdl2.SDL_HAPTIC_RAMP
            r = e.ramp
            r.type = sdl2.SDL_HAPTIC_RAMP
            r.direction.type = sdl2.SDL_HAPTIC_STEERING_AXIS
            r.length = sdl2.SDL_HAPTIC_INFINITY
            r.start = s
            r.end = e_lvl
            run(e, 2, f"rampa: {label} (2s)")
    print("Teste concluído.")
    sdl2.SDL_Quit()
