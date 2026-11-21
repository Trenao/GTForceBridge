import unittest

from gtforce_bridge.curves import apply_curve, norm_pedal, norm_steering, to_vjoy, to_vjoy_pedal


class Curves(unittest.TestCase):
    def test_steering_center_and_extremes(self):
        cal = {"min": -1.0, "center": 0.0, "max": 1.0}
        self.assertEqual(norm_steering(0.0, cal), 0.0)
        self.assertEqual(norm_steering(1.0, cal), 1.0)
        self.assertEqual(norm_steering(-1.0, cal), -1.0)

    def test_pedal_range(self):
        cal = {"min": -1.0, "max": 1.0}
        self.assertEqual(norm_pedal(-1.0, cal), 0.0)
        self.assertEqual(norm_pedal(1.0, cal), 1.0)

    def test_deadzone_invert_and_gain(self):
        p = {"deadzone": 0.1, "expo": 0.0, "gain": 1.0, "invert": False}
        self.assertEqual(apply_curve(0.05, p), 0.0)
        self.assertEqual(apply_curve(1.0, p), 1.0)
        self.assertEqual(apply_curve(1.0, dict(p, invert=True)), -1.0)

    def test_vjoy_range(self):
        self.assertEqual(to_vjoy(-1.0), 1)
        self.assertEqual(to_vjoy(1.0), 32768)
        self.assertEqual(to_vjoy_pedal(0.0), 1)
        self.assertEqual(to_vjoy_pedal(1.0), 32768)


if __name__ == "__main__":
    unittest.main()
