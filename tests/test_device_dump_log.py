import logging
import os
import queue
import sys
import tempfile
import unittest

from gtforce_bridge import device_table, logsetup
from gtforce_bridge.ffb_dump import DumpStats, format_event


class DeviceTable(unittest.TestCase):
    def test_lookup(self):
        self.assertEqual(device_table.lookup(0x046D, 0xC293).name, "WingMan Formula Force GP")
        self.assertIsNone(device_table.lookup(0x1234, 0xC293))
        self.assertIsNone(device_table.lookup(0x046D, 0x9999))

    def test_describe_warns_when_ffb_expected_but_no_haptic(self):
        self.assertIn("aviso", device_table.describe(0x046D, 0xC293, False))
        self.assertNotIn("aviso", device_table.describe(0x046D, 0xC293, True))
        self.assertIn("fora da tabela", device_table.describe(0x046D, 0x9999, True))


class Dump(unittest.TestCase):
    def test_format_and_stats(self):
        q = queue.Queue()
        q.put(("report", 1, 1, 255, 0, 0, 0))
        q.put(("constant", 1, 5000))
        t = [0.0]
        st = DumpStats(clock=lambda: t[0], interval=5, warn_after=10)
        lines = st.consume(q)
        self.assertEqual(len(lines), 2)
        self.assertIn("CONST", lines[0])
        self.assertIn("5000", lines[1])
        t[0] = 6
        self.assertTrue(any("resumo" in x for x in st.periodic()))
        self.assertIn("2 pacotes", st.summary())

    def test_warns_when_nothing_arrives(self):
        t = [0.0]
        st = DumpStats(clock=lambda: t[0], interval=100, warn_after=10)
        self.assertEqual(st.periodic(), [])
        t[0] = 11
        out = st.periodic()
        self.assertEqual(len(out), 1)
        self.assertIn("nenhum pacote", out[0])
        self.assertEqual(st.periodic(), [])           # avisa só uma vez
        self.assertEqual(format_event(("op", 1, 1, 0)), "op      1 1 0")


class LogTee(unittest.TestCase):
    def test_tee_writes_file_and_keeps_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x", "bridge.log")
            old_out, old_err = sys.stdout, sys.stderr
            logsetup._installed = False
            try:
                got = logsetup.setup_logging({"enabled": True, "file": path}, "teste")
                self.assertEqual(got, path)
                print("linha de teste")
                sys.stdout.flush()
            finally:
                sys.stdout, sys.stderr = old_out, old_err
                logsetup._installed = False
                lg = logging.getLogger("gtforce_bridge.file")
                for h in list(lg.handlers):
                    h.close()
                    lg.removeHandler(h)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("linha de teste", text)
            self.assertIn("sessão 'teste' iniciada", text)

    def test_disabled_returns_none(self):
        logsetup._installed = False
        self.assertIsNone(logsetup.setup_logging({"enabled": False}))


if __name__ == "__main__":
    unittest.main()
