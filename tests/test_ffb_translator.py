"""Comportamento do FfbTranslator com volante simulado: o que realmente chegaria ao motor."""
import queue
import unittest

import sdl2

from gtforce_bridge.config import DEFAULT_CONFIG
from gtforce_bridge.ffb_translator import FfbTranslator
from gtforce_bridge.vjoy_protocol import EFF_START, EFF_STOP, ET_CONST, ET_DMPR, ET_SPRNG
from tests.fakes import FakeClock, FakeSdl, FakeWheel

LV = 32767 / 10000.0      # magnitude do jogo (±10000) -> nível SDL


class Rig:
    def __init__(self, **cfg):
        self.clk = FakeClock()
        self.sdl = FakeSdl(self.clk)
        c = dict(DEFAULT_CONFIG["ffb"])
        c.update(cfg)
        self.tr = FfbTranslator(self.sdl, FakeWheel(), c, False, clock=self.clk)
        self.q = queue.Queue()

    def put(self, *ev):
        self.q.put(ev)

    def run(self, seconds, dt=0.002):
        for _ in range(int(round(seconds / dt))):
            self.tr.process(self.q)
            self.clk.advance(dt)

    def start_const(self, mag=0, idx=1):
        self.put("report", idx, ET_CONST, 255, 0, 0, 0)
        self.put("constant", idx, mag)
        self.put("op", idx, EFF_START, 1)
        self.run(0.02)

    def levels(self):
        return [lv for _, lv in self.sdl.const_levels()]


class Params(unittest.TestCase):
    def test_constant_stream_without_reports_is_followed(self):
        r = Rig()
        r.start_const(100)
        for i in range(1, 201):
            r.put("constant", 1, 100 + i * 40)
            r.run(0.01)
        self.assertAlmostEqual(r.levels()[-1], (100 + 200 * 40) * LV, delta=LV * 50)
        self.assertGreater(len(r.levels()), 150)

    def test_spring_damper_alternating_keep_their_own_params(self):
        r = Rig()
        want = {sdl2.SDL_HAPTIC_SPRING: int(2000 * LV), sdl2.SDL_HAPTIC_DAMPER: int(6000 * LV)}
        for _ in range(8):
            for et, coef in ((ET_SPRNG, 2000), (ET_DMPR, 6000)):
                r.put("report", 1, et, 255, 0, 0, 0)
                r.put("cond", 1, 0, 0, coef, coef, 10000, 10000, 0)
                r.put("op", 1, EFF_START, 1)
                r.run(0.02)
        sent = [info for _, op, _, info in r.sdl.calls if op in ("new", "update") and info[0] == "cond"]
        self.assertGreater(len(sent), 1)
        for _, flag, coef, _ in sent:
            self.assertAlmostEqual(coef, want[flag], delta=2, msg=f"coeficiente trocado para {flag}")

    def test_param_arriving_before_report_is_applied(self):
        r = Rig()
        r.put("cond", 1, 0, 0, 3000, 3000, 10000, 10000, 0)
        r.put("report", 1, ET_SPRNG, 255, 0, 0, 0)
        r.put("op", 1, EFF_START, 1)
        r.run(0.05)
        sent = [info for _, op, _, info in r.sdl.calls if op in ("new", "update") and info[0] == "cond"]
        self.assertTrue(sent)
        self.assertAlmostEqual(sent[-1][2], 3000 * LV, delta=2)

    def test_small_first_magnitudes_are_not_read_as_8bit(self):
        r = Rig(slew_per_sec=0, const_deadzone_pct=0)
        r.start_const(200)
        self.assertLess(max(r.levels()), 200 * LV + 5)
        r2 = Rig(slew_per_sec=0, const_deadzone_pct=0, magnitude_scale=255)
        r2.start_const(200)
        self.assertGreater(max(r2.levels()), 20000)

    def test_autocenter_is_disabled(self):
        self.assertEqual(Rig().sdl.autocenter, 0)
        self.assertIsNone(Rig(disable_autocenter=False).sdl.autocenter)


