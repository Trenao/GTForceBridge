"""O vJoy entrega Magnitude/Start/End/Offset int16 SEM sinal (negativo = 65536 + x). O receiver tem de restaurar o sinal."""
import ctypes
import unittest

from gtforce_bridge.ffb_receiver import FfbReceiver
from gtforce_bridge.vjoy_protocol import PT_CONSTREP, PT_RAMPREP, PT_PRIDREP, FFB_EFF_CONSTANT, s16
from tests.test_ffb_translator import Rig
from gtforce_bridge.vjoy_protocol import EFF_START, ET_CONST


class FakeDll:
    def __init__(self, ptype, fill):
        self.ptype, self.fill = ptype, fill

    def Ffb_h_Type(self, pkt, ref):
        ref._obj.value = self.ptype
        return 0

    def Ffb_h_Eff_Constant(self, pkt, ref):
        self.fill(ref._obj); return 0


class V:
    def __init__(self, dll): self.dll = dll


def decode(raw):
    d = FakeDll(PT_CONSTREP, lambda c: (setattr(c, "EffectBlockIndex", 1), setattr(c, "Magnitude", raw)))
    r = FfbReceiver(V(d)); r._decode(1); return r.q.get_nowait()


class Sign(unittest.TestCase):
    def test_s16(self):
        for raw, want in ((0, 0), (8000, 8000), (10000, 10000), (65429, -107), (55536, -10000), (65535, -1), (-5, -5)):
            self.assertEqual(s16(raw), want)

    def test_receiver_restores_negative_constant_from_real_capture(self):
        self.assertEqual(decode(65429), ("constant", 1, -107))      # valores reais do log do Assetto Corsa Rally
        self.assertEqual(decode(64853), ("constant", 1, -683))      # Wreckfest 2
        self.assertEqual(decode(7726), ("constant", 1, 7726))

    def test_both_sides_reach_the_motor_after_decode(self):
        r = Rig()
        r.put("report", 1, ET_CONST, 255, 0, 0, 0)
        r.put("op", 1, EFF_START, 1)
        out = []
        for raw in (8000, 7726, 65429, 65277, 55536, 3000):
            r.put(*decode(raw)); r.run(0.03); out.append(r.levels()[-1])
        self.assertEqual([x > 0 for x in out], [True, True, False, False, False, True])
        self.assertLess(out[4], -30000)                              # 55536 = -10000 => fundo de escala negativo


if __name__ == "__main__":
    unittest.main()
