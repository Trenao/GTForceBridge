"""Recebe pacotes FFB do vJoy (thread do driver), decodifica e enfileira eventos."""
from __future__ import annotations

import ctypes
import queue
from ctypes import POINTER, byref, c_int, c_int32, c_ubyte, c_void_p

from .vjoy_protocol import s16, cartesian_x, FFB_EFF_COND, FFB_EFF_CONSTANT, FFB_EFF_OP, FFB_EFF_PERIOD, FFB_EFF_RAMP, direction_to_byte, report_class, uses_new_layout, PT_BLKFRREP, PT_CONDREP, PT_CONSTREP, PT_CTRLREP, PT_EFFREP, PT_EFOPREP, PT_GAINREP, PT_PRIDREP, PT_RAMPREP


class FfbReceiver:
    def __init__(self, vjoy, verbose=False):
        self.v = vjoy
        self.q = queue.Queue()
        self.verbose = verbose

    def callback(self, data, _user):
        try:
            self._decode(data)
        except Exception as e:
            if self.verbose:
                print("[ffb] erro no decode:", e)

    def _decode(self, pkt):
        d = self.v.dll
        t = c_int(0)
        if d.Ffb_h_Type(c_void_p(pkt), byref(t)) != 0:
            return
        t = t.value
        if t == PT_EFFREP:
            r = report_class(d)()
            if d.Ffb_h_Eff_Report(c_void_p(pkt), byref(r)) == 0:
                new = uses_new_layout(d)
                self.q.put(("report", r.EffectBlockIndex, r.EffectType, r.Gain,
                            r.Polar, direction_to_byte(r.Direction, new),
                            r.Duration, getattr(r, "StartDelay", 0),
                            cartesian_x(r.Direction, new)))
        elif t == PT_CONSTREP:
            c = FFB_EFF_CONSTANT()
            if d.Ffb_h_Eff_Constant(c_void_p(pkt), byref(c)) == 0:
                self.q.put(("constant", c.EffectBlockIndex, s16(c.Magnitude)))
        elif t == PT_RAMPREP:
            if hasattr(d, "Ffb_h_Eff_Ramp"):
                r = FFB_EFF_RAMP()
                if d.Ffb_h_Eff_Ramp(c_void_p(pkt), byref(r)) == 0:
                    self.q.put(("ramp", r.EffectBlockIndex, s16(r.Start), s16(r.End)))
            else:
                buf = ctypes.string_at(pkt, 9)
                ebi = buf[0]
                arr = ctypes.cast(ctypes.create_string_buffer(buf[1:9]), POINTER(c_int32))
                self.q.put(("ramp", ebi, s16(arr[0]), s16(arr[1])))
        elif t == PT_CONDREP:
            c = FFB_EFF_COND()
            if d.Ffb_h_Eff_Cond(c_void_p(pkt), byref(c)) == 0:
                self.q.put(("cond", c.EffectBlockIndex, c.isY, s16(c.CenterPointOffset),
                            s16(c.PosCoeff), s16(c.NegCoeff), c.PosSatur, c.NegSatur, c.DeadBand))
        elif t == PT_PRIDREP:
            p = FFB_EFF_PERIOD()
            if d.Ffb_h_Eff_Period(c_void_p(pkt), byref(p)) == 0:
                self.q.put(("period", p.EffectBlockIndex, p.Magnitude, s16(p.Offset), p.Phase, p.Period))
        elif t == PT_EFOPREP:
            o = FFB_EFF_OP()
            if d.Ffb_h_EffOp(c_void_p(pkt), byref(o)) == 0:
                self.q.put(("op", o.EffectBlockIndex, o.EffectOp, o.LoopCount))
        elif t == PT_BLKFRREP:
            i = c_int(0)
            if d.Ffb_h_EBI(c_void_p(pkt), byref(i)) == 0:
                self.q.put(("free", i.value))
        elif t == PT_CTRLREP:
            c = c_int(0)
            if d.Ffb_h_DevCtrl(c_void_p(pkt), byref(c)) == 0:
                self.q.put(("ctrl", c.value))
        elif t == PT_GAINREP:
            g = c_ubyte(0)
            if d.Ffb_h_DevGain(c_void_p(pkt), byref(g)) == 0:
                self.q.put(("devgain", g.value))
        elif self.verbose:
            print(f"[ffb] pacote tipo 0x{t:02X} ignorado")
