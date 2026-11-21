"""Roda o cmd_run de verdade com volante/vJoy/SDL falsos: entrada, reconexão e --ffb-dump."""
import io
import os
import queue
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock

from gtforce_bridge import bridge, sinks
from gtforce_bridge.config import DEFAULT_CONFIG, deep_merge


class FakeSdl:
    def SDL_JoystickUpdate(self): pass
    def SDL_Quit(self): pass


class FakeWheel:
    instances = []
    plugged = True            # o teste liga/desliga

    def __init__(self, sdl2, match, pids=None):
        if not FakeWheel.plugged:
            raise RuntimeError("não encontrado")
        self.name, self.vendor, self.product = "GT Force Falso", 0x046D, 0xC293
        self.n_axes, self.n_buttons, self.haptic = 3, 4, None
        self.joy = object()
        FakeWheel.instances.append(self)

    def update(self): pass
    def axis(self, i): return 0.5 if i == 0 else 0.0
    def button(self, i): return False
    def can(self, f): return False
    def attached(self): return bool(self.joy) and FakeWheel.plugged
    def close(self): self.joy = None


class FakeVJoy:
    last = None

    def __init__(self, dll, dev):
        self.axes, self.cb, self.dll = [], None, object()
        FakeVJoy.last = self

    broken = False
    reacquired = 0

    def set_axis(self, name, v):
        if FakeVJoy.broken:
            raise RuntimeError("SetAxis falhou")
        self.axes.append((name, v))

    def reacquire(self):
        FakeVJoy.reacquired += 1
        FakeVJoy.broken = False
        return True

    def set_button(self, n, p): pass
    def register_ffb(self, cb): self.cb = cb
    def close(self): pass


class FakeReceiver:
    last = None

    def __init__(self, vjoy, verbose=False):
        self.q = queue.Queue()
        FakeReceiver.last = self

    def callback(self, *a): pass


class Loop(unittest.TestCase):
    def run_loop(self, scenario, cfg_over=None, fake_keys=None, **kw):
        FakeWheel.instances, FakeWheel.plugged = [], True
        with tempfile.TemporaryDirectory() as d:
            stop = os.path.join(d, "bridge.stop")
            patches = [
                mock.patch.object(bridge, "init_sdl", lambda: FakeSdl()),
                mock.patch.object(bridge, "Wheel", FakeWheel),
                mock.patch.object(bridge, "VJoy", FakeVJoy),
                mock.patch.object(bridge, "FfbReceiver", FakeReceiver),
                mock.patch.object(bridge, "STOP_PATH", stop),
                mock.patch.object(bridge, "TELEMETRY_PATH", os.path.join(d, "t.json")),
                mock.patch.object(bridge, "CONFIG_PATH", os.path.join(d, "config.json")),
            ]
            for p in patches:
                p.start()
            buf = io.StringIO()
            cfg = deep_merge(DEFAULT_CONFIG, cfg_over or {})
            if fake_keys is not None:      # troca o injetor do Windows por um falso
                def build(c, vj, log=print):
                    return [sinks.VJoySink(vj, c, log=log),
                            sinks.KeyboardSink(c, log=log, injector_factory=lambda: fake_keys)]
                bp = mock.patch.object(bridge, "build_sinks", build)
                bp.start()
                patches.append(bp)
            try:
                def worker():
                    with redirect_stdout(buf):
                        bridge.cmd_run(cfg, False, **kw)
                th = threading.Thread(target=worker)
                th.start()
                time.sleep(0.3)
                try:
                    scenario()
                finally:                      # mesmo se um assert do cenário falhar, o loop encerra
                    with open(stop, "w") as f:
                        f.write("stop")
                    th.join(5)                # ANTES de remover os patches (o loop ainda os usa)
                self.assertFalse(th.is_alive(), "o loop não encerrou")
            finally:
                for p in patches:
                    p.stop()
        return buf.getvalue()

    def test_input_flows_to_vjoy(self):
        out = self.run_loop(lambda: time.sleep(0.2), ffb=False)
        self.assertIn("só entrada", out)
        self.assertIn("Modelo: WingMan Formula Force GP", out)
        steer = [v for n, v in FakeVJoy.last.axes if n == "X"]
        self.assertGreater(len(steer), 5)
        self.assertGreater(max(steer), 20000)          # 0.5 -> acima do centro

    def test_vjoy_failure_mid_run_does_not_kill_the_loop(self):
        FakeVJoy.broken, FakeVJoy.reacquired = False, 0

        def scenario():
            FakeVJoy.broken = True               # o vJoy "some" com o loop rodando
            time.sleep(1.4)
        out = self.run_loop(scenario, ffb=False)  # run_loop falha se o loop morrer/não encerrar
        self.assertIn("[vjoy] falha", out)
        self.assertIn("readquirido", out)
        self.assertGreaterEqual(FakeVJoy.reacquired, 1)
        self.assertNotIn("Traceback", out)

    def test_keyboard_output_presses_and_never_leaves_a_key_stuck(self):
        class Keys:
            def __init__(self): self.events, self.down = [], set()
            def key(self, code, down):
                self.events.append((code, down))
                (self.down.add if down else self.down.discard)(code)
        keys = Keys()
        RIGHT = (0x4D, True)

        def scenario():
            time.sleep(0.3)
            self.assertIn(RIGHT, keys.down)           # direção a 0.5 > 0.35: tecla → apertada
            FakeWheel.plugged = False                  # volante some com a tecla segurada
            time.sleep(0.4)
            self.assertNotIn(RIGHT, keys.down)         # solta ao perder o volante
            FakeWheel.plugged = True
            time.sleep(1.6)                            # reconecta: volta a apertar
            self.assertIn(RIGHT, keys.down)            # (e o stop do teste ocorre com ela segurada)
        self.run_loop(scenario, ffb=False, fake_keys=keys,
                      cfg_over={"outputs": {"keyboard": {"enabled": True}}})
        self.assertEqual(keys.down, set())             # ao encerrar a ponte, nada ficou preso

    def test_disconnect_neutral_and_reconnect(self):
        def scenario():
            FakeWheel.plugged = False
            time.sleep(0.4)
            n_before = len(FakeVJoy.last.axes)
            time.sleep(0.3)
            self.assertEqual(len(FakeVJoy.last.axes), n_before)     # nada novo enquanto ausente
            FakeWheel.plugged = True
            time.sleep(1.6)                                           # retry de 1 s
        out = self.run_loop(scenario, ffb=False)
        self.assertIn("desconectado", out)
        self.assertIn("reconectado", out)
        self.assertEqual(len(FakeWheel.instances), 2)

    def test_dump_mode_prints_events_without_translator(self):
        def scenario():
            FakeReceiver.last.q.put(("report", 1, 8, 255, 0, 0, 0))
            FakeReceiver.last.q.put(("cond", 1, 0, 0, 3000, 3000, 10000, 10000, 0))
            time.sleep(0.3)
        out = self.run_loop(scenario, dump=True)
        self.assertIn("[ffb-dump] report", out)
        self.assertIn("SPRING", out)
        self.assertIn("[ffb-dump] total: 2 pacotes", out)


if __name__ == "__main__":
    unittest.main()
