"""Inicialização com o Windows (registro simulado), comando de autostart e padrões da seção app."""
import sys
import types
import unittest
from unittest import mock

from gtforce_bridge.config import DEFAULT_CONFIG


def fake_winreg(store):
    class K:
        def __enter__(s): return s
        def __exit__(s, *a): pass
    def query(k, n):
        if n not in store:
            raise OSError
        return store[n], 1
    def delete(k, n):
        if n not in store:
            raise FileNotFoundError
        del store[n]
    return types.SimpleNamespace(HKEY_CURRENT_USER=1, KEY_SET_VALUE=2, REG_SZ=1, OpenKey=lambda *a, **k: K(),
                                 SetValueEx=lambda k, n, r, t, v: store.__setitem__(n, v), QueryValueEx=query, DeleteValue=delete)


class Autostart(unittest.TestCase):
    def setUp(self):
        from gtforce_bridge.gui import tray
        self.tray, self.store = tray, {}
        p1 = mock.patch.dict(sys.modules, {"winreg": fake_winreg(self.store)}); p1.start(); self.addCleanup(p1.stop)
        p2 = mock.patch.object(tray, "IS_WINDOWS", True); p2.start(); self.addCleanup(p2.stop)

    def test_ligar_desligar(self):
        self.assertFalse(self.tray.is_autostart())
        self.tray.set_autostart(True)
        self.assertTrue(self.tray.is_autostart())
        self.assertIn("--tray", self.store[self.tray.RUN_NAME])
        self.tray.set_autostart(False)
        self.tray.set_autostart(False)          # remover duas vezes não pode falhar
        self.assertFalse(self.tray.is_autostart())

    def test_comando_aponta_para_main(self):
        cmd = self.tray.autostart_command()
        self.assertIn("main.py", cmd); self.assertTrue(cmd.endswith("--gui --tray"))

    def test_fora_do_windows_levanta(self):
        with mock.patch.object(self.tray, "IS_WINDOWS", False):
            with self.assertRaises(OSError):
                self.tray.set_autostart(True)
            self.assertFalse(self.tray.is_autostart())


class Defaults(unittest.TestCase):
    def test_app_defaults(self):
        app = DEFAULT_CONFIG["app"]
        self.assertTrue(app["minimize_to_tray"]); self.assertTrue(app["close_to_tray"])
        self.assertFalse(app["autorun_bridge"])        # início automático da ponte é opt-in


if __name__ == "__main__":
    unittest.main()
