"""GTFB.ico: existe, tem vários tamanhos, o .bat de compilação o aplica e a bandeja o usa."""
import os
import re
import unittest

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Icon(unittest.TestCase):
    def test_ico_is_multi_size_with_256(self):
        im = Image.open(os.path.join(ROOT, "GTFB.ico"))
        sizes = im.ico.sizes()
        self.assertIn((256, 256), sizes); self.assertIn((16, 16), sizes); self.assertIn((32, 32), sizes)

    def test_build_bat_applies_icon_and_finds_prepare(self):
        bat = open(os.path.join(ROOT, "3-compilar_gtforce_bridge.bat"), encoding="utf-8").read()
        self.assertRegex(bat, r'--icon "%ICON%"')
        self.assertRegex(bat, r'--add-data "%ICON%;\."')
        self.assertIn("1-PREPARAR_GTForceBridge.bat", bat)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "1-PREPARAR_GTForceBridge.bat")))

    def test_bats_reference_existing_files_and_keep_crlf(self):
        for n in ("1-PREPARAR_GTForceBridge.bat", "2-INICIAR_GTForceBridge.bat", "3-compilar_gtforce_bridge.bat"):
            raw = open(os.path.join(ROOT, n), "rb").read()
            self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"), n)       # CRLF em todas as linhas
        for n in ("2-INICIAR_GTForceBridge.bat",):
            txt = open(os.path.join(ROOT, n), encoding="utf-8").read()
            for ref in re.findall(r"\b([\w-]+\.bat)\b", txt):
                self.assertTrue(os.path.exists(os.path.join(ROOT, ref)), ref)

    def test_spec_has_icon(self):
        spec = open(os.path.join(ROOT, "GTForceBridge.spec"), encoding="utf-8").read()
        self.assertIn("icon='GTFB.ico'", spec); self.assertNotIn("D:/", spec)

    def test_tray_icon_uses_file(self):
        try:
            from gtforce_bridge.gui import tray
        except Exception as e:          # sem tkinter neste ambiente
            self.skipTest(str(e))
        img = tray.make_icon("running", 64)
        self.assertEqual(img.size, (64, 64))
        self.assertIsNotNone(tray._file_icon(64))


if __name__ == "__main__":
    unittest.main()
