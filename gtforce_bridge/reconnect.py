"""Lógica de reconexão do volante (pura, testável sem hardware).

`WheelLink.poll(attached)` é chamado a cada tick do loop. Quando o volante some, chama `on_lost()` uma
vez; enquanto estiver ausente tenta `try_reopen()` a cada `retry_s` segundos; quando volta chama
`on_back(novo_volante)`. Enquanto estiver ausente `poll` devolve False (o loop mantém o vJoy neutro).
"""
from __future__ import annotations

import time
from typing import Callable


class WheelLink:
    def __init__(self, try_reopen: Callable[[], object], on_lost: Callable[[], None],
                 on_back: Callable[[object], None], retry_s: float = 1.0,
                 clock: Callable[[], float] = time.monotonic):
        self._try = try_reopen
        self._lost = on_lost
        self._back = on_back
        self.retry_s = retry_s
        self._clock = clock
        self.connected = True
        self._next_try = 0.0
        self.reconnects = 0

    def poll(self, attached: bool) -> bool:
        if self.connected:
            if attached:
                return True
            self.connected = False
            self._next_try = self._clock() + self.retry_s
            self._lost()
            return False
        now = self._clock()
        if now < self._next_try:
            return False
        self._next_try = now + self.retry_s
        try:
            new = self._try()
        except Exception:
            new = None
        if new is None:
            return False
        self.connected = True
        self.reconnects += 1
        self._back(new)
        return True
