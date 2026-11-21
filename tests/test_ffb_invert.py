"""Inversão do FFB = negar o valor enviado ao motor, para QUALQUER valor/sinal recebido do jogo."""
import unittest

from gtforce_bridge.vjoy_protocol import EFF_START, ET_CONST, direction_ambiguous
from tests.test_ffb_translator import Rig


def final_level(invert, mag, idx=1, **cfg):
    r = Rig(invert=invert, **cfg)
    r.put("report", idx, ET_CONST, 255, 0, 0, 0)          # cartesiano, DirX=0 => sem inversão por direção
    r.put("constant", idx, mag)
    r.put("op", idx, EFF_START, 1)
    r.run(0.05)
    return r.levels()[-1]


class InvertIsPureNegation(unittest.TestCase):
    def test_any_value_any_sign(self):
        for mag in (10000, 5000, 1200, 7, -7, -1200, -5000, -10000):
            with self.subTest(mag=mag):
                normal, inverted = final_level(False, mag), final_level(True, mag)
                self.assertEqual(inverted, -normal)
                self.assertEqual(normal > 0, mag > 0)        # o sinal do jogo é preservado quando não inverte

    def test_scale_255_example(self):
        # "recebeu 255 passa para -255; -12 passa para 12" (magnitude_scale=255 => 255 = fundo de escala)
        self.assertEqual(final_level(False, 255, magnitude_scale=255), 32767)
        self.assertEqual(final_level(True, 255, magnitude_scale=255), -32767)
        self.assertEqual(final_level(True, -12, magnitude_scale=255), -final_level(False, -12, magnitude_scale=255))
        self.assertGreater(final_level(True, -12, magnitude_scale=255), 0)

    def test_negative_game_values_reach_the_motor_negative(self):
        # sem inversão, magnitude negativa do jogo chega NEGATIVA ao volante (o lado negativo não é descartado)
        self.assertLess(final_level(False, -4000), 0)

    def test_negation_also_with_min_effective_stretch(self):
        k = dict(min_effective_magnitude=0.12, min_effect_mode="stretch")
        for mag in (1100, -1100, 6000, -6000):
            with self.subTest(mag=mag):
                self.assertEqual(final_level(True, mag, **k), -final_level(False, mag, **k))
        self.assertAlmostEqual(final_level(False, 1100, **k) / 32767.0, 0.12 + 0.88 * 0.11, places=2)  # +11% -> ~+22%


class Diagnostics(unittest.TestCase):
    def test_ambiguity_flag(self):
        self.assertTrue(direction_ambiguous(True, 64, "east"))       # ~90° com zero=leste
        self.assertFalse(direction_ambiguous(True, 64, "north"))
        self.assertFalse(direction_ambiguous(False, 0, "east"))

    def test_snapshot_reports_direction_history_and_invert(self):
        r = Rig(invert=True, polar_zero="east")
        for byte in (63, 63, 191):                                   # ~89°, ~89°, ~269°
            r.put("report", 1, ET_CONST, 255, 1, byte, 0)
            r.put("constant", 1, 3000)
        r.put("op", 1, EFF_START, 1); r.run(0.05)
        s = r.tr.snapshot()
        self.assertEqual(s["dirs"][0], [90, 2])                      # ângulos em passos de 5°
        self.assertEqual(s["dirs"][1], [270, 1])
        self.assertTrue(s["inv"]); self.assertTrue(s["amb"])         # zero=leste (padrão): 269° é ambíguo


if __name__ == "__main__":
    unittest.main()
