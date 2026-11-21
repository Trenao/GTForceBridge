"""Garante que todos os módulos importam (sem Windows, sem volante, sem tkinter)."""
import importlib
import pkgutil
import unittest

import gtforce_bridge


class ImportAll(unittest.TestCase):
    def test_import_every_module(self):
        names = [m.name for m in pkgutil.walk_packages(gtforce_bridge.__path__, "gtforce_bridge.")]
        self.assertGreater(len(names), 15)
        for n in names:
            with self.subTest(module=n):
                importlib.import_module(n)


if __name__ == "__main__":
    unittest.main()