class Smoothness(unittest.TestCase):
    def test_step_in_force_becomes_a_linear_ramp(self):
        r = Rig(slew_per_sec=2.0)
        r.start_const(0)
        r.put("constant", 1, 8000)
        r.run(1.0)
        lv = r.levels()
        steps = [b - a for a, b in zip(lv, lv[1:]) if b != a]
        self.assertTrue(all(s >= 0 for s in steps), "a rampa não pode voltar")
        # passo por atualização = slew * 32767 * dt_calc (dt_calc limitado a min_interval)
        self.assertLessEqual(max(steps), 2.0 * 32767 * 0.01 + 3)
        self.assertAlmostEqual(lv[-1], 8000 * LV, delta=2)
        self.assertGreater(len(steps), 10)

    def test_reversal_goes_through_zero_without_jumping(self):
        r = Rig(slew_per_sec=2.0)
        r.start_const(6000)
        r.run(1.0)
        r.put("constant", 1, -6000)
        r.run(1.5)
        lv = r.levels()
        i = max(k for k, v in enumerate(lv) if v > 5000)
        tail = lv[i:]
        self.assertTrue(all(b <= a for a, b in zip(tail, tail[1:])), "inversão deve ser monótona")
        self.assertLessEqual(max(a - b for a, b in zip(tail, tail[1:])), 2.0 * 32767 * 0.01 + 3)
        self.assertAlmostEqual(tail[-1], -6000 * LV, delta=2)

    def test_stop_fades_out_then_stops_the_effect(self):
        r = Rig(slew_per_sec=2.0)
        r.start_const(6000)
        r.run(1.0)
        r.put("op", 1, EFF_STOP, 1)
        r.run(0.2)
        self.assertEqual([c for c in r.sdl.calls if c[1] == "stop"], [])
        r.run(1.5)
        self.assertEqual(r.levels()[-1], 0)
        self.assertEqual(len([c for c in r.sdl.calls if c[1] == "stop"]), 1)

    def test_restart_after_stop_ramps_from_zero(self):
        r = Rig(slew_per_sec=2.0)
        r.start_const(6000)
        r.run(1.0)
        r.put("op", 1, EFF_STOP, 1)
        r.run(3.0)
        n = len(r.levels())
        r.put("op", 1, EFF_START, 1)
        r.run(0.5)
        new = r.levels()[n:]
        self.assertEqual(new[0], 0)
        self.assertTrue(all(b >= a for a, b in zip(new, new[1:])))

    def test_noise_with_car_stopped_is_ignored(self):
        r = Rig(const_deadzone_pct=1.0)
        r.start_const(0)
        for i in range(100):
            r.put("constant", 1, 20 if i % 2 else -20)
            r.run(0.01)
        self.assertEqual(max(abs(v) for v in r.levels()), 0)

    def test_update_rate_is_capped(self):
        r = Rig(update_hz=100, slew_per_sec=0, const_deadzone_pct=0)
        r.start_const(0)
        n0 = len(r.levels())
        for i in range(500):
            r.put("constant", 1, 1000 + i * 7)
            r.run(0.002)
        self.assertLessEqual(len(r.levels()) - n0, 105)
        self.assertAlmostEqual(r.levels()[-1], (1000 + 499 * 7) * LV, delta=LV * 40)

    def test_no_slew_means_immediate(self):
        r = Rig(slew_per_sec=0, const_deadzone_pct=0)
        r.start_const(5000)
        self.assertAlmostEqual(r.levels()[-1], 5000 * LV, delta=2)


class Extras(unittest.TestCase):
    def test_min_effective_magnitude_stretches_small_forces(self):
        r = Rig(slew_per_sec=0, update_hz=0, min_effective_magnitude=0.10)
        r.start_const(100)                          # 1% da escala
        expected = (0.10 + 0.90 * 0.01) * 32767     # [0..1] -> [0.10..1]
        self.assertAlmostEqual(r.levels()[-1], expected, delta=3)
        r.put("constant", 1, 0)
        r.run(0.02)
        self.assertEqual(r.levels()[-1], 0)         # zero continua zero

    def test_start_during_fade_cancels_the_stop(self):
        r = Rig(slew_per_sec=2.0)
        r.start_const(6000)
        r.run(1.0)
        r.put("op", 1, EFF_STOP, 1)
        r.run(0.25)                                 # já em rampa de descida
        r.put("op", 1, EFF_START, 1)
        r.run(1.5)
        self.assertEqual([c for c in r.sdl.calls if c[1] == "stop"], [])
        self.assertAlmostEqual(r.levels()[-1], 6000 * LV, delta=2)

    def test_two_effects_same_index_in_one_batch_keep_their_params(self):
        r = Rig(update_hz=0)
        for et, coef in ((ET_SPRNG, 2000), (ET_DMPR, 6000)):     # tudo na fila antes de processar
            r.put("report", 1, et, 255, 0, 0, 0)
            r.put("cond", 1, 0, 0, coef, coef, 10000, 10000, 0)
            r.put("op", 1, EFF_START, 1)
        r.run(0.02)
        want = {sdl2.SDL_HAPTIC_SPRING: int(2000 * LV), sdl2.SDL_HAPTIC_DAMPER: int(6000 * LV)}
        for _, op, _, info in r.sdl.calls:
            if op in ("new", "update") and info[0] == "cond":
                self.assertAlmostEqual(info[2], want[info[1]], delta=2)

    def test_stale_parameter_without_report_is_discarded(self):
        r = Rig()
        r.put("cond", 7, 0, 0, 3000, 3000, 10000, 10000, 0)
        r.run(0.5)
        self.assertEqual(r.tr.pending, {})
        self.assertEqual([c for c in r.sdl.calls if c[1] == "new"], [])


if __name__ == "__main__":
    unittest.main()