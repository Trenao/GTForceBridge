import ctypes
import unittest

from gtforce_bridge import vjoy_protocol as p


class Protocol(unittest.TestCase):
    def test_struct_sizes_are_sane(self):
        for s in (p.FFB_EFF_REPORT, p.FFB_EFF_CONSTANT, p.FFB_EFF_RAMP,
                  p.FFB_EFF_COND, p.FFB_EFF_PERIOD, p.FFB_EFF_OP):
            self.assertGreater(ctypes.sizeof(s), 4)

    def test_effect_names_cover_types(self):
        for t in (p.ET_CONST, p.ET_SINE, p.ET_SPRNG, p.ET_DMPR, p.ET_FRCTN):
            self.assertIn(t, p.ET_NAMES)

    def test_report_layout_matches_vjoyinterface_h(self):
        # offsets esperados do vjoyinterface.h (vJoy 2.2.x) em ABI x64/Win (BOOL/enum=4 bytes)
        R = p.FFB_EFF_REPORT
        off = {n: getattr(R, n).offset for n, *_ in R._fields_}
        self.assertEqual((off["EffectType"], off["Duration"], off["SamplePrd"], off["StartDelay"]), (4, 8, 12, 14))
        self.assertEqual((off["Gain"], off["TrigerBtn"], off["AxesEnabledDirection"], off["Polar"]), (16, 17, 18, 20))
        self.assertEqual((off["Direction"], off["DirY"]), (24, 26))
        L = p.FFB_EFF_REPORT_LEGACY
        self.assertEqual((L.Gain.offset, L.Polar.offset, L.Direction.offset), (14, 16, 20))

    def test_layout_selection_and_direction(self):
        class New: Ffb_h_EffectBlockIndex = 1
        class Old: pass
        self.assertIs(p.report_class(New()), p.FFB_EFF_REPORT)
        self.assertIs(p.report_class(Old()), p.FFB_EFF_REPORT_LEGACY)
        self.assertEqual(p.direction_to_byte(0x7FFF, True), 255)
        self.assertIn(p.direction_to_byte(0x3FFF, True), (127, 128))   # 180 graus
        self.assertEqual(p.direction_to_byte(128, False), 128)


if __name__ == "__main__":
    unittest.main()
