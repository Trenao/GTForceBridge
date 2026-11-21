"""Autocalibração de FFB: mede a resposta do volante e sugere fatores (nunca aplica sem aprovação)."""
from __future__ import annotations

import json
import statistics
import sys
import time
import threading

from .autocal_profile import apply_autocal_profile
from .config import AUTOCAL_MAX_PLAUSIBLE_CENTER_OFFSET, AUTOCAL_MAX_PLAUSIBLE_CONST_SCALE
from .curves import clamp
from .paths import AUTOCAL_REPORT_PATH, CONFIG_PATH
from .wheel import Wheel, init_sdl


class FfbAutocal:
    """Mede a resposta REAL do volante (sensor hall) e sugere fatores de correção.

    Correções aplicadas vs. versão anterior:
      - Estabilização ativa: espera |vel| < 0.02 por 200 ms (timeout 2 s).
      - Descarte de 60% iniciais (era 30%) — motor pesado leva > 1 s para parar.
      - Detecta saturação (|median| > 0.85) e marca teste como INVÁLIDO.
      - Invert vem do SPRING (não saturante), não da constante.
      - center_offset vem de spring_off0.median, não de pos_rest (atrito estático).
      - constant_scale derivado de teste NÃO saturado (±15%); se saturar, 1.0.
      - Deadband: mede excursão durante o efeito, nos dois sentidos, com
        baseline por repetição; registra ausência de resposta sem inventar limiar.
      - Sine removido do pacote (só poluía o relatório).
    """

    SAMPLE_HZ = 500
    SETTLE_TIMEOUT_MS = 2000
    SETTLE_VEL_EPS = 0.02
    SETTLE_HOLD_MS = 200
    DISCARD_FRACTION = 0.60
    REPEATS = 2
    SATURATION_THRESHOLD = 0.85
    DEADBAND_DISP_EPS = 0.08     # acima do ruído/assentamento medido (~0.04 a 1%)

    def __init__(self, sdl2, wheel, cfg, verbose=False, progress_cb=None):
        self.sdl2 = sdl2
        self.w = wheel
        self.cfg = cfg
        self.verbose = verbose
        self.progress_cb = progress_cb or (lambda *_: None)
        self._stop = threading.Event()
        self.steer_axis = int(cfg["axes"]["steering"])

    # -------- amostragem --------
    def _sample_steady(self, duration_ms, label):
        self.w.update()
        n = max(1, int(self.SAMPLE_HZ * duration_ms / 1000.0))
        dt = 1.0 / self.SAMPLE_HZ
        xs = []
        next_t = time.perf_counter()
        for _ in range(n):
            if self._stop.is_set():
                break
            self.w.update()
            xs.append(self.w.axis(self.steer_axis))
            next_t += dt
            delay = next_t - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
        if not xs:
            return {"n": 0, "label": label}
        skip = int(len(xs) * self.DISCARD_FRACTION)
        tail = xs[skip:] if len(xs) - skip >= 5 else xs
        tail_sorted = sorted(tail)
        median = tail_sorted[len(tail_sorted) // 2]
        if len(tail) >= 2:
            vel = (tail[-1] - tail[0]) / max((len(tail) - 1) * dt, 1e-6)
        else:
            vel = 0.0
        return {"n": len(xs), "median": median, "first": tail[0],
                "last": tail[-1], "vel": vel, "span": max(tail) - min(tail),
                "min": min(tail), "max": max(tail), "label": label}

    def _settle(self):
        """Espera o motor parar antes do próximo teste (até SETTLE_TIMEOUT_MS)."""
        deadline = time.perf_counter() + self.SETTLE_TIMEOUT_MS / 1000.0
        hold_start = None
        dt = 1.0 / self.SAMPLE_HZ
        last = self.w.axis(self.steer_axis)
        while time.perf_counter() < deadline and not self._stop.is_set():
            self.w.update()
            cur = self.w.axis(self.steer_axis)
            vel = abs(cur - last) / dt
            last = cur
            if vel < self.SETTLE_VEL_EPS:
                if hold_start is None:
                    hold_start = time.perf_counter()
                elif (time.perf_counter() - hold_start) * 1000.0 >= self.SETTLE_HOLD_MS:
                    return True
            else:
                hold_start = None
            time.sleep(dt)
        return False

    # -------- efeitos de teste --------
    def _new_const(self, frac):
        sd = self.sdl2
        e = sd.SDL_HapticEffect()
        e.type = sd.SDL_HAPTIC_CONSTANT
        e.constant.type = sd.SDL_HAPTIC_CONSTANT
        e.constant.direction.type = sd.SDL_HAPTIC_STEERING_AXIS
        e.constant.length = sd.SDL_HAPTIC_INFINITY
        e.constant.level = int(clamp(frac, -1.0, 1.0) * 32767)
        return e

    def _new_spring(self, sat_frac, coeff_frac, offset_frac):
        sd = self.sdl2
        e = sd.SDL_HapticEffect()
        e.type = sd.SDL_HAPTIC_SPRING
        c = e.condition
        c.type = sd.SDL_HAPTIC_SPRING
        c.direction.type = sd.SDL_HAPTIC_STEERING_AXIS
        c.length = sd.SDL_HAPTIC_INFINITY
        sat = int(clamp(sat_frac, 0.0, 1.0) * 65535)
        coeff = int(clamp(coeff_frac, 0.0, 1.0) * 32767)
        off = int(clamp(offset_frac, -1.0, 1.0) * 32767)
        c.right_sat[0] = c.left_sat[0] = sat
        c.right_coeff[0] = c.left_coeff[0] = coeff
        c.center[0] = off
        c.deadband[0] = 0
        return e

    def _run_effect(self, effect, duration_ms, label):
        sd = self.sdl2
        if not self.w.haptic:
            return {"n": 0, "label": label}
        eid = sd.SDL_HapticNewEffect(self.w.haptic, effect)
        if eid < 0:
            return {"n": 0, "label": label, "error": sd.SDL_GetError().decode()}
        try:
            sd.SDL_HapticRunEffect(self.w.haptic, eid, 1)
            stats = self._sample_steady(duration_ms, label)
        finally:
            sd.SDL_HapticStopEffect(self.w.haptic, eid)
            sd.SDL_HapticDestroyEffect(self.w.haptic, eid)
            self._settle()
        return stats

    def _measure_repeated(self, effect_factory, duration_ms, label):
        results = []
        for r in range(self.REPEATS):
            if self._stop.is_set():
                break
            self.progress_cb(f"{label} ({r+1}/{self.REPEATS})", None)
            eff = effect_factory()
            st = self._run_effect(eff, duration_ms, f"{label}#{r+1}")
            if st.get("n", 0) > 0:
                results.append(st)
        if not results:
            return {"n": 0, "label": label}
        med = statistics.median(r["median"] for r in results)
        return {"median": med, "n": sum(r["n"] for r in results),
                "vel": statistics.median(r["vel"] for r in results),
                "span": max(r["span"] for r in results),
                "min": min(r["min"] for r in results),
                "max": max(r["max"] for r in results),
                "runs": results, "label": label,
                "saturated": abs(med) > self.SATURATION_THRESHOLD}

    # -------- recentralização e teste direcional --------
    CENTER_TOL = 0.05
    CONST_WINDOW_MS = 1000
    CONST_MOVE_EPS = 0.05      # deslocamento mínimo para contar como "moveu"
    CONST_STOP_LIMIT = 0.90    # perto do batente: encerra a janela

    def _recenter(self):
        """Leva o volante ao centro com spring forte (o GT Force não tem autocenter próprio).

        Sem isso, cada teste de força constante começa de onde o anterior parou
        (geralmente no batente) e a posição final não diz nada sobre o motor."""
        sd = self.sdl2
        if not self.w.haptic:
            return False
        eid = sd.SDL_HapticNewEffect(self.w.haptic, self._new_spring(1.0, 1.0, 0.0))
        if eid < 0:
            return False
        ok = False
        try:
            sd.SDL_HapticRunEffect(self.w.haptic, eid, 1)
            dt = 1.0 / self.SAMPLE_HZ
            deadline = time.perf_counter() + 3.0
            hold = None
            last = self.w.axis(self.steer_axis)
            while time.perf_counter() < deadline and not self._stop.is_set():
                self.w.update()
                cur = self.w.axis(self.steer_axis)
                vel = abs(cur - last) / dt
                last = cur
                if abs(cur) < self.CENTER_TOL and vel < self.SETTLE_VEL_EPS * 2:
                    hold = hold or time.perf_counter()
                    if time.perf_counter() - hold >= 0.25:
                        ok = True
                        break
                else:
                    hold = None
                time.sleep(dt)
        finally:
            sd.SDL_HapticStopEffect(self.w.haptic, eid)
            sd.SDL_HapticDestroyEffect(self.w.haptic, eid)
            self._settle()
        return ok

    def _measure_const_direction(self, frac, label):
        """Janela curta de força constante a partir do centro.

        Mede o deslocamento ASSINADO (eixo SDL) e a velocidade inicial. O volante
        não tem força restauradora aqui: ele só anda até o batente, então a
        posição final não serve de escala; o que vale é o SENTIDO e o quanto
        andou/acelerou no começo."""
        sd = self.sdl2
        dt = 1.0 / self.SAMPLE_HZ
        runs = []
        for _ in range(self.REPEATS):
            if self._stop.is_set():
                break
            centered = self._recenter()
            base = []
            for _i in range(int(self.SAMPLE_HZ * 0.2)):
                self.w.update()
                base.append(self.w.axis(self.steer_axis))
                time.sleep(dt)
            if len(base) < 5:
                continue
            baseline = statistics.median(base)
            eid = sd.SDL_HapticNewEffect(self.w.haptic, self._new_const(frac))
            if eid < 0:
                return {"n": 0, "label": label,
                        "error": sd.SDL_GetError().decode(errors="replace")}
            xs, ts = [], []
            try:
                if sd.SDL_HapticRunEffect(self.w.haptic, eid, 1) < 0:
                    continue
                t0 = time.perf_counter()
                next_t = t0
                while (time.perf_counter() - t0) * 1000.0 < self.CONST_WINDOW_MS:
                    if self._stop.is_set():
                        break
                    self.w.update()
                    x = self.w.axis(self.steer_axis)
                    xs.append(x - baseline)
                    ts.append(time.perf_counter() - t0)
                    if abs(x) > self.CONST_STOP_LIMIT:
                        break
                    next_t += dt
                    delay = next_t - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
            finally:
                sd.SDL_HapticStopEffect(self.w.haptic, eid)
                sd.SDL_HapticDestroyEffect(self.w.haptic, eid)
            if len(xs) < 5:
                continue
            peak = max(xs, key=abs)
            # velocidade inicial: inclinação entre 0 e o instante em que cruzou 25% do pico
            k = next((i for i, v in enumerate(xs) if abs(v) >= 0.25 * abs(peak)), len(xs) - 1)
            vel0 = xs[k] / max(ts[k], 1e-3) if ts[k] > 0 else 0.0
            runs.append({"delta": peak, "vel0": vel0, "t_window": ts[-1],
                         "start_centered": centered, "baseline": baseline, "n": len(xs)})
        if not runs:
            return {"n": 0, "label": label}
        delta = statistics.median(r["delta"] for r in runs)
        return {"median": delta,                      # deslocamento assinado (nome mantido p/ a GUI)
                "vel0": statistics.median(r["vel0"] for r in runs),
                "span": max(abs(r["delta"]) for r in runs) - min(abs(r["delta"]) for r in runs),
                "n": sum(r["n"] for r in runs), "runs": runs, "label": label,
                "moved": abs(delta) > self.CONST_MOVE_EPS,
                "hit_stop": any(abs(r["baseline"] + r["delta"]) > self.CONST_STOP_LIMIT for r in runs),
                "saturated": False}                   # bater no batente é esperado; não invalida

    # -------- pacote --------
    def run(self):
        report = {"started": time.time(), "device": {
            "name": self.w.name, "vid": self.w.vendor, "pid": self.w.product,
            "has_haptic": bool(self.w.haptic)}, "tests": {}}
        if not self.w.haptic:
            report["error"] = "volante sem haptic"
            return report, {}
        sd = self.sdl2
        if self.w.can(sd.SDL_HAPTIC_GAIN):
            sd.SDL_HapticSetGain(self.w.haptic, 100)

        # Repouso
        self.progress_cb("Repouso", 0.0)
        self._settle()
        rest = self._sample_steady(1500, "repouso")
        report["tests"]["rest"] = rest

        # Constantes NÃO saturantes (15%)
        self.progress_cb("Constante +15%", 0.10)
        cpos = self._measure_const_direction(0.15, "const_+15")
        report["tests"]["const_pos"] = cpos
        self.progress_cb("Constante -15%", 0.20)
        cneg = self._measure_const_direction(-0.15, "const_-15")
        report["tests"]["const_neg"] = cneg
        # Constante forte (25%): só diagnóstico (velocidade/sentido)
        self.progress_cb("Constante +25%", 0.30)
        cstrong = self._measure_const_direction(0.25, "const_+25")
        report["tests"]["const_strong"] = cstrong

        # Springs
        self.progress_cb("Spring offset 0", 0.42)
        spr0 = self._measure_repeated(lambda: self._new_spring(1.0, 1.0, 0.0), 2500, "spring_off0")
        report["tests"]["spring_off0"] = spr0
        self.progress_cb("Spring offset +50%", 0.52)
        sprP = self._measure_repeated(lambda: self._new_spring(1.0, 1.0, 0.5), 2500, "spring_offP")
        report["tests"]["spring_off_pos"] = sprP
        self.progress_cb("Spring offset -50%", 0.62)
        sprN = self._measure_repeated(lambda: self._new_spring(1.0, 1.0, -0.5), 2500, "spring_offN")
        report["tests"]["spring_off_neg"] = sprN

        # Deadband
        self.progress_cb("Deadband do motor", 0.78)
        dead_res = self._find_deadband()
        report["tests"]["deadband"] = dead_res

        # Derivação
        self.progress_cb("Derivando fatores", 0.97)
        suggested = self._derive(cpos, cneg, cstrong, spr0, sprP, sprN, dead_res)
        report["suggested"] = suggested
        report["finished"] = time.time()
        self.progress_cb("Concluído", 1.0)
        return report, suggested

    def _measure_deadband_direction(self, magnitude, label):
        """Mede excursão do eixo durante a força, relativa ao repouso pré-teste.

        Usa percentil 90 da excursão absoluta para não perder um movimento
        inicial que depois estabilize. O baseline é medido novamente em cada
        repetição, evitando confundir centro deslocado com resposta do motor.
        """
        sd = self.sdl2
        runs = []
        for repeat in range(self.REPEATS):
            if self._stop.is_set():
                break
            self._recenter()
            baseline_samples = []
            dt = 1.0 / self.SAMPLE_HZ
            next_t = time.perf_counter()
            for _ in range(max(1, int(self.SAMPLE_HZ * 0.30))):
                if self._stop.is_set():
                    break
                self.w.update()
                baseline_samples.append(self.w.axis(self.steer_axis))
                next_t += dt
                delay = next_t - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
            if len(baseline_samples) < 5:
                continue
            baseline = statistics.median(baseline_samples)

            effect = self._new_const(magnitude)
            eid = sd.SDL_HapticNewEffect(self.w.haptic, effect)
            if eid < 0:
                return {"n": 0, "label": label,
                        "error": sd.SDL_GetError().decode(errors="replace")}
            samples = []
            try:
                if sd.SDL_HapticRunEffect(self.w.haptic, eid, 1) < 0:
                    continue
                next_t = time.perf_counter()
                for _ in range(max(1, int(self.SAMPLE_HZ * 1.10))):
                    if self._stop.is_set():
                        break
                    self.w.update()
                    samples.append(self.w.axis(self.steer_axis))
                    next_t += dt
                    delay = next_t - time.perf_counter()
                    if delay > 0:
                        time.sleep(delay)
            finally:
                sd.SDL_HapticStopEffect(self.w.haptic, eid)
                sd.SDL_HapticDestroyEffect(self.w.haptic, eid)
                self._settle()

            if len(samples) >= 5:
                excursions = sorted(abs(x - baseline) for x in samples)
                p90 = excursions[min(len(excursions) - 1, int(0.90 * len(excursions)))]
                signed = statistics.median(samples) - baseline
                runs.append({"baseline": baseline, "median_delta": signed,
                             "peak_delta": max(excursions), "p90_delta": p90,
                             "n": len(samples)})

        if not runs:
            return {"n": 0, "label": label, "runs": []}
        return {
            "n": sum(r["n"] for r in runs),
            "displacement": statistics.median(r["p90_delta"] for r in runs),
            "peak_displacement": max(r["peak_delta"] for r in runs),
            "median_delta": statistics.median(r["median_delta"] for r in runs),
            "baseline": statistics.median(r["baseline"] for r in runs),
            "runs": runs, "label": label,
        }

    def _find_deadband(self):
        # Varredura crescente nos dois sentidos. O primeiro nível que move
        # consistentemente o volante é o limiar mínimo observado do motor.
        levels = (0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.18, 0.25)
        tests = []
        for pct in levels:
            if self._stop.is_set():
                break
            self.progress_cb(f"Deadband: testando +/-{int(pct*100)}%", None)
            positive = self._measure_deadband_direction(pct, f"dead_pos_{pct:.2f}")
            negative = self._measure_deadband_direction(-pct, f"dead_neg_{pct:.2f}")
            valid = (positive.get("n", 0) > 0 and negative.get("n", 0) > 0)
            p_disp = positive.get("displacement", 0.0)
            n_disp = negative.get("displacement", 0.0)
            tests.append({"magnitude": pct, "positive": positive,
                          "negative": negative, "valid": valid})
            if not valid:
                continue
            # Resposta real = deslocamento ASSINADO grande e em sentidos opostos
            # (ruído/assentamento dá valores pequenos e sem relação com o sinal da força).
            p_d = positive.get("median_delta", 0.0)
            n_d = negative.get("median_delta", 0.0)
            opposite = p_d * n_d < 0
            moved_pos = p_disp > self.DEADBAND_DISP_EPS and abs(p_d) > self.DEADBAND_DISP_EPS and opposite
            moved_neg = n_disp > self.DEADBAND_DISP_EPS and abs(n_d) > self.DEADBAND_DISP_EPS and opposite
            if moved_pos or moved_neg:
                # Registra se o limiar apareceu em apenas um dos sentidos.
                return {
                    "min_magnitude": pct,
                    "displacement": max(p_disp, n_disp),
                    "positive_displacement": p_disp,
                    "negative_displacement": n_disp,
                    "positive_responded": moved_pos,
                    "negative_responded": moved_neg,
                    "status": "response" if moved_pos and moved_neg else "one_direction_only",
                    "tests": tests,
                }
        return {
            "min_magnitude": 0.0, "displacement": 0.0,
            "positive_displacement": 0.0, "negative_displacement": 0.0,
            "positive_responded": False, "negative_responded": False,
            "status": "no_response" if not self._stop.is_set() else "cancelled",
            "tests": tests,
        }

    def _derive(self, cpos, cneg, cstrong, spr0, sprP, sprN, deadband):
        def sat(d):
            return bool(d.get("saturated")) or d.get("n", 0) == 0

        # ---- invert: da FORÇA CONSTANTE (é ela que ffb.invert inverte) ----
        # O sinal da constante NÃO segue o do spring neste hardware (medido: constante
        # positiva foi para a esquerda enquanto o spring com offset positivo foi para a
        # direita). Então o spring não decide o invert. Tomamos a direção da constante a
        # partir do centro: +15% deve mover o eixo SDL para o lado positivo; se foi para
        # o negativo (e -15% para o positivo), invert=True.
        inv = False
        inv_known = False
        spr0_m = spr0.get("median", 0.0)
        sprP_m = sprP.get("median", 0.0)
        sprN_m = sprN.get("median", 0.0)
        cpos_d = cpos.get("median", 0.0) if cpos.get("moved") else 0.0
        cneg_d = cneg.get("median", 0.0) if cneg.get("moved") else 0.0
        const_dir_conflict = False
        if not cpos_d and not cneg_d and cstrong.get("moved"):
            cpos_d = cstrong.get("median", 0.0)      # 15% abaixo do limiar do motor: usa o 25%
        if cpos_d > 0 and cneg_d < 0:
            inv_known, inv = True, False
        elif cpos_d < 0 and cneg_d > 0:
            inv_known, inv = True, True
        elif cpos_d or cneg_d:
            # só um sentido respondeu, ou os dois foram para o mesmo lado: não decide
            const_dir_conflict = bool(cpos_d and cneg_d)
            if cpos_d and not cneg_d:
                inv_known, inv = True, cpos_d < 0
            elif cneg_d and not cpos_d:
                inv_known, inv = True, cneg_d > 0

        # ---- center_offset: do SPRING off0 (atrito estático engana pos_rest) ----
        # Convenção: center_offset = onde o volante ASSENTA com o spring centrado em 0
        # (positivo = à direita). O tradutor compensa deslocando o centro do spring em
        # -center_offset, para que ele assente em 0.
        center_offset = None
        if not sat(spr0) and abs(spr0_m) < AUTOCAL_MAX_PLAUSIBLE_CENTER_OFFSET:
            center_offset = round(spr0_m, 4)

        # ---- constant_scale: NÃO medido ----
        # Sem força restauradora, a posição final só diz "bateu no batente"; não há como
        # tirar uma escala confiável disso. Fica None (não sobrescreve o valor do usuário).
        constant_scale = None
        const_ok = bool(cpos.get("moved") and cneg.get("moved"))

        # ---- min_effective_magnitude: só se deadband válido ----
        dead_m = deadband.get("min_magnitude", 0.0)
        dead_known = deadband.get("status") == "response"
        # O modo stretch é simétrico. Só aplicamos um limiar se os dois
        # sentidos responderam; assim não mascaramos falha assimétrica.
        if deadband.get("status") != "response":
            dead_m = 0.0

        # ---- simetria (informativo): razão das velocidades iniciais -/+ ----
        sym = None
        vp, vn = abs(cpos.get("vel0", 0.0)), abs(cneg.get("vel0", 0.0))
        if const_ok and vp > 1e-3 and vn > 1e-3:
            sym = round(vn / vp, 3)
        spr_sym = 1.0
        if not sat(sprP) and not sat(sprN):
            if abs(sprP_m) > 1e-3 and abs(sprN_m) > 1e-3:
                spr_sym = abs(sprN_m) / abs(sprP_m)

        spring_returns = (not sat(spr0)) and abs(spr0_m) < 0.05

        # ---- veredito ----
        # +15% e -15% são os testes usados para derivar a escala constante.
        # Se QUALQUER um saturar/faltar, os dados deixam de ser confiáveis e
        # a calibração inteira não pode ser aprovada, mesmo que o spring volte
        # ao centro. O teste +25% é diagnóstico; saturação nele, isoladamente,
        # não invalida os testes principais. Saturação dos testes spring também
        # é registrada e rejeita quando o retorno ao centro não foi confirmado.
        constant_tests_saturated = False
        any_test_saturated = sat(spr0) or sat(sprP) or sat(sprN)
        # Aviso (a decisão de aplicar é sempre do usuário):
        warning_reason = ""
        if not inv_known:
            warning_reason = "força constante não moveu o volante nos dois sentidos: invert não medido"
        elif const_dir_conflict:
            warning_reason = "força constante foi para o mesmo lado nos dois sentidos"
        elif not spring_returns:
            warning_reason = "retorno do spring ao centro não confirmado"
        warning = bool(warning_reason)

        # Só entram na sugestão as chaves MEDIDAS. condition_scale e periodic_scale
        # nunca são medidos pela autocal (não há teste para eles), então não são tocados.
        out = {}
        if inv_known:
            out["invert"] = bool(inv)
        if center_offset is not None:
            out["center_offset"] = center_offset
        if dead_known:
            out["min_effective_magnitude"] = round(clamp(dead_m, 0.0, 0.25), 4)
            out["min_effect_mode"] = "stretch"
        if constant_scale is not None:
            out["constant_scale"] = constant_scale
        return {
            **out,
            "rejected": False,
            "warning": warning,
            "diagnostics": {
                "const_+15_median": round(cpos.get("median", 0.0), 4),
                "const_-15_median": round(cneg.get("median", 0.0), 4),
                "const_+25_median": round(cstrong.get("median", 0.0), 4),
                "spring_off0_median": round(spr0_m, 4),
                "spring_off_pos_median": round(sprP_m, 4),
                "spring_off_neg_median": round(sprN_m, 4),
                "symmetry_ratio": sym,
                "constant_tests_valid": bool(const_ok),
                "constant_vel0_pos": round(cpos.get("vel0", 0.0), 4),
                "constant_vel0_neg": round(cneg.get("vel0", 0.0), 4),
                "spring_dir_agrees_with_constant": (None if not inv_known else ((sprP_m > 0) != inv)),
                "spring_symmetry_ratio": round(spr_sym, 3),
                "spring_returns_to_center": bool(spring_returns),
                "deadband_min": round(deadband.get("min_magnitude", 0.0), 4),
                "deadband_status": deadband.get("status", "unknown"),
                "deadband_positive": round(deadband.get("positive_displacement", 0.0), 4),
                "deadband_negative": round(deadband.get("negative_displacement", 0.0), 4),
                "any_test_saturated": bool(any_test_saturated),
                "warning_reason": warning_reason,
                "warning": bool(warning),
                "rejected": False,
            }
        }

    def stop(self):
        self._stop.set()


def cmd_ffb_autocal(cfg, apply=False, verbose=False):
    sdl2 = init_sdl()
    wheel = Wheel(sdl2, cfg["device_match"], cfg.get("device_pids"))
    if not wheel.haptic:
        print("Volante sem haptic — autocalibração impossível.")
        sdl2.SDL_Quit(); return
    print(f"Autocalibração em '{wheel.name}' (VID=0x{wheel.vendor:04X} PID=0x{wheel.product:04X})")
    print("Deixe o volante SOLTO, jogos FECHADOS. Autocenter do driver deve estar OFF.\n")

    def progress(label, frac):
        if frac is not None:
            sys.stdout.write(f"\r[{frac*100:5.1f}%] {label:<40}")
        else:
            sys.stdout.write(f"\r         {label:<40}")
        sys.stdout.flush()

    ac = FfbAutocal(sdl2, wheel, cfg, verbose=verbose, progress_cb=progress)
    try:
        report, suggested = ac.run()
    except KeyboardInterrupt:
        ac.stop()
        print("\nCancelado.")
        wheel.close(); sdl2.SDL_Quit(); return

    print()
    try:
        with open(AUTOCAL_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"Relatório bruto salvo em {AUTOCAL_REPORT_PATH}")
    except OSError as e:
        print(f"[aviso] não conseguiu salvar relatório: {e}")

    print("\n--- Sugestões ---")
    for k, v in suggested.items():
        if k == "diagnostics":
            print("  diagnósticos:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")

    if suggested.get("warning"):
        reason = (suggested.get("diagnostics", {}) or {}).get("warning_reason", "medição fora do esperado")
        print(f"\n[AVISO] {reason}.")
        print("A sugestão continua disponível. Use --apply somente se quiser aplicá-la.")

    if apply:
        pid_key = f"0x{wheel.product:04X}"
        apply_autocal_profile(cfg["ffb"], pid_key, suggested)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        print("\nFatores APLICADOS em config.json (por PID e como defaults).")
    else:
        print("\nNada aplicado. Use --apply para gravar (ou aprove na GUI).")

    wheel.close(); sdl2.SDL_Quit()
