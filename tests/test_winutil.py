import sys
import unittest
from unittest import mock

from gtforce_bridge import winutil


class FakeWinmm:
    def __init__(self, result=0):
        self.begun, self.ended, self.result = [], [], result

    def timeBeginPeriod(self, ms):
        self.begun.append(ms)
        return self.result

    def timeEndPeriod(self, ms):
        self.ended.append(ms)
        return 0


class Winutil(unittest.TestCase):
    def setUp(self):
        winutil._timer_ms = None

    def test_begin_end_are_paired_with_same_value(self):
        w = FakeWinmm()
        with mock.patch.object(winutil, "_winmm", lambda: w):
            self.assertTrue(winutil.begin_timer_resolution(1))
            self.assertTrue(winutil.begin_timer_resolution(1))     # idempotente
            winutil.end_timer_resolution()
            winutil.end_timer_resolution()                         # segundo End é no-op
        self.assertEqual((w.begun, w.ended), ([1], [1]))

    def test_error_code_is_failure(self):
        w = FakeWinmm(result=97)                                   # TIMERR_NOCANDO
        with mock.patch.object(winutil, "_winmm", lambda: w):
            self.assertFalse(winutil.begin_timer_resolution(1))
        self.assertIsNone(winutil._timer_ms)

    @unittest.skipIf(sys.platform == "win32", "só fora do Windows")
    def test_noop_outside_windows(self):
        self.assertFalse(winutil.begin_timer_resolution(1))
        self.assertFalse(winutil.set_high_priority())
        winutil.end_timer_resolution()


if __name__ == "__main__":
    unittest.main()
