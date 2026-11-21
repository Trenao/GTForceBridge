"""Diagnóstico: lista dispositivos/capacidades (--list) e monitor ao vivo de eixos (--monitor)."""
from __future__ import annotations

import time

from .device_table import lookup
from .wheel import Wheel, haptic_flags, init_sdl


def cmd_list():
    sdl2 = init_sdl()
    n = sdl2.SDL_NumJoysticks()
    print(f"{n} dispositivo(s) SDL:")
    for i in range(n):
        name = (sdl2.SDL_JoystickNameForIndex(i) or b"").decode(errors="replace")
        joy = sdl2.SDL_JoystickOpen(i)
        info = f"  [{i}] {name}"
        try:
            vid = sdl2.SDL_JoystickGetDeviceVendor(i)
            pid = sdl2.SDL_JoystickGetDeviceProduct(i)
            info += f" | VID=0x{vid:04X} PID=0x{pid:04X}"
            known = lookup(vid, pid)
            if known:
                info += f" | {known.name} (~{known.range_deg}°)"
        except AttributeError:
            pass
        if joy:
            info += (f" | eixos={sdl2.SDL_JoystickNumAxes(joy)}"
                     f" botões={sdl2.SDL_JoystickNumButtons(joy)}"
                     f" hats={sdl2.SDL_JoystickNumHats(joy)}")
            if sdl2.SDL_JoystickIsHaptic(joy):
                h = sdl2.SDL_HapticOpenFromJoystick(joy)
                if h:
                    q = sdl2.SDL_HapticQuery(h)
                    caps = [nm for nm, fl in haptic_flags(sdl2) if q & fl]
                    info += f"\n      haptic: {', '.join(caps)}"
                    for label, fn in (("efeitos simultâneos na memória do driver", "SDL_HapticNumEffects"),
                                      ("tocando ao mesmo tempo (máx.)", "SDL_HapticNumEffectsPlaying"),
                                      ("eixos com FFB", "SDL_HapticNumAxes")):
                        try:
                            n = getattr(sdl2, fn)(h)
                            if n >= 0:
                                info += f"\n      {label}: {n}"
                        except Exception:
                            pass
                    sdl2.SDL_HapticClose(h)
            else:
                info += "\n      sem haptic"
            sdl2.SDL_JoystickClose(joy)
        print(info)
    sdl2.SDL_Quit()


def cmd_monitor(cfg):
    sdl2 = init_sdl()
    w = Wheel(sdl2, cfg["device_match"], cfg.get("device_pids"))
    print(f"Monitorando '{w.name}' (Ctrl+C para sair)\n")
    try:
        while True:
            w.update()
            axes = " ".join(f"A{i}:{w.axis(i):+.3f}" for i in range(w.n_axes))
            btns = "".join("1" if w.button(i) else "0" for i in range(w.n_buttons))
            print(f"\r{axes} | B:{btns}   ", end="", flush=True)
            time.sleep(0.03)
    except KeyboardInterrupt:
        print()
