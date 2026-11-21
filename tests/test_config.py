import json
import os
import tempfile
import unittest
from unittest import mock

from gtforce_bridge import config


class Config(unittest.TestCase):
    def test_deep_merge_keeps_defaults(self):
        out = config.deep_merge(config.DEFAULT_CONFIG, {"ffb": {"master_gain": 0.5}})
        self.assertEqual(out["ffb"]["master_gain"], 0.5)
        self.assertIn("constant_scale", out["ffb"])

    def test_load_creates_file_and_sanitizes(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with mock.patch.object(config, "CONFIG_PATH", path):
                cfg = config.load_config()
                self.assertTrue(os.path.exists(path))
                self.assertEqual(cfg["loop_hz"], 500)
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                data["ffb"]["constant_scale"] = 9.0      # absurdo -> volta a 1.0
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                self.assertEqual(config.load_config()["ffb"]["constant_scale"], 1.0)


class Novos(unittest.TestCase):
    def test_unknown_keys_flags_old_schema_but_not_valid_ones(self):
        old = {"wheel": {"name_contains": ["x"]}, "steering": {"deadzone_pct": 10, "expo": 1.0},
               "ffb": {"constant_gain": 1.0, "invert": True, "autocal_by_pid": {"0xC293": {"a": 1}}}}
        self.assertEqual(sorted(config.unknown_keys(old)),
                         ["ffb.constant_gain", "steering.deadzone_pct", "wheel"])
        self.assertEqual(config.unknown_keys(config.DEFAULT_CONFIG), [])

    def test_sanitize_clamps_new_ffb_params(self):
        c = config.deep_merge(config.DEFAULT_CONFIG, {"ffb": {
            "update_hz": 99999, "slew_per_sec": -3, "const_deadzone_pct": 80, "magnitude_scale": "abc"}})
        f = config._sanitize_ffb(c)["ffb"]
        self.assertEqual((f["update_hz"], f["slew_per_sec"], f["const_deadzone_pct"], f["magnitude_scale"]),
                         (1000.0, 0.0, 50.0, 0.0))


if __name__ == "__main__":
    unittest.main()
