"""Autocal: derivação só com chaves medidas, perfil por PID e cadeia até o motor."""
import unittest

from gtforce_bridge.autocal import FfbAutocal
from gtforce_bridge.autocal_profile import (AUTOCAL_KEYS, apply_autocal_profile, overlay_profile,
                                            pid_key, profile_for, reset_autocal)
from gtforce_bridge.config import DEFAULT_CONFIG
from gtforce_bridge.vjoy_protocol import EFF_START, ET_SPRNG
from tests.test_ffb_translator import Rig


def T(med, sat=False, n=5):
    return {"median": med, "saturated": sat, "n": n, "moved": abs(med) > 0.05, "vel0": med * 2}


def derive(cpos, cneg, spr0, sprP, sprN, dead):
    ac = FfbAutocal.__new__(FfbAutocal)
    return ac._derive(cpos, cneg, T(0.0), spr0, sprP, sprN, dead)


GOOD_DEAD = {"status": "response", "min_magnitude": 0.05}


class Derive(unittest.TestCase):
    def test_only_measured_keys(self):
        s = derive(T(0.3), T(-0.3), T(0.01), T(0.3), T(-0.3), GOOD_DEAD)
        self.assertNotIn("condition_scale", s)
        self.assertNotIn("periodic_scale", s)
        self.assertNotIn("constant_scale", s)             # posição final não dá escala
        self.assertEqual(s["center_offset"], 0.01)
        self.assertEqual(s["min_effective_magnitude"], 0.05)
        self.assertIs(s["invert"], False)

    def test_unmeasured_keys_are_omitted(self):
        bad = {"median": 0.0, "saturated": True, "n": 0}
        s = derive(bad, bad, bad, bad, bad, {"status": "none"})
        for k in AUTOCAL_KEYS:
            self.assertNotIn(k, s)

    def test_invert_comes_from_constant_not_spring(self):
        # caso real medido: +15% foi para a esquerda, spring offset+ foi para a direita
        s = derive(T(-0.9), T(0.7), T(0.012), T(0.52), T(-0.53), GOOD_DEAD)
        self.assertIs(s["invert"], True)
        self.assertFalse(s["warning"])
        self.assertIs(s["diagnostics"]["spring_dir_agrees_with_constant"], False)

    def test_constant_hitting_stop_is_not_a_warning(self):
        s = derive(T(-0.99), T(0.98), T(0.0), T(0.5), T(-0.5), GOOD_DEAD)
        self.assertFalse(s["warning"])

    def test_weak_15_falls_back_to_25(self):
        ac = FfbAutocal.__new__(FfbAutocal)
        s = ac._derive(T(0.0), T(0.0), T(-0.4), T(0.0), T(0.5), T(-0.5), GOOD_DEAD)
        self.assertIs(s["invert"], True)

    def test_no_constant_motion_leaves_invert_unknown(self):
        s = derive(T(0.0), T(0.0), T(0.0), T(0.5), T(-0.5), GOOD_DEAD)
        self.assertNotIn("invert", s)
        self.assertTrue(s["warning"])


class Chain(unittest.TestCase):
    def test_profile_overrides_only_measured(self):
        ffb = dict(DEFAULT_CONFIG["ffb"], condition_scale=0.7)
        apply_autocal_profile(ffb, pid_key(0xC294), {"constant_scale": 0.8, "center_offset": 0.02})
        self.assertEqual(ffb["constant_scale"], 0.8)
        self.assertEqual(ffb["condition_scale"], 0.7)            # intocado
        ffb2 = dict(DEFAULT_CONFIG["ffb"])
        self.assertEqual(overlay_profile(ffb2, profile_for(ffb, 0xC294)), ["center_offset", "constant_scale"])
        self.assertEqual(profile_for(ffb, 0x1234), {})

    def test_reset(self):
        ffb = dict(DEFAULT_CONFIG["ffb"])
        apply_autocal_profile(ffb, "0xC294", {"constant_scale": 0.8})
        reset_autocal(ffb)
        self.assertEqual(ffb["constant_scale"], DEFAULT_CONFIG["ffb"]["constant_scale"])
        self.assertEqual(ffb["autocal_by_pid"], {})

    def test_center_offset_reaches_motor_with_compensating_sign(self):
        r = Rig(center_offset=0.02)
        r.put("report", 1, ET_SPRNG, 255, 0, 0, 0)
        r.put("cond", 1, 0, 0, 3000, 3000, 10000, 10000, 0)
        r.put("op", 1, EFF_START, 1)
        r.run(0.05)
        self.assertAlmostEqual(r.sdl.last_center, -0.02 * 32767, delta=2)


class Periodic(unittest.TestCase):
    def test_phase_is_forwarded(self):
        from gtforce_bridge.vjoy_protocol import ET_SINE
        r = Rig()
        r.put("report", 1, ET_SINE, 255, 0, 0, 0)
        r.put("period", 1, 5000, 0, 9000, 100)
        r.put("op", 1, EFF_START, 1)
        r.run(0.05)
        self.assertEqual(r.sdl.last_phase, 9000)


if __name__ == "__main__":
    unittest.main()
