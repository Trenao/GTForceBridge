"""Loop principal da ponte (--run): lê o volante, publica no vJoy e repassa o FFB."""
from __future__ import annotations

import json
import os
import time

from . import winutil
from .autocal_profile import overlay_profile, pid_key, profile_for
from .config import DEFAULT_CONFIG, _sanitize_ffb, deep_merge
from .controls import compute_controls
from .curves import clamp
from .device_table import describe
from .ffb_dump import DumpStats
from .ffb_receiver import FfbReceiver
from .ffb_translator import FfbTranslator
from .paths import CONFIG_PATH, STOP_PATH, TELEMETRY_PATH
from .reconnect import WheelLink
from .sinks import build_sinks
from .vjoy import VJoy
from .wheel import Wheel, init_sdl


class _RunState:
    __slots__ = ("last_telemetry",)
    def __init__(self):
        self.last_telemetry = 0.0


def cmd_run(cfg, verbose, ffb=True, dump=False):
    """Loop da ponte. ffb=False: só entrada (--no-ffb). dump=True: só loga o FFB que o jogo manda ao vJoy."""
    winutil.begin_timer_resolution(1)          # desfeito no finally
    if cfg.get("high_priority"):
        print("Prioridade ALTA do processo:", "ok" if winutil.set_high_priority() else "não aplicada")

    sdl2 = init_sdl()
    wheel = Wheel(sdl2, cfg["device_match"], cfg.get("device_pids"))
    print(f"Volante: {wheel.name} (VID=0x{wheel.vendor:04X} PID=0x{wheel.product:04X}) "
          f"| eixos={wheel.n_axes} botões={wheel.n_buttons} "
          f"| haptic={'sim' if wheel.haptic else 'NÃO'}")
    print("Modelo:", describe(wheel.vendor, wheel.product, bool(wheel.haptic)))

    # Aplica o último perfil salvo para este PID; avisos não bloqueiam o usuário.
    autocal = profile_for(cfg["ffb"], wheel.product)
    if autocal:
        applied = overlay_profile(cfg["ffb"], autocal)
        if applied:
            print(f"[autocal] aplicado do perfil PID {pid_key(wheel.product)}: {', '.join(applied)}")

    vjoy = VJoy(cfg["vjoy_dll"], cfg["vjoy_device_id"])
    print(f"vJoy device {cfg['vjoy_device_id']} adquirido.")
    # Saídas dos controles (vJoy / teclado / Xbox): ligadas em config.json > outputs
    sinks = build_sinks(cfg, vjoy)

    translator = None
    receiver = None
    dump_stats = None
    if dump:
        # captura: registra o callback, mas NUNCA toca no volante
        receiver = FfbReceiver(vjoy, True)
        dump_stats = DumpStats()
        try:
            vjoy.register_ffb(receiver.callback)
            print("[ffb-dump] callback registrado. Abra o jogo e entre numa corrida; Ctrl+C ou Parar encerra.")
        except RuntimeError as e:
            print("[ffb-dump] não foi possível registrar o callback de FFB:", e)
            receiver = dump_stats = None
    elif not ffb:
        print("FFB desativado (--no-ffb): só entrada.")
    elif cfg["ffb"]["enabled"] and wheel.haptic:
        receiver = FfbReceiver(vjoy, verbose)
        translator = FfbTranslator(sdl2, wheel, cfg["ffb"], verbose)
        try:
            vjoy.register_ffb(receiver.callback)
            print("FFB: callback registrado (o jogo deve enviar efeitos ao vJoy).")
        except RuntimeError as e:
            print("FFB desativado:", e)
            receiver = translator = None
    else:
        print("FFB desativado (config ou volante sem haptic).")

    period = 1.0 / max(50, cfg["loop_hz"])
    print("Rodando. Ctrl+C para sair.\n")

    run_state = _RunState()

    # --- reconexão do volante (Etapa 6): zera forças e vJoy ao perder, reabre sozinho ao voltar
    def _neutral():
        for sk in sinks:
            sk.neutral()

    def _lost():
        nonlocal translator
        print("[volante] desconectado: forças zeradas, vJoy neutro. Aguardando reconexão…")
        if translator:
            try:
                translator.shutdown()
            except Exception as exc:
                print(f"[volante] falha ao parar FFB: {exc}")
            translator = None
        try:
            wheel.close()
        except Exception:
            pass
        _neutral()

    def _reopen():
        sdl2.SDL_JoystickUpdate()
        try:
            return Wheel(sdl2, cfg["device_match"], cfg.get("device_pids"))
        except RuntimeError:
            return None

    def _back(new_wheel):
        nonlocal wheel, translator
        wheel = new_wheel
        print(f"[volante] reconectado: {wheel.name} | haptic={'sim' if wheel.haptic else 'NÃO'}")
        if receiver is not None and not dump and cfg["ffb"]["enabled"] and wheel.haptic:
            translator = FfbTranslator(sdl2, wheel, cfg["ffb"], verbose)

    def _safe(fn):
        """Telemetria é só para a GUI: nunca pode derrubar o loop."""
        try:
            return fn()
        except Exception:
            return None

    link = WheelLink(_reopen, _lost, _back, retry_s=1.0)

    def _mtime():
        try:
            return os.path.getmtime(CONFIG_PATH)
        except OSError:
            return 0.0

    cfg_mtime = _mtime()
    next_reload_check = 0.0

    try:
        next_t = time.perf_counter()
        while True:
            if next_t >= next_reload_check:
                next_reload_check = next_t + 0.5
                m = _mtime()
                if m != cfg_mtime:
                    cfg_mtime = m
                    try:
                        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                            new_cfg = deep_merge(DEFAULT_CONFIG, json.load(f))
                        new_cfg = _sanitize_ffb(new_cfg)
                        for key, val in new_cfg.items():
                            if isinstance(val, dict) and isinstance(cfg.get(key), dict):
                                cfg[key].clear(); cfg[key].update(val)
                            else:
                                cfg[key] = val
                        period = 1.0 / max(50, cfg["loop_hz"])
                        if translator and wheel.haptic and wheel.can(sdl2.SDL_HAPTIC_GAIN):
                            sdl2.SDL_HapticSetGain(
                                wheel.haptic, int(100 * clamp(cfg["ffb"]["master_gain"], 0, 1)))
                        print("[config] recarregado")
                    except (OSError, ValueError, KeyError) as exc:
                        print(f"[config] falha ao recarregar (mantendo anterior): {exc}")
            if os.path.exists(STOP_PATH):
                try: os.remove(STOP_PATH)
                except OSError: pass
                print("\nEncerramento solicitado pela interface.")
                break
            wheel.update()
            if not link.poll(wheel.attached()):
                if receiver is not None:       # não deixa a fila crescer enquanto o volante está fora
                    try:
                        while True:
                            receiver.q.get_nowait()
                    except Exception:
                        pass
                time.sleep(period)
                next_t = time.perf_counter()
                continue

            state = compute_controls(wheel, cfg)
            for sk in sinks:
                sk.send(state)
            steer, thr, brk = state.steering, state.throttle, state.brake

            now = time.perf_counter()
            if now - run_state.last_telemetry >= 0.05:
                payload = {
                    "time": time.time(), "device": wheel.name,
                    "vid": wheel.vendor, "pid": wheel.product,
                    "physical": {f"A{i}": round(wheel.axis(i), 4) for i in range(wheel.n_axes)},
                    "buttons": [int(wheel.button(i)) for i in range(wheel.n_buttons)],
                    "output": {"steering": round(steer, 4), "throttle": round(thr, 4), "brake": round(brk, 4)},
                    "vjoy_axes": cfg["vjoy_axes"],
                    "ffb": _safe(lambda: translator.snapshot() if translator else None),
                    "caps": _safe(lambda: wheel.capabilities()),
                }
                tmp_path = TELEMETRY_PATH + ".tmp"
                try:
                    with open(tmp_path, "w", encoding="utf-8") as tf:
                        json.dump(payload, tf)
                    os.replace(tmp_path, TELEMETRY_PATH)
                except OSError:
                    pass
                run_state.last_telemetry = now

            if translator:
                translator.process(receiver.q)
            elif dump_stats is not None:
                for line in dump_stats.consume(receiver.q) + dump_stats.periodic():
                    print(line)

            next_t += period
            delay = next_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                next_t = time.perf_counter()
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        if dump_stats is not None:
            print("[ffb-dump] total:", dump_stats.summary())
        try:
            if translator:
                translator.shutdown()
        except Exception as exc:
            print(f"[cleanup] falha ao parar FFB: {exc}")
        for sk in sinks:
            sk.close()
        try:
            wheel.close()
        except Exception as exc:
            print(f"[cleanup] falha ao fechar volante: {exc}")
        try:
            if os.path.exists(TELEMETRY_PATH):
                os.remove(TELEMETRY_PATH)
        except OSError:
            pass
        try:
            sdl2.SDL_Quit()
        except Exception as exc:
            print(f"[cleanup] SDL_Quit: {exc}")
        winutil.end_timer_resolution()
