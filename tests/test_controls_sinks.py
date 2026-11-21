"""controls (leitura→estado) e sinks (estado→saída), incluindo falha/recuperação do vJoy."""
import unittest

from gtforce_bridge.config import DEFAULT_CONFIG, deep_merge
from gtforce_bridge.controls import ControlState, compute_controls
from gtforce_bridge.sinks import VJoySink


class FakeWheel:
    n_buttons = 3

    def __init__(self, axes, buttons=(False, True, False)):
        self.axes, self.b = axes, buttons

    def axis(self, i): return self.axes.get(i, 0.0)
    def button(self, i): return self.b[i]


def cfg(**over):
    return deep_merge(DEFAULT_CONFIG, over)


class Controls(unittest.TestCase):
    def test_steering_throttle_brake(self):
        w = FakeWheel({0: 0.5, 1: 1.0, 2: -1.0})
        st = compute_controls(w, cfg(steering={"expo": 0.0, "deadzone": 0.0}))
        self.assertAlmostEqual(st.steering, 0.5, places=3)
        self.assertAlmostEqual(st.throttle, 1.0, places=2)    # eixo +1 -> pedal cheio
        self.assertAlmostEqual(st.brake, 0.0, places=2)       # eixo -1 -> pedal solto
        self.assertEqual(st.buttons, (False, True, False))

    def test_combined_pedals_split_throttle_and_brake(self):
        c = cfg(pedals_mode="combined", throttle={"deadzone": 0.0}, brake={"deadzone": 0.0})
        up = compute_controls(FakeWheel({1: 0.6}), c)
        dn = compute_controls(FakeWheel({1: -0.4}), c)
        self.assertGreater(up.throttle, 0.5); self.assertEqual(up.brake, 0.0)
        self.assertGreater(dn.brake, 0.3); self.assertEqual(dn.throttle, 0.0)

    def test_buttons_can_be_disabled(self):
        st = compute_controls(FakeWheel({}), cfg(buttons_map_all=False))
        self.assertEqual(st.buttons, ())


class FakeVJoy:
    def __init__(self):
        self.axes, self.btn = {}, {}
        self.broken, self.reacquired, self.reacquire_ok = False, 0, True

    def set_axis(self, name, v):
        if self.broken:
            raise RuntimeError("SetAxis falhou")
        self.axes[name] = v

    def set_button(self, n, p):
        if self.broken:
            raise RuntimeError("SetBtn falhou")
        self.btn[n] = p

    def reacquire(self):
        self.reacquired += 1
        if self.reacquire_ok:
            self.broken = False
        return self.reacquire_ok


class Sink(unittest.TestCase):
    def setUp(self):
        self.t = 1000.0
        self.logs = []
        self.vj = FakeVJoy()
        self.sink = VJoySink(self.vj, cfg(), log=self.logs.append, clock=lambda: self.t)

    def test_maps_axes_and_buttons(self):
        self.sink.send(ControlState(0.0, 1.0, 0.0, (True, False)))
        self.assertEqual(self.vj.axes["X"], 16384)            # centro
        self.assertEqual(self.vj.axes["RZ"], 32768)           # acelerador cheio
        self.assertEqual(self.vj.axes["SL0"], 1)              # freio solto (mínimo do vJoy)
        self.assertEqual(self.vj.btn, {1: True, 2: False})

    def test_failure_does_not_raise_and_recovers_via_reacquire(self):
        self.vj.broken = True
        self.sink.send(ControlState(0.1, 0, 0))               # não pode levantar exceção
        self.assertEqual(self.vj.reacquired, 1)
        self.assertFalse(self.vj.broken)                      # readquiriu
        self.sink.send(ControlState(0.1, 0, 0))
        self.assertIn("recuperado", " ".join(self.logs))

    def test_retry_and_log_are_rate_limited(self):
        self.vj.broken, self.vj.reacquire_ok = True, False
        for _ in range(500):                                  # 500 ticks no mesmo instante
            self.sink.send(ControlState())
        self.assertEqual(self.vj.reacquired, 1)
        self.assertEqual(len([l for l in self.logs if "falha" in l]), 1)
        self.t += 1.1
        self.sink.send(ControlState())
        self.assertEqual(self.vj.reacquired, 2)               # tenta de novo após ~1 s
        self.t += 5.1
        self.sink.send(ControlState())
        self.assertEqual(len([l for l in self.logs if "falha" in l]), 2)

    def test_neutral_never_raises(self):
        self.vj.broken = True
        self.sink.neutral()


if __name__ == "__main__":
    unittest.main()
