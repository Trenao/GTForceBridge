"""Aba FFB da GUI sem tkinter real: widgets falsos (MagicMock); pega erro de nome/atributo e confere o que é salvo."""
import copy
import unittest
from unittest.mock import MagicMock

from gtforce_bridge.config import DEFAULT_CONFIG
from gtforce_bridge.gui.ffb_tab import FfbTabMixin


class Var:
    def __init__(self, value=None):
        self.v = value
    def get(self):
        return self.v
    def set(self, v):
        self.v = v


class FakeTk:
    BooleanVar = DoubleVar = StringVar = Var


class FakeTtk:
    """Cada Label/Button/... é um MagicMock distinto (um mock único misturaria os widgets)."""
    def __getattr__(self, name):
        return lambda *a, **k: MagicMock()


class Host(FfbTabMixin):
    def __init__(self):
        self.tk, self.ttk = FakeTk, FakeTtk()
        self.messagebox = MagicMock()
        self.cfg = copy.deepcopy(DEFAULT_CONFIG)
        self.tab_ffb = MagicMock()
        self.saved = 0
    def section(self, parent, title):
        return MagicMock()
    def save_config(self):
        self.saved += 1


class FfbTab(unittest.TestCase):
    def host(self):
        h = Host()
        h.build_ffb()
        return h

    def test_builds_and_reads_defaults(self):
        h = self.host()
        self.assertEqual(h.ffb_choice["polar_zero"].get(), "east")
        self.assertTrue(h.ffb_flags["honor_duration"].get())

    def test_save_writes_every_option_and_clamps(self):
        h = self.host()
        h.ffb_num["update_hz"][0].set("5000")           # acima do máximo
        h.ffb_num["slew_per_sec"][0].set("2,5")         # vírgula decimal
        h.ffb_choice["polar_zero"].set("north")
        h.ffb_flags["honor_duration"].set(False)
        h.ffb_invert.set(True)
        h.save_ffb()
        f = h.cfg["ffb"]
        self.assertEqual(f["update_hz"], 1000)
        self.assertEqual(f["slew_per_sec"], 2.5)
        self.assertEqual(f["polar_zero"], "north")
        self.assertFalse(f["honor_duration"])
        self.assertTrue(f["invert"])
        self.assertEqual(h.saved, 1)

    def test_invalid_number_is_refused_without_saving(self):
        h = self.host()
        h.ffb_num["update_hz"][0].set("abc")
        h.save_ffb()
        self.assertEqual(h.saved, 0)
        h.messagebox.showwarning.assert_called_once()

    def test_save_syncs_autocal_profile(self):
        h = self.host()
        h.cfg["ffb"]["autocal_by_pid"] = {"0xC293": {"invert": False, "center_offset": 0.0}}
        h.ffb_invert.set(True)
        h.save_ffb()
        self.assertTrue(h.cfg["ffb"]["autocal_by_pid"]["0xC293"]["invert"])

    def test_live_update_handles_all_telemetry_shapes(self):
        h = self.host()
        h.update_ffb_live({"ffb": None})
        h.update_ffb_live({"ffb": {"const": -0.5, "active": ["CONST", "SPRING"]},
                           "caps": {"effects": ["CONSTANT"], "num_effects": 16, "num_playing": None, "axes": 1}})
        h.ffb_live_val.configure.assert_called_with(text="-50%")
        h.update_ffb_live({})                           # telemetria antiga, sem as chaves novas


if __name__ == "__main__":
    unittest.main()
