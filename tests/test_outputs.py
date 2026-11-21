"""mapping.py + saídas de teclado e Xbox (com injetor/controle falsos)."""
import ctypes
import sys
import types
import unittest

from gtforce_bridge import sinks
from gtforce_bridge.config import DEFAULT_CONFIG, deep_merge, unknown_keys
from gtforce_bridge.controls import ControlState
from gtforce_bridge.mapping import Hysteresis, resolve_key, source_value


def cfg(**outputs):
    return deep_merge(DEFAULT_CONFIG, {"outputs": outputs})


class Mapping(unittest.TestCase):
    def test_sources(self):
        st = ControlState(-0.4, 0.7, 0.1, (True, False))
        self.assertAlmostEqual(source_value(st, "steering-"), 0.4)
        self.assertEqual(source_value(st, "steering+"), 0.0)
        self.assertEqual(source_value(st, "THROTTLE"), 0.7)
        self.assertEqual(source_value(st, "button:1"), 1.0)
        self.assertEqual(source_value(st, "button:2"), 0.0)
        self.assertEqual(source_value(st, "button:9"), 0.0)       # além dos botões existentes
        for bad in ("button:0", "button:x", "volante", None, 3):
            self.assertIsNone(source_value(st, bad))

    def test_hysteresis(self):
        h = Hysteresis(on=0.5, off=0.3)
        self.assertEqual([h.update(v) for v in (0.4, 0.5, 0.4, 0.31, 0.29, 0.4)],
                         [False, True, True, True, False, False])

    def test_keys(self):
        self.assertEqual(resolve_key("A"), (0x1E, False))
        self.assertEqual(resolve_key(" Left "), (0x4B, True))      # setas são estendidas
        self.assertEqual(resolve_key("f12"), (0x58, False))
        self.assertEqual(resolve_key("f10"), (0x44, False))
        self.assertIsNone(resolve_key("banana"))
        self.assertIsNone(resolve_key(None))


class FakeInjector:
    def __init__(self):
        self.events = []

    def key(self, code, down):
        self.events.append((code, down))


