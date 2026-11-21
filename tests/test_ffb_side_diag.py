"""Diagnóstico do lado da força constante: regra de sinal, telemetria (snapshot) e resumo do --ffb-dump."""
import queue
import unittest

from gtforce_bridge.ffb_dump import DumpStats
from gtforce_bridge.vjoy_protocol import EFF_START, ET_CONST, direction_sign
from tests.test_ffb_translator import Rig

EAST_BYTE, WEST_BYTE = 64, 191      # ~90° e ~270° na escala 0-255 do PID


class DirectionSign(unittest.TestCase):
    def test_zero_east_loses_side_at_90_and_270(self):
        # documenta a limitação conhecida: com zero=leste, 90° e 270° são "indefinidos" (+1 para os dois)
        self.assertEqual(direction_sign(True, EAST_BYTE, None, "east"), 1.0)
        self.assertEqual(direction_sign(True, WEST_BYTE, None, "east"), 1.0)

    def test_zero_north_separates_90_and_270(self):
        self.assertEqual(direction_sign(True, EAST_BYTE, None, "north"), 1.0)
        self.assertEqual(direction_sign(True, WEST_BYTE, None, "north"), -1.0)

    def test_cartesian(self):
        self.assertEqual(direction_sign(False, 0, -5), -1.0)
        self.assertEqual(direction_sign(False, 0, 5), 1.0)
        self.assertEqual(direction_sign(False, 0, None), 1.0)


class Snapshot(unittest.TestCase):
    def test_game_raw_and_sent_and_direction_text(self):
        r = Rig(polar_zero="north")
        r.put("report", 1, ET_CONST, 255, 1, WEST_BYTE, 0)       # polar ~270° => esquerda sob "north"
        r.put("constant", 1, 5000); r.put("op", 1, EFF_START, 1); r.run(0.05)
        s = r.tr.snapshot()
        self.assertAlmostEqual(s["game"], 0.5, places=2)           # bruto: +5000/10000
        self.assertAlmostEqual(s["const"], -0.5, places=2)         # enviado: sinal da direção aplicado
        self.assertEqual(s["sign"], -1)
        self.assertTrue(s["dir"].startswith("polar"))

    def test_two_constant_effects_are_summed_and_clipped(self):
        r = Rig()
        for idx, mag in ((1, 3000), (2, 4000)):
            r.put("report", idx, ET_CONST, 255, 0, 0, 0)
            r.put("constant", idx, mag); r.put("op", idx, EFF_START, 1)
        r.run(0.05)
        s = r.tr.snapshot()
        self.assertAlmostEqual(s["const"], 0.7, places=2)          # o motor soma os efeitos
        r.put("report", 3, ET_CONST, 255, 0, 0, 0); r.put("constant", 3, 9000); r.put("op", 3, EFF_START, 1); r.run(0.05)
        self.assertEqual(r.tr.snapshot()["const"], 1.0)             # limitado a ±1

    def test_no_constant_playing_gives_none(self):
        s = Rig().tr.snapshot()
        self.assertIsNone(s["const"]); self.assertIsNone(s["game"])


def feed(stats, *events):
    q = queue.Queue()
    for e in events:
        q.put(e)
    stats.consume(q)


class DumpSides(unittest.TestCase):
    def test_game_sends_side_in_direction_only(self):
        """Magnitude sempre positiva; o lado vem da direção (90° direita, 270° esquerda): só 'north' separa."""
        st = DumpStats(clock=lambda: 0.0)
        for byte in (EAST_BYTE, WEST_BYTE, WEST_BYTE):
            feed(st, ("report", 1, ET_CONST, 255, 1, byte, 0, 0, 0), ("constant", 1, 4000))
        self.assertEqual((st.sides["east"][-1], st.sides["east"][1]), (0, 3))
        self.assertEqual((st.sides["north"][-1], st.sides["north"][1]), (2, 1))
        text = "\n".join(st.side_summary())
        self.assertIn("'north'", text)

    def test_game_sends_signed_magnitude(self):
        """Magnitude com os dois sinais e direção fixa: as duas convenções mostram os dois lados."""
        st = DumpStats(clock=lambda: 0.0)
        feed(st, ("report", 1, ET_CONST, 255, 0, 0, 0, 0, 1), ("constant", 1, 3000), ("constant", 1, -3000))
        for conv in ("east", "north"):
            self.assertEqual((st.sides[conv][-1], st.sides[conv][1]), (1, 1))
        self.assertNotIn("uma convenção", "\n".join(st.side_summary()))

    def test_one_sided_game(self):
        st = DumpStats(clock=lambda: 0.0)
        feed(st, ("report", 1, ET_CONST, 255, 0, 0, 0, 0, 1), ("constant", 1, -3000), ("constant", 1, -500))
        self.assertIn("um lado só", "\n".join(st.side_summary()))

    def test_empty(self):
        self.assertIn("nenhuma", DumpStats(clock=lambda: 0.0).side_summary()[0])


if __name__ == "__main__":
    unittest.main()
