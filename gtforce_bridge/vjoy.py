"""Acesso ao vJoy via vJoyInterface.dll (ctypes): adquirir device, enviar eixos/botões e registrar callback de FFB."""
from __future__ import annotations

import ctypes
import os
from ctypes import c_int, c_int32, c_ubyte, c_uint, c_void_p

from .constants import AXIS_USAGE
from .vjoy_protocol import FFB_CB


class VJoy:
    def __init__(self, dll_path, dev_id):
        if not os.path.exists(dll_path):
            raise RuntimeError(f"vJoyInterface.dll não encontrada em: {dll_path}\n"
                               "Ajuste 'vjoy_dll' no config.json.")
        self.dll = ctypes.WinDLL(dll_path) if hasattr(ctypes, "WinDLL") else ctypes.CDLL(dll_path)
        self.id = dev_id
        d = self.dll
        d.vJoyEnabled.restype = c_int
        d.GetVJDStatus.argtypes = [c_uint]
        d.GetVJDStatus.restype = c_int
        d.AcquireVJD.argtypes = [c_uint]
        d.AcquireVJD.restype = c_int
        d.RelinquishVJD.argtypes = [c_uint]
        d.ResetVJD.argtypes = [c_uint]
        d.SetAxis.argtypes = [c_int32, c_uint, c_uint]
        d.SetAxis.restype = c_int
        d.SetBtn.argtypes = [c_int, c_uint, c_ubyte]
        d.SetBtn.restype = c_int
        if not d.vJoyEnabled():
            raise RuntimeError("vJoy não está instalado/ativo.")
        status = d.GetVJDStatus(dev_id)
        if status not in (0, 1):
            raise RuntimeError(f"vJoy device {dev_id} indisponível (status={status}).")
        if not d.AcquireVJD(dev_id):
            raise RuntimeError(f"Falha ao adquirir o vJoy device {dev_id}.")
        d.ResetVJD(dev_id)
        self._last_axis = {}
        self._last_btn = {}
        self._cb = None
        self._py_cb = None          # callback de FFB do Python (para re-registrar após reacquire)

    def set_axis(self, name, value):
        key = str(name).strip().upper().replace(" ", "")
        try:
            usage = AXIS_USAGE[key]
        except KeyError:
            valid = "X, Y, Z, RX, RY, RZ, SL0/Slider, SL1"
            raise ValueError(f"Eixo vJoy '{name}' inválido. Use: {valid}.") from None
        if self._last_axis.get(usage) != value:
            if not self.dll.SetAxis(value, self.id, usage):
                raise RuntimeError(f"SetAxis falhou: eixo {key}, valor {value}.")
            self._last_axis[usage] = value

    def set_button(self, n, pressed):
        if self._last_btn.get(n) != pressed:
            if not self.dll.SetBtn(1 if pressed else 0, self.id, n):
                raise RuntimeError(f"SetBtn falhou: botão {n}.")
            self._last_btn[n] = pressed

    def register_ffb(self, py_callback):
        d = self.dll
        self._py_cb = py_callback
        self._cb = FFB_CB(py_callback)
        d.FfbRegisterGenCB.argtypes = [FFB_CB, c_void_p]
        d.FfbRegisterGenCB.restype = None
        d.FfbRegisterGenCB(self._cb, None)
        try:
            d.FfbStart.argtypes = [c_uint]
            d.FfbStart(self.id)
        except AttributeError:
            pass
        for fn in ("Ffb_h_Type", "Ffb_h_EffNew", "Ffb_h_Eff_Report", "Ffb_h_Eff_Constant",
                   "Ffb_h_Eff_Ramp", "Ffb_h_Eff_Cond", "Ffb_h_Eff_Period", "Ffb_h_EffOp",
                   "Ffb_h_DevCtrl", "Ffb_h_DevGain", "Ffb_h_EBI"):
            if not hasattr(d, fn):
                if fn == "Ffb_h_Eff_Ramp":
                    continue
                raise RuntimeError(f"{fn} ausente na DLL: o vJoy instalado não expõe FFB.")
            getattr(d, fn).restype = c_uint

    def reacquire(self):
        """Libera e readquire o device (ex.: outro programa o tomou, ou o driver reiniciou).
        Devolve True se voltou a funcionar. Re-registra o callback de FFB se havia um."""
        d = self.dll
        try:
            d.RelinquishVJD(self.id)
            if d.GetVJDStatus(self.id) not in (0, 1):      # 0=meu, 1=livre; 2=ocupado, 3=ausente
                return False
            if not d.AcquireVJD(self.id):
                return False
            d.ResetVJD(self.id)
        except Exception:
            return False
        self._last_axis.clear()
        self._last_btn.clear()
        if self._py_cb is not None:
            try:
                self.register_ffb(self._py_cb)
            except RuntimeError:
                pass
        return True

    def close(self):
        try:
            self.dll.RelinquishVJD(self.id)
        except Exception:
            pass