class Keyboard(unittest.TestCase):
    def make(self, **kb):
        self.inj = FakeInjector()
        self.logs = []
        c = cfg(keyboard={"enabled": True, **kb})
        self.sink = sinks.KeyboardSink(c, log=self.logs.append, injector_factory=lambda: self.inj)
        return c

    def test_disabled_by_default_does_not_even_create_injector(self):
        def boom():
            raise AssertionError("não deveria criar o injetor")
        s = sinks.KeyboardSink(deep_merge(DEFAULT_CONFIG, {}), injector_factory=boom)
        s.send(ControlState(1.0, 1.0, 0.0, (True,)))

    def test_press_and_release_with_hysteresis(self):
        self.make()
        LEFT, RIGHT, UP = (0x4B, True), (0x4D, True), (0x48, True)
        self.sink.send(ControlState(0.2, 0, 0))                       # abaixo do limiar
        self.assertEqual(self.inj.events, [])
        self.sink.send(ControlState(0.6, 0.5, 0))                     # direita + acelerador
        self.assertEqual(sorted(self.inj.events), sorted([(RIGHT, True), (UP, True)]))
        self.inj.events.clear()
        self.sink.send(ControlState(0.30, 0.5, 0))                    # entre off(0.25) e on(0.35): segura
        self.assertEqual(self.inj.events, [])
        self.sink.send(ControlState(0.10, 0.5, 0))                    # abaixo de off: solta só a direita
        self.assertEqual(self.inj.events, [(RIGHT, False)])
        self.assertNotIn((LEFT, True), self.inj.events)

    def test_no_repeat_events_while_held(self):
        self.make()
        for _ in range(50):
            self.sink.send(ControlState(0.9, 0, 0))
        self.assertEqual(len(self.inj.events), 1)

    def test_two_sources_same_key_are_ored(self):
        self.make(bindings=[{"source": "throttle", "key": "w"}, {"source": "button:1", "key": "w"}])
        W = (0x11, False)
        self.sink.send(ControlState(0, 0.9, 0, (True,)))
        self.sink.send(ControlState(0, 0.0, 0, (True,)))              # acelerador soltou, botão segura
        self.assertEqual(self.inj.events, [(W, True)])
        self.sink.send(ControlState(0, 0.0, 0, (False,)))
        self.assertEqual(self.inj.events[-1], (W, False))

    def test_neutral_close_and_disable_release_every_key(self):
        c = self.make()
        self.sink.send(ControlState(0.9, 0.9, 0.9, (True,)))
        held = {e[0] for e in self.inj.events if e[1]}
        self.assertEqual(len(held), 4)             # direita, acelerador, freio, botão 1
        self.sink.neutral()                                           # volante sumiu
        self.assertEqual({e[0] for e in self.inj.events if not e[1]}, held)
        self.inj.events.clear()
        self.sink.send(ControlState(0.9, 0.9, 0.9, (True,)))
        c["outputs"]["keyboard"]["enabled"] = False                   # desligou com o loop rodando
        self.sink.send(ControlState(0.9, 0.9, 0.9, (True,)))
        self.assertEqual(len([e for e in self.inj.events if not e[1]]), 4)
        self.inj.events.clear()
        self.sink.close()
        self.assertEqual(self.inj.events, [])                         # nada preso para soltar

    def test_binding_removed_while_held_releases_key(self):
        c = self.make(bindings=[{"source": "throttle", "key": "w"}])
        self.sink.send(ControlState(0, 0.9, 0))
        c["outputs"]["keyboard"]["bindings"] = []
        self.sink.send(ControlState(0, 0.9, 0))
        self.assertEqual(self.inj.events[-1], ((0x11, False), False))

    def test_bad_bindings_warn_once_and_do_not_crash(self):
        self.make(bindings=[{"source": "throttle", "key": "banana"}, {"source": "nada", "key": "a"},
                            {"source": "throttle", "key": "a"}])
        for _ in range(5):
            self.sink.send(ControlState(0, 0.9, 0))
        self.assertEqual(len([l for l in self.logs if "desconhecida" in l]), 2)
        self.assertEqual(self.inj.events, [((0x1E, False), True)])

    def test_unavailable_injector_is_reported_once(self):
        logs = []
        def fail():
            raise OSError("só Windows")
        s = sinks.KeyboardSink(cfg(keyboard={"enabled": True}), log=logs.append, injector_factory=fail)
        for _ in range(10):
            s.send(ControlState(0.9, 0, 0))
        self.assertEqual(len(logs), 1)

    def test_sendinput_structs(self):
        want = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28     # tamanho que o Windows exige
        self.assertEqual(ctypes.sizeof(sinks.INPUT), want)
        down = sinks.make_key_input((0x4B, True), True)
        up = sinks.make_key_input((0x1E, False), False)
        self.assertEqual((down.type, down.ki.wVk, down.ki.wScan, down.ki.dwFlags), (1, 0, 0x4B, 0x8 | 0x1))
        self.assertEqual(up.ki.dwFlags, 0x8 | 0x2)

    @unittest.skipIf(sys.platform == "win32", "só fora do Windows")
    def test_real_injector_refuses_outside_windows(self):
        with self.assertRaises(OSError):
            sinks.WinKeyInjector()


class FakePad:
    def __init__(self):
        self.calls, self.stick_v, self.trig, self.down, self.updates, self.resets = [], None, None, set(), 0, 0

    def stick(self, x, y): self.stick_v = (x, y)
    def triggers(self, lt, rt): self.trig = (lt, rt)

    def button(self, name, pressed):
        (self.down.add if pressed else self.down.discard)(name)

    def update(self): self.updates += 1
    def reset(self): self.resets += 1


class Xbox(unittest.TestCase):
    def make(self, **xb):
        self.pad, self.logs = FakePad(), []
        c = cfg(xbox={"enabled": True, **xb})
        self.sink = sinks.XboxSink(c, log=self.logs.append, pad_factory=lambda: self.pad)
        return c

    def test_maps_stick_triggers_and_buttons(self):
        self.make()
        self.sink.send(ControlState(-0.5, 0.8, 0.25, (True, False, True)))
        self.assertEqual(self.pad.stick_v, (-0.5, 0.0))
        self.assertEqual(self.pad.trig, (0.25, 0.8))                   # (LT=freio, RT=acelerador)
        self.assertEqual(self.pad.down, {"A", "X"})

    def test_only_updates_driver_on_change(self):
        self.make()
        st = ControlState(0.1, 0.0, 0.0, (False,))
        for _ in range(100):
            self.sink.send(st)
        self.assertEqual(self.pad.updates, 1)
        self.sink.send(ControlState(0.2, 0.0, 0.0, (False,)))
        self.assertEqual(self.pad.updates, 2)

    def test_empty_mapping_and_unknown_button(self):
        self.make(buttons={"1": "", "2": "ZZZ", "3": "start"})
        self.sink.send(ControlState(0, 0, 0, (True, True, True)))
        self.assertEqual(self.pad.down, {"START"})                     # "" ignorado, nome em minúsculas aceito
        self.assertEqual(len([l for l in self.logs if "desconhecido" in l]), 1)

    def test_disabled_never_creates_pad_and_neutral_resets(self):
        def boom():
            raise AssertionError("não deveria criar")
        sinks.XboxSink(deep_merge(DEFAULT_CONFIG, {}), pad_factory=boom).send(ControlState(1, 1, 1, (True,)))
        c = self.make()
        self.sink.send(ControlState(1, 1, 1, (True,)))
        self.sink.neutral()
        self.assertEqual(self.pad.resets, 1)
        c["outputs"]["xbox"]["enabled"] = False
        self.sink.send(ControlState(1, 1, 1, (True,)))                 # nada novo
        self.assertEqual(self.pad.updates, 1)

    def test_missing_driver_is_reported_once_and_does_not_crash(self):
        logs = []
        def fail():
            raise OSError("ViGEmBus ausente")
        s = sinks.XboxSink(cfg(xbox={"enabled": True}), log=logs.append, pad_factory=fail)
        for _ in range(10):
            s.send(ControlState(1, 1, 1, (True,)))
        self.assertEqual(len(logs), 1)
        self.assertIn("vgamepad", logs[0])


