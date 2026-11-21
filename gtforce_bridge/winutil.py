"""Utilidades do Windows: resolução de timer de 1 ms e prioridade do processo.

Fora do Windows (ou se a chamada falhar) tudo vira no-op e devolve False, para a ponte
continuar funcionando e os testes rodarem em qualquer sistema.
"""
from __future__ import annotations

import ctypes
import sys

HIGH_PRIORITY_CLASS = 0x00000080
TIMERR_NOERROR = 0

_timer_ms = None          # período ativo (precisa do timeEndPeriod correspondente)


def _winmm():
    return ctypes.windll.winmm if sys.platform == "win32" else None


def _kernel32():
    return ctypes.windll.kernel32 if sys.platform == "win32" else None


def begin_timer_resolution(ms: int = 1) -> bool:
    """timeBeginPeriod(ms): faz time.sleep() ter ~1 ms de precisão (essencial a 500 Hz)."""
    global _timer_ms
    try:
        w = _winmm()
        if w is None or _timer_ms is not None:
            return _timer_ms is not None
        if w.timeBeginPeriod(int(ms)) == TIMERR_NOERROR:
            _timer_ms = int(ms)
            return True
    except Exception:
        pass
    return False


def end_timer_resolution() -> None:
    """Desfaz o timeBeginPeriod (o Windows exige o par Begin/End com o mesmo valor)."""
    global _timer_ms
    if _timer_ms is None:
        return
    try:
        w = _winmm()
        if w is not None:
            w.timeEndPeriod(_timer_ms)
    except Exception:
        pass
    _timer_ms = None


def set_high_priority() -> bool:
    """Eleva a classe de prioridade do processo para HIGH (não exige administrador)."""
    try:
        k = _kernel32()
        if k is None:
            return False
        return bool(k.SetPriorityClass(k.GetCurrentProcess(), HIGH_PRIORITY_CLASS))
    except Exception:
        return False
