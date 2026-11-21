"""Duração, loops, atraso, direção cartesiana/polar e rampa (header do vJoy + PID 1.0)."""
import math
import unittest

from gtforce_bridge.vjoy_protocol import (EFF_START, EFF_STOP, ET_CONST, ET_RAMP, cartesian_x)
from tests.test_ffb_translator import Rig, LV


def start(r, dur, delay=0, loops=1, mag=3000, idx=1):
    r.put("report", idx, ET_CONST, 255, 0, 0, dur, delay, None)
    r.put("constant", idx, mag)
    r.put("op", idx, EFF_START, loops)


class Duration(unittest.TestCase):
    def test_finite_duration_stops_by_itself(self):
        r = Rig(slew_per_sec=0)
        start(r, dur=300)
        r.run(0.2)
        self.assertEqual(r.sdl.ops("stop"), [])
        r.run(0.3)
        self.assertEqual(len(r.sdl.ops("stop")), 1)

    def test_infinite_duration_never_stops(self):
        for dur in (0xFFFF, 0):
            r = Rig(slew_per_sec=0)
            start(r, dur=dur)
            r.run(2.0)
            self.assertEqual(r.sdl.ops("stop"), [], f"dur={dur}")

    def test_loop_count_multiplies_duration(self):
        r = Rig(slew_per_sec=0)
        start(r, dur=200, loops=3)
        r.run(0.5)
        self.assertEqual(r.sdl.ops("stop"), [])
        r.run(0.2)
        self.assertEqual(len(r.sdl.ops("stop")), 1)

    def test_loop_255_is_forever(self):
        r = Rig(slew_per_sec=0)
        start(r, dur=100, loops=255)
        r.run(1.0)
        self.assertEqual(r.sdl.ops("stop"), [])

    def test_start_delay_defers_playing(self):
        r = Rig(slew_per_sec=0)
        start(r, dur=0xFFFF, delay=400)
        r.run(0.3)
        self.assertEqual(r.sdl.ops("run"), [])
        r.run(0.2)
        self.assertEqual(len(r.sdl.ops("run")), 1)

    def test_explicit_stop_cancels_deadline_and_delay(self):
        r = Rig(slew_per_sec=0)
        start(r, dur=300, delay=100)
        r.run(0.05)
        r.put("op", 1, EFF_STOP, 1)
        r.run(1.0)
        self.assertEqual(r.sdl.ops("run"), [])

    def test_honor_duration_off_restores_old_behavior(self):
        r = Rig(slew_per_sec=0, honor_duration=False)
        start(r, dur=100, delay=200)
        r.run(0.3)
        self.assertEqual(r.sdl.ops("stop"), [])
        self.assertEqual(len(r.sdl.ops("run")), 1)


class Direction(unittest.TestCase):
    def level(self, r):
        return r.levels()[-1]

    def test_cartesian_negative_dirx_pushes_left(self):
        r = Rig(slew_per_sec=0)
        r.put("report", 1, ET_CONST, 255, 0, 0, 0, 0, -1)
        r.put("constant", 1, 3000)
        r.put("op", 1, EFF_START, 1)
        r.run(0.05)
        self.assertAlmostEqual(self.level(r), -3000 * LV, delta=2)

    def test_cartesian_positive_dirx_pushes_right(self):
        r = Rig(slew_per_sec=0)
        r.put("report", 1, ET_CONST, 255, 0, 0, 0, 0, 1)
        r.put("constant", 1, 3000)
        r.put("op", 1, EFF_START, 1)
        r.run(0.05)
        self.assertAlmostEqual(self.level(r), 3000 * LV, delta=2)

    def test_cartesian_x_decoding_is_twos_complement(self):
        self.assertEqual(cartesian_x(0xFFFF, True), -1)
        self.assertEqual(cartesian_x(0x7FFF, True), 0x7FFF)
        self.assertEqual(cartesian_x(0xFF, False), -1)
        self.assertEqual(cartesian_x(0x01, False), 1)

    def polar(self, zero, byte):
        r = Rig(slew_per_sec=0, polar_zero=zero)
        r.put("report", 1, ET_CONST, 255, 1, byte, 0, 0, None)
        r.put("constant", 1, 3000)
        r.put("op", 1, EFF_START, 1)
        r.run(0.05)
        return self.level(r)

    def test_polar_north_is_directinput_convention(self):
        # 90° (byte 64) = leste = +X; 270° (byte 192) = oeste = -X
        self.assertGreater(self.polar("north", 64), 0)
        self.assertLess(self.polar("north", 192), 0)

    def test_polar_east_keeps_v06_behavior(self):
        self.assertGreater(self.polar("east", 0), 0)       # 0° = +X
        self.assertLess(self.polar("east", 128), 0)        # 180° = -X


class Ramp(unittest.TestCase):
    def test_ramp_uses_game_duration(self):
        r = Rig(slew_per_sec=0)
        r.put("report", 1, ET_RAMP, 255, 0, 0, 800, 0, None)
        r.put("ramp", 1, 1000, 9000)
        r.put("op", 1, EFF_START, 1)
        r.run(0.05)
        ramps = [i for _, op, _, i in r.sdl.calls if op in ("new", "update") and i[0] == "ramp"]
        self.assertTrue(ramps)
        self.assertEqual(ramps[-1][1], 800)


if __name__ == "__main__":
    unittest.main()