class VGamepadAdapter(unittest.TestCase):
    """O adaptador chama a API do pacote `vgamepad` (nomes conferidos no código-fonte da v0.2.0)."""

    def setUp(self):
        calls = self.calls = []

        class Btn:                                   # IntFlag no pacote real; aqui só identifica
            pass
        names = ("DPAD_UP DPAD_DOWN DPAD_LEFT DPAD_RIGHT START BACK LEFT_THUMB RIGHT_THUMB "
                 "LEFT_SHOULDER RIGHT_SHOULDER GUIDE A B X Y").split()
        XUSB = types.SimpleNamespace(**{f"XUSB_GAMEPAD_{n}": f"btn:{n}" for n in names})

        class Pad:
            def left_joystick_float(self, x_value_float, y_value_float): calls.append(("stick", x_value_float, y_value_float))
            def left_trigger_float(self, value_float): calls.append(("lt", value_float))
            def right_trigger_float(self, value_float): calls.append(("rt", value_float))
            def press_button(self, button): calls.append(("press", button))
            def release_button(self, button): calls.append(("release", button))
            def update(self): calls.append(("update",))
            def reset(self): calls.append(("reset",))

        mod = types.ModuleType("vgamepad")
        mod.XUSB_BUTTON, mod.VX360Gamepad = XUSB, Pad
        self._old = sys.modules.get("vgamepad")
        sys.modules["vgamepad"] = mod

    def tearDown(self):
        if self._old is None:
            sys.modules.pop("vgamepad", None)
        else:
            sys.modules["vgamepad"] = self._old

    def test_calls(self):
        p = sinks.VGamepadPad()
        p.stick(0.5, 0.0); p.triggers(0.1, 0.9)
        p.button("A", True); p.button("LB", False); p.button("UP", True)
        p.update(); p.reset()
        self.assertEqual(self.calls, [
            ("stick", 0.5, 0.0), ("lt", 0.1), ("rt", 0.9),
            ("press", "btn:A"), ("release", "btn:LEFT_SHOULDER"), ("press", "btn:DPAD_UP"),
            ("update",), ("reset",), ("update",)])

    def test_every_listed_button_name_is_mapped(self):
        p = sinks.VGamepadPad()
        for name in sinks.XBOX_BUTTON_NAMES:
            p.button(name, True)


class Wiring(unittest.TestCase):
    def test_build_sinks_and_config_has_no_unknown_keys(self):
        self.assertEqual([s.name for s in sinks.build_sinks(DEFAULT_CONFIG, object())],
                         ["vJoy", "teclado", "xbox"])
        self.assertEqual(unknown_keys(DEFAULT_CONFIG), [])
        custom = {"outputs": {"xbox": {"buttons": {"9": "GUIDE"}}, "keyboard": {"enabled": True}}}
        self.assertEqual(unknown_keys(custom), [])

    def test_vjoy_output_can_be_turned_off(self):
        class VJ:
            def __init__(self): self.n = 0
            def set_axis(self, *a): self.n += 1
            def set_button(self, *a): self.n += 1
        vj = VJ()
        c = cfg(vjoy={"enabled": False})
        sinks.VJoySink(vj, c).send(ControlState(1, 1, 1, (True,)))
        self.assertEqual(vj.n, 0)

    def test_user_can_remove_a_default_xbox_mapping_with_empty_string(self):
        c = deep_merge(DEFAULT_CONFIG, {"outputs": {"xbox": {"buttons": {"1": ""}}}})
        self.assertEqual(c["outputs"]["xbox"]["buttons"]["1"], "")
        self.assertEqual(c["outputs"]["xbox"]["buttons"]["2"], "B")


if __name__ == "__main__":
    unittest.main()
