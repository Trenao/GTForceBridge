"""Traduz eventos FFB do vJoy em efeitos SDL haptic no volante (um efeito SDL por idx+categoria)."""
from __future__ import annotations

import ctypes
import math
import queue
import time

from .constants import SCALE_16BIT, SCALE_8BIT, SCALE_DINPUT, SCALE_HYSTERESIS, SCALE_SAMPLES_MIN
from .curves import clamp
from .vjoy_protocol import DURATION_INFINITE, LOOP_INFINITE, CTRL_DEVCONT, CTRL_DEVPAUSE, CTRL_DEVRST, CTRL_DISACT, CTRL_ENACT, CTRL_STOPALL, EFF_SOLO, EFF_START, EFF_STOP, ET_CONST, ET_DMPR, ET_FRCTN, ET_INRT, ET_NAMES, ET_RAMP, ET_SINE, ET_SPRNG, ET_SQR, ET_STDN, ET_STUP, ET_TRI


class FfbTranslator:
    STOP_DEBOUNCE_S = 0.15   # carência antes de parar de verdade (EFF_STOP)

    def __init__(self, sdl2, wheel, ffb_cfg, verbose=False, clock=time.monotonic):
        self.clock = clock      # injetável: os testes usam um relógio falso
        self.sdl2 = sdl2
        self.w = wheel
        self.cfg = ffb_cfg
        self.verbose = verbose
        self.fx = {}            # (idx, tipo) -> estado do efeito do JOGO
        self.pending = {}
        self.latest = {}
        self.last_key = {}
        # vJoy reutiliza EffectBlockIndex; o tipo vem do último EFF_REPORT.
        # Guardamos o tipo atual por índice para associar dados e operações.
        self.last_report_key = {}
        self.scale = {}
        self.scale_samples = {}
        self.dev_gain = 1.0
        # (idx, cat) -> {"id": sdl_id, "subtype": flag_sdl}
        self.sdl_fx = {}
        # slot -> (deadline, key): paradas agendadas (debounce de EFF_STOP)
        self.pending_stops = {}
        self._naxes = sdl2.SDL_HapticNumAxes(wheel.haptic) if wheel.haptic else 0
        if wheel.haptic and wheel.can(sdl2.SDL_HAPTIC_GAIN):
            sdl2.SDL_HapticSetGain(wheel.haptic, int(100 * clamp(ffb_cfg["master_gain"], 0, 1)))
        # O autocenter (mola) do driver brigaria com o FFB do jogo.
        if wheel.haptic and ffb_cfg.get("disable_autocenter", True) \
                and wheel.can(sdl2.SDL_HAPTIC_AUTOCENTER):
            sdl2.SDL_HapticSetAutocenter(wheel.haptic, 0)

    # ---- parâmetros de suavização (lidos a cada uso: valem após hot reload) ----
    def _slew(self):
        """Fração da escala total por segundo que a força constante pode variar (0 = sem limite)."""
        return max(0.0, float(self.cfg.get("slew_per_sec", 0.0) or 0.0))

    def _interval(self):
        """Intervalo mínimo entre atualizações de um mesmo efeito (0 = sem limite)."""
        hz = float(self.cfg.get("update_hz", 100) or 0)
        return 1.0 / hz if hz > 0 else 0.0

    def log(self, *a):
        if self.verbose:
            print("[ffb]", *a)

    # ---- escala ----
    def _observe_magnitude(self, idx, mag):
        a = abs(int(mag))
        if a == 0:
            return self.scale.get(idx, SCALE_DINPUT)
        samples = self.scale_samples.setdefault(idx, [])
        samples.append(a)
        if len(samples) > 8:
            samples.pop(0)
        if idx in self.scale and len(samples) >= SCALE_SAMPLES_MIN:
            cur = self.scale[idx]
            if a > cur * SCALE_HYSTERESIS:
                new_scale = SCALE_16BIT if a > SCALE_DINPUT * 1.5 else SCALE_DINPUT
                if new_scale != cur:
                    self.scale[idx] = new_scale
                    self.log(f"escala do efeito {idx}: {cur:.0f} -> {new_scale:.0f} (mag={a})")
            return self.scale[idx]
        # Nunca se presume 8 bits: uma força pequena (ex.: 200 de 10000) seria
        # lida como força quase total. 8 bits só por 'magnitude_scale' no config.
        peak = max(samples)
        guess = SCALE_DINPUT if peak <= SCALE_DINPUT * 1.5 else SCALE_16BIT
        self.scale[idx] = guess
        self.log(f"escala inicial do efeito {idx}: {guess:.0f} (peak={peak})")
        return guess

    @staticmethod
    def category(etype):
        if etype == ET_CONST:
            return "const"
        if etype == ET_RAMP:
            return "ramp"
        if etype in (ET_SPRNG, ET_DMPR, ET_INRT, ET_FRCTN):
            return "cond"
        if etype in (ET_SINE, ET_SQR, ET_TRI, ET_STUP, ET_STDN):
            return "per"
        return None

    @staticmethod
    def _sdl_cat(cat, etype=None):
        # Condições (spring/damper/inertia/friction) tinham UM slot SDL e eram
        # destruídas/recriadas a cada troca SPRING<->DAMPER (o FH4 alterna os
        # dois todo ciclo) => tremor. O SDK da Logitech também mantém um efeito
        # por tipo, então agora cada subtipo tem o seu slot.
        if cat in ("cond", "per") and etype is not None:
            return f"{cat}{etype}"
        return cat

    def _slot_for_key(self, key):
        """(idx, etype) do jogo -> chave do slot SDL (idx, categoria[+tipo])."""
        return (key[0], self._sdl_cat(self.category(key[1]), key[1]))

    def _slots_of(self, idx):
        return [sl for sl in self.sdl_fx if sl[0] == idx]

    def state(self, key):
        return self.fx.setdefault(key, {"type": key[1], "gain": 1.0, "sign": 1.0,
                                        "direction_factor": 1.0, "dur": 0, "delay": 0, "loops": 1,
                                        "deadline": None, "start_at": None,
                                        "const": 0, "ramp": None, "cond": None, "per": None,
                                        "playing": False})

    def keys_for(self, idx):
        return [k for k in self.fx if k[0] == idx]

    def set_param(self, idx, cat, value):
        # Os callbacks de parâmetro e EFF_REPORT chegam por eventos separados.
        # Não presumimos que a thread do jogo os enfileire na mesma ordem.
        # Guardamos por (índice, categoria); flush_pending resolve o tipo usando
        # last_key, que é atualizado quando o EFF_REPORT correspondente chega.
        pk = (idx, cat)
        self.latest[pk] = value
        key = self.last_key.get(pk)
        if key is not None and key in self.fx:
            # tipo conhecido: aplica na hora (um fluxo contínuo de força não pode ficar
            # esperando "silêncio" para chegar ao volante)
            self.pending.pop(pk, None)
            self.fx[key][cat] = value
            self.sync(key)
        else:
            self.pending[pk] = (value, self.clock())   # chegou antes do EFF_REPORT
        self.log(f"parâmetro recebido idx={idx} cat={cat}: {value}")

    def flush_pending(self):
        """Parâmetros que chegaram antes do EFF_REPORT: aplica quando o tipo aparecer; descarta se demorar."""
        now = self.clock()
        for pk, (val, t) in list(self.pending.items()):
            idx, cat = pk
            key = self.last_key.get(pk)
            if key is not None and key in self.fx:
                self.pending.pop(pk, None)
                self.fx[key][cat] = val
                self.sync(key)
            elif now - t >= 0.25:
                self.pending.pop(pk, None)
                self.log(f"parâmetro idx={idx} cat={cat} sem EFF_REPORT após espera; descartado")

    def process(self, q):
        while True:
            try:
                ev = q.get_nowait()
            except queue.Empty:
                break
            self.handle(ev)
        self.flush_pending()
        self._expire()
        self.flush_stops()
        self.tick()

    def tick(self):
        """Envia atualizações adiadas pelo limite de taxa e avança as rampas (slew)."""
        now = self.clock()
        for slot, entry in list(self.sdl_fx.items()):
            if entry.get("dirty"):
                self._push(slot, now)

    def flush_stops(self):
        if not self.pending_stops:
            return
        now = self.clock()
        for slot, (deadline, key) in list(self.pending_stops.items()):
            if now < deadline:
                continue
            self.pending_stops.pop(slot, None)
            st = self.fx.get(key)
            if st is None or not st["playing"]:
                continue
            entry = self.sdl_fx.get(slot)
            if (entry is not None and entry["cat"] == "const" and self._slew() > 0
                    and entry.get("out", 0) != 0):
                # com slew, a força constante desce em rampa até 0 e só então o efeito para
                entry["stopping"] = True
                entry["dirty"] = True
                self._push(slot, now)
                self.log(f"efeito {slot[0]}: STOP em rampa {slot[1]}")
                continue
            st["playing"] = False
            if entry is not None and self.w.haptic:
                self.sdl2.SDL_HapticStopEffect(self.w.haptic, entry["id"])
            self.log(f"efeito {slot[0]}: STOP efetivo {slot[1]}")

    # ---- eventos ----
    def handle(self, ev):
        k = ev[0]
        if not self.w.haptic:
            return
        if k == "report":
            _, idx, etype, gain, polar, direction, dur, *extra = ev
            delay = extra[0] if extra else 0
            dirx = extra[1] if len(extra) > 1 else None
            key = (idx, etype)
            s = self.state(key)
            cat = self.category(etype)
            self.last_report_key[idx] = key
            if cat:
                pk = (idx, cat)
                early = self.pending.pop(pk, None)
                if early is not None:
                    s[cat] = early[0]
                self.last_key[(idx, cat)] = key
            s["gain"] = clamp(gain / 255.0, 0.0, 1.0) if gain else 1.0
            s["dur"] = dur
            s["delay"] = delay or 0
            if polar:
                # O volante físico tem um único eixo de força. A direção polar
                # do jogo não deve reduzir a magnitude pela projeção cos(X):
                # direções próximas de 90/270 graus zerariam o FFB. Usamos
                # apenas o hemisfério X para definir o sinal; perto do eixo Y,
                # tratamos a direção como indefinida e preservamos magnitude.
                ang = direction / 255.0 * 2.0 * math.pi
                # O PID 1.0 não define o zero do ângulo. "east": a partir de +X (cos);
                # "north": convenção do DirectInput (0° = norte, 90° = leste = +X; sen).
                component_x = (math.sin(ang) if self.cfg.get("polar_zero") == "north"
                               else math.cos(ang))
                s["direction_factor"] = 1.0
                if abs(component_x) < 0.1:
                    s["sign"] = 1.0
                else:
                    s["sign"] = -1.0 if component_x < 0.0 else 1.0
            else:
                s["direction_factor"] = 1.0
                # Cartesiano (vjoyinterface.h): DirX positivo = direita, negativo = esquerda.
                s["sign"] = -1.0 if (dirx is not None and dirx < 0) else 1.0
            self.log(f"efeito {idx}: {ET_NAMES.get(etype, etype)} gain={s['gain']:.2f} "
                     f"sign={s['sign']:+.0f} dir_f={s['direction_factor']:+.3f} "
                     f"polar={int(bool(polar))} direction={direction} dirx={dirx} dur={dur} delay={delay}")
            self.sync(key)
        elif k == "constant":
            _, idx, mag = ev
            self._observe_magnitude(idx, mag)
            self.set_param(idx, "const", mag)
        elif k == "ramp":
            _, idx, start, end = ev
            self._observe_magnitude(idx, max(abs(start), abs(end)))
            self.set_param(idx, "ramp", (start, end))
        elif k == "cond":
            _, idx, is_y, center, pos_c, neg_c, pos_s, neg_s, dead = ev
            if is_y:
                return
            self.set_param(idx, "cond", (center, pos_c, neg_c, pos_s, neg_s, dead))
        elif k == "period":
            _, idx, mag, off, phase, period = ev
            self._observe_magnitude(idx, mag)
            self.set_param(idx, "per", (mag, off, phase, period))
        elif k == "op":
            _, idx, op, loops = ev
            loops = loops or 1
            if op in (EFF_START, EFF_SOLO):
                if op == EFF_SOLO:
                    self.stop_all(keep=idx)
                # Como o vJoy entrega todos os efeitos com o mesmo idx,
                # START precisa ativar todos os tipos configurados nesse índice.
                keys = self.keys_for(idx)
                for key in keys:
                    s = self.fx[key]
                    slot = self._slot_for_key(key)
                    self.pending_stops.pop(slot, None)
                    if slot in self.sdl_fx:
                        self.sdl_fx[slot]["stopping"] = False
                    s["loops"] = loops
                    now = self.clock()
                    delay_s = (s.get("delay") or 0) / 1000.0 if self.cfg.get("honor_duration", True) else 0.0
                    if delay_s > 0:
                        # atraso inicial do jogo (StartDelay): o efeito só toca depois dele
                        s["start_at"] = now + delay_s
                        s["deadline"] = None
                        continue
                    self._begin(key, now)
                self.log(f"efeito {idx}: START ({len(keys)} efeito(s))")
            elif op == EFF_STOP:
                for key in self.keys_for(idx):
                    self.fx[key]["start_at"] = None
                    self.fx[key]["deadline"] = None
                # Mantém o STOP cirúrgico por categoria; o índice do vJoy é compartilhado.
                deadline = self.clock() + self.STOP_DEBOUNCE_S
                stopped = set()
                for cat in ("const", "cond", "per", "ramp"):
                    key = self.last_key.get((idx, cat))
                    if key is not None and key in self.fx and self.fx[key]["playing"]:
                        slot = self._slot_for_key(key)
                        self.pending_stops.setdefault(slot, (deadline, key))
                        stopped.add(cat)
                if not stopped:
                    for key in self.keys_for(idx):
                        self.fx[key]["playing"] = False
                    for slot in self._slots_of(idx):
                        self._destroy_sdl(slot)
                    self.log(f"efeito {idx}: STOP (fallback: tudo)")
                else:
                    self.log(f"efeito {idx}: STOP cat={','.join(sorted(stopped))} "
                             f"(em {self.STOP_DEBOUNCE_S*1000:.0f} ms)")
        elif k == "free":
            idx = ev[1]
            for key in self.keys_for(idx):
                self.fx.pop(key, None)
            for slot in self._slots_of(idx):
                self._destroy_sdl(slot)
            for sl in [x for x in self.pending_stops if x[0] == idx]:
                self.pending_stops.pop(sl, None)
            for d in (self.latest, self.pending):
                for pk in list(d):
                    if pk[0] == idx:
                        d.pop(pk, None)
            for pk in [x for x in self.last_key if x[0] == idx]:
                self.last_key.pop(pk, None)
            self.last_report_key.pop(idx, None)
            self.scale.pop(idx, None)
            self.scale_samples.pop(idx, None)
        elif k == "ctrl":
            c = ev[1]
            if c in (CTRL_STOPALL, CTRL_DEVRST):
                self.stop_all()
                if c == CTRL_DEVRST:
                    for slot in list(self.sdl_fx):
                        self._destroy_sdl(slot)
                    self.pending_stops.clear()
                    self.fx.clear(); self.latest.clear(); self.pending.clear()
                    self.last_key.clear(); self.last_report_key.clear()
                    self.scale.clear(); self.scale_samples.clear()
                    self.sdl2.SDL_HapticUnpause(self.w.haptic)
            elif c in (CTRL_DEVPAUSE, CTRL_DISACT):
                self.sdl2.SDL_HapticPause(self.w.haptic)
            elif c in (CTRL_DEVCONT, CTRL_ENACT):
                self.sdl2.SDL_HapticUnpause(self.w.haptic)
        elif k == "devgain":
            self.dev_gain = ev[1] / 255.0
            for key in list(self.fx):
                self.sync(key)

    def _total_s(self, s):
        """Duração total do efeito em segundos; None = sem fim (0xFFFF, 0 ou loop infinito)."""
        if not self.cfg.get("honor_duration", True):
            return None
        dur = int(s.get("dur") or 0)
        if dur <= 0 or dur >= DURATION_INFINITE:
            return None
        loops = int(s.get("loops") or 1)
        if loops >= LOOP_INFINITE:
            return None
        return dur / 1000.0 * max(1, loops)

    def _begin(self, key, now):
        """Liga o efeito agora e arma o prazo de parada (duração x loops do jogo)."""
        s = self.fx.get(key)
        if s is None:
            return
        s["start_at"] = None
        was_playing = s["playing"]
        s["playing"] = True
        total = self._total_s(s)
        s["deadline"] = now + total if total is not None else None
        self.sync(key, start=not was_playing or total is not None)

    def _expire(self):
        """Inícios atrasados (StartDelay) e fins por duração: o vJoy não avisa quando o prazo acaba."""
        now = self.clock()
        for key, s in list(self.fx.items()):
            if s.get("start_at") is not None and now >= s["start_at"]:
                self._begin(key, now)
            dl = s.get("deadline")
            if dl is not None and now >= dl and s["playing"]:
                s["deadline"] = None
                self.pending_stops.setdefault(self._slot_for_key(key), (now, key))
                self.log(f"efeito {key[0]}: fim da duração ({s['dur']} ms x {s['loops']})")

    def _destroy_sdl(self, slot):
        entry = self.sdl_fx.pop(slot, None)
        if entry is not None:
            self.sdl2.SDL_HapticStopEffect(self.w.haptic, entry["id"])
            self.sdl2.SDL_HapticDestroyEffect(self.w.haptic, entry["id"])

    # ---- build ----
    def _dir(self, d):
        """Define a direção do efeito conforme ffb.direction_mode."""
        sd = self.sdl2
        if self.cfg.get("direction_mode") == "cartesian" and self._naxes >= 2:
            d.type = sd.SDL_HAPTIC_CARTESIAN
            d.dir[0], d.dir[1], d.dir[2] = 1, 0, 0
        else:
            d.type = sd.SDL_HAPTIC_STEERING_AXIS

    def _scale_for(self, idx):
        forced = float(self.cfg.get("magnitude_scale", 0) or 0)
        if forced > 0:
            return forced
        return self.scale.get(idx, SCALE_DINPUT)

    def build(self, s, idx):
        sd = self.sdl2
        c = self.cfg
        scale = c["master_gain"] if not self.w.can(sd.SDL_HAPTIC_GAIN) else 1.0
        scale *= self.dev_gain * s["gain"]
        et = s["type"]
        e = sd.SDL_HapticEffect()
        norm = self._scale_for(idx)
        inv = -1.0 if c.get("invert") else 1.0

        if et == ET_CONST:
            if not self.w.can(sd.SDL_HAPTIC_CONSTANT):
                return None, None
            sign = s["sign"] * inv
            direction_factor = abs(s.get("direction_factor", 1.0))
            level = int(clamp(s["const"] / norm * 32767 * sign *
                              direction_factor * c["constant_scale"] * scale,
                              -32767, 32767))
            if abs(s["const"]) / norm < float(c.get("const_deadzone_pct", 0) or 0) / 100.0:
                level = 0                       # ruído com o carro parado
            min_m = float(c.get("min_effective_magnitude", 0) or 0)
            if level and min_m > 0 and c.get("min_effect_mode", "stretch") == "stretch":
                # a autocal mediu a zona morta do motor: [0..1] vira [min..1]
                frac = min_m + (1.0 - min_m) * (abs(level) / 32767.0)
                level = int(clamp(frac, 0.0, 1.0) * 32767) * (1 if level > 0 else -1)
            self.log(f"const idx={idx} raw={s['const']} norm={norm:.0f} "
                     f"sign={sign:+.0f} dir_f={direction_factor:.3f} level={level}")
            e.type = sd.SDL_HAPTIC_CONSTANT
            e.constant.type = sd.SDL_HAPTIC_CONSTANT
            self._dir(e.constant.direction)
            e.constant.length = sd.SDL_HAPTIC_INFINITY
            e.constant.level = level
            return e, "const"

        if et == ET_RAMP and s["ramp"]:
            if not self.w.can(sd.SDL_HAPTIC_RAMP):
                return None, None
            start, end = s["ramp"]
            k = c.get("ramp_scale", 1.0) * scale
            e.type = sd.SDL_HAPTIC_RAMP
            r = e.ramp
            r.type = sd.SDL_HAPTIC_RAMP
            self._dir(r.direction)
            # PID 1.0: ramp não pode ter duração infinita; a rampa vai de start a end em Duration.
            dur = int(s.get("dur") or 0)
            r.length = dur if 0 < dur < DURATION_INFINITE else sd.SDL_HAPTIC_INFINITY
            direction_gain = abs(s.get("direction_factor", 1.0))
            r.start = int(clamp(start / norm * 32767 * s["sign"] * inv * direction_gain * k, -32767, 32767))
            r.end = int(clamp(end / norm * 32767 * s["sign"] * inv * direction_gain * k, -32767, 32767))
            return e, "ramp"

        if et in (ET_SPRNG, ET_DMPR, ET_INRT, ET_FRCTN) and s["cond"]:
            flag = {ET_SPRNG: sd.SDL_HAPTIC_SPRING, ET_DMPR: sd.SDL_HAPTIC_DAMPER,
                    ET_INRT: sd.SDL_HAPTIC_INERTIA, ET_FRCTN: sd.SDL_HAPTIC_FRICTION}[et]
            if not self.w.can(flag):
                return None, None
            center, pos_c, neg_c, pos_s, neg_s, dead = s["cond"]
            k = c["condition_scale"] * scale
            center_shift = 0
            if et == ET_SPRNG:
                # center_offset = onde o volante assenta com spring em 0 (medido pela autocal);
                # desloca o centro no sentido oposto para ele assentar em 0.
                center_shift = -clamp(float(c.get("center_offset", 0.0)), -1.0, 1.0) * SCALE_DINPUT
            e.type = flag
            cd = e.condition
            cd.type = flag
            self._dir(cd.direction)
            cd.length = sd.SDL_HAPTIC_INFINITY
            cd.right_coeff[0] = int(clamp(pos_c / SCALE_DINPUT * 32767 * k, -32767, 32767))
            cd.left_coeff[0] = int(clamp(neg_c / SCALE_DINPUT * 32767 * k, -32767, 32767))
            cd.right_sat[0] = int(clamp(pos_s / SCALE_DINPUT * 65535, 0, 65535))
            cd.left_sat[0] = int(clamp(neg_s / SCALE_DINPUT * 65535, 0, 65535))
            cd.deadband[0] = int(clamp(dead / SCALE_DINPUT * 65535, 0, 65535))
            cd.center[0] = int(clamp((center + center_shift) / SCALE_DINPUT * 32767, -32767, 32767))
            return e, ("cond", flag)

        if et in (ET_SINE, ET_SQR, ET_TRI, ET_STUP, ET_STDN) and s["per"]:
            flag = {ET_SINE: sd.SDL_HAPTIC_SINE, ET_SQR: sd.SDL_HAPTIC_SINE,
                    ET_TRI: sd.SDL_HAPTIC_TRIANGLE, ET_STUP: sd.SDL_HAPTIC_SAWTOOTHUP,
                    ET_STDN: sd.SDL_HAPTIC_SAWTOOTHDOWN}[et]
            if not self.w.can(flag):
                return None, None
            mag, off, phase, period = s["per"]
            e.type = flag
            p = e.periodic
            p.type = flag
            self._dir(p.direction)
            p.length = sd.SDL_HAPTIC_INFINITY
            minp = int(c.get("periodic_min_period_ms", 0) or 0)
            p.period = int(clamp(max(period or 20, minp), 1, 65535))
            direction_gain = abs(s.get("direction_factor", 1.0))
            p.magnitude = int(clamp(abs(mag) / norm * 32767 * direction_gain * c["periodic_scale"] * scale, 0, 32767))
            p.offset = int(clamp(off / norm * 32767 * s["sign"] * inv, -32767, 32767))
            p.phase = int(clamp(phase or 0, 0, 35999))   # centésimos de grau (vjoyinterface.h = SDL)
            return e, ("per", flag)

        return None, None

    @staticmethod
    def _sig(eff):
        return ctypes.string_at(ctypes.addressof(eff), ctypes.sizeof(eff))

    def sync(self, idx, start=False):
        """Atualiza SÓ o efeito da categoria do (idx, tipo). Nunca toca em outros.

        Se a categoria é "cond" e o subtipo (flag SDL) mudou, destrói e recria o
        slot — o SDL não permite trocar tipo de condição via UpdateEffect.
        Atualizações respeitam update_hz (limite de taxa) e, na força constante,
        slew_per_sec (rampa): ver _push().
        """
        if not self.cfg["enabled"] or not self.w.haptic:
            return
        sd = self.sdl2
        s = self.state(idx)
        eff, kind = self.build(s, idx[0])
        if eff is None:
            return
        if isinstance(kind, tuple):
            cat_str, subtype = kind[0], kind[1]
        else:
            cat_str, subtype = kind, None
        slot = self._slot_for_key(idx)
        entry = self.sdl_fx.get(slot)
        now = self.clock()
        is_const = cat_str == "const"

        # Se o subtipo mudou (spring→damper, sine→triangle), recria o efeito.
        if entry is not None and subtype is not None and entry.get("subtype") != subtype:
            self._destroy_sdl(slot)
            entry = None

        created = False
        if entry is None:
            out = None
            if is_const:
                target = eff.constant.level
                out = 0.0 if (self._slew() > 0 and not s["playing"]) else float(target)
                eff.constant.level = int(out)
            eid = sd.SDL_HapticNewEffect(self.w.haptic, eff)
            if eid < 0:
                self.log(f"falha ao criar efeito {slot}: {sd.SDL_GetError().decode()}")
                return
            entry = {"id": eid, "subtype": subtype, "cat": cat_str, "key": idx,
                     "sig": self._sig(eff), "last_t": now, "dirty": False,
                     "stopping": False, "eff": eff}
            if is_const:
                entry["out"], entry["target"] = out, float(target)
                entry["dirty"] = out != target       # ainda precisa chegar ao alvo
            self.sdl_fx[slot] = entry
            created = True
        else:
            entry["key"], entry["eff"] = idx, eff
            if is_const:
                entry["target"] = float(eff.constant.level)
                if start and self._slew() > 0:
                    # (re)início: a força sobe em rampa a partir de zero
                    entry["out"], entry["sig"], entry["stopping"] = 0.0, None, False
                    self._push(slot, now, force=True)
                else:
                    entry["dirty"] = True
                    self._push(slot, now)
            else:
                entry["dirty"] = True
                self._push(slot, now)
        if (start or created) and s["playing"]:
            sd.SDL_HapticRunEffect(self.w.haptic, self.sdl_fx[slot]["id"], 1)

    def _push(self, slot, now, force=False):
        """Envia ao volante o estado atual do slot, respeitando taxa máxima e slew."""
        entry = self.sdl_fx.get(slot)
        if entry is None or not (entry.get("dirty") or force):
            return
        iv = self._interval()
        last = entry["last_t"]
        if not force and iv > 0 and now - last < iv - 1e-9:
            entry["dirty"] = True                 # adiado: tick() reenvia
            return
        eff = entry["eff"]
        done = True
        if entry["cat"] == "const":
            target = 0.0 if entry["stopping"] else entry["target"]
            out = entry["out"]
            slew = self._slew()
            playing = bool(self.fx.get(entry["key"], {}).get("playing"))
            if force:
                pass                               # reinício: usa 'out' como está (0)
            elif slew > 0 and playing:
                dt = min(max(now - last, 0.0), iv if iv > 0 else 0.02)
                step = slew * 32767.0 * dt
                out = target if abs(target - out) <= step else out + (step if target > out else -step)
            else:
                out = target
            entry["out"] = out
            eff.constant.level = int(round(out))
            done = out == target
        sig = self._sig(eff)
        if force or sig != entry.get("sig"):
            if self.sdl2.SDL_HapticUpdateEffect(self.w.haptic, entry["id"], eff) < 0:
                self.log(f"falha ao atualizar efeito {slot}: {self.sdl2.SDL_GetError().decode()}")
            else:
                entry["sig"] = sig
            entry["last_t"] = now
        entry["dirty"] = not done
        if done and entry.get("stopping"):
            entry["stopping"] = False
            st = self.fx.get(entry["key"])
            if st is not None:
                st["playing"] = False
            self.sdl2.SDL_HapticStopEffect(self.w.haptic, entry["id"])
            self.log(f"efeito {slot[0]}: STOP efetivo {slot[1]} (fim da rampa)")

    def stop_all(self, keep=None):
        for key, st in self.fx.items():
            if key[0] != keep:
                st["playing"] = False
        for sl in [x for x in self.pending_stops if x[0] != keep]:
            self.pending_stops.pop(sl, None)
        if self.w.haptic:
            self.sdl2.SDL_HapticStopAll(self.w.haptic)
        if keep is not None and self.w.haptic:
            # Reenvia RunEffect nos efeitos do idx que sobreviveu.
            for key, st in self.fx.items():
                if key[0] == keep and st["playing"]:
                    entry = self.sdl_fx.get(self._slot_for_key(key))
                    if entry is not None:
                        self.sdl2.SDL_HapticRunEffect(self.w.haptic, entry["id"], 1)

    def snapshot(self):
        """Estado resumido para a GUI (via telemetria): força constante enviada e efeitos tocando."""
        const, active = None, []
        for slot, entry in self.sdl_fx.items():
            st = self.fx.get(entry["key"])
            if not st or not st["playing"]:
                continue
            if entry["cat"] == "const":
                const = (entry.get("out") if entry.get("out") is not None else entry["eff"].constant.level) / 32767.0
                const = max(-1.0, min(1.0, const))
            active.append(ET_NAMES.get(entry["key"][1], str(entry["key"][1])))
        return {"const": None if const is None else round(const, 3),
                "active": sorted(set(active)), "slots": len(self.sdl_fx)}

    def shutdown(self):
        if self.w.haptic:
            self.sdl2.SDL_HapticStopAll(self.w.haptic)
            for slot in list(self.sdl_fx):
                self._destroy_sdl(slot)
            self.fx.clear()
