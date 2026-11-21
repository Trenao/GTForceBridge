"""--ffb-dump: mostra o que o jogo manda ao vJoy (sem tocar no volante). Etapa 3 do PLANO.

Serve para responder "o Forza Horizon 4 trata o vJoy como volante com FFB?". Se nada chegar, o jogo
não está mandando efeitos ao vJoy e o caminho é o Plano B (telemetria UDP).
"""
from __future__ import annotations

import math
import time
from collections import Counter
from typing import Callable, List

from .vjoy_protocol import ET_NAMES, direction_sign


def format_event(ev) -> str:
    kind = ev[0]
    if kind == "report":
        # ("report", idx, tipo, ganho, polar, direção, duração)
        extra = ev[7:]
        delay = extra[0] if extra else 0
        dirx = extra[1] if len(extra) > 1 else None
        dur = "infinita" if ev[6] in (0, 0xFFFF) else f"{ev[6]} ms"
        if ev[4]:
            ang = ev[5] / 255.0 * 360.0
            # o PID 1.0 não define o zero do ângulo: mostra o lado X sob as duas convenções
            x_east = "+" if math.cos(math.radians(ang)) >= 0 else "-"
            x_north = "+" if math.sin(math.radians(ang)) >= 0 else "-"
            dirtxt = f"polar {ang:.0f}° (lado X: zero=leste {x_east} / zero=norte {x_north})"
        else:
            dirtxt = f"cartesiano DirX={dirx}"
        return (f"report  idx={ev[1]} tipo={ET_NAMES.get(ev[2], ev[2])} ganho={ev[3]} "
                f"{dirtxt} dur={dur} atraso={delay} ms")
    return f"{kind:<7} " + " ".join(str(x) for x in ev[1:])


class DumpStats:
    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 interval: float = 5.0, warn_after: float = 10.0):
        self._clock = clock
        self.interval = interval
        self.warn_after = warn_after
        self.start = clock()
        self._next_summary = self.start + interval
        self.total = 0
        self.by_kind: Counter = Counter()
        self._warned = False
        self._dir = {}                       # idx -> (polar, byte 0-255, dirx) do último "report"
        self.dir_seen: Counter = Counter()   # descrição da direção -> nº de pacotes de força constante
        self.mag_pos = self.mag_neg = 0      # pacotes constantes com magnitude > 0 / < 0
        self.mag_min = self.mag_max = 0
        self.sides = {"east": Counter(), "north": Counter()}   # convenção -> {-1: esquerda, +1: direita}

    def _track(self, ev):
        """Junta a DIREÇÃO do último report com a MAGNITUDE de cada força constante: é o que decide o lado."""
        if ev[0] == "report":
            extra = ev[7:]
            self._dir[ev[1]] = (bool(ev[4]), ev[5], extra[1] if len(extra) > 1 else None)
        elif ev[0] == "constant" and ev[2] != 0:
            idx, mag = ev[1], ev[2]
            polar, byte, dirx = self._dir.get(idx, (False, 0, None))
            self.mag_pos += mag > 0
            self.mag_neg += mag < 0
            self.mag_min, self.mag_max = min(self.mag_min, mag), max(self.mag_max, mag)
            self.dir_seen[f"polar {byte / 255.0 * 360.0:.0f}°" if polar else f"cartesiano X{'-' if (dirx or 0) < 0 else '+'}"] += 1
            for conv in self.sides:
                self.sides[conv][(1 if mag > 0 else -1) * int(direction_sign(polar, byte, dirx, conv))] += 1

    def side_summary(self):
        """Linhas que respondem: o jogo manda força para os DOIS lados? Qual convenção do zero polar mostra isso?"""
        n = self.mag_pos + self.mag_neg
        if not n:
            return ["[ffb-dump] lados: nenhuma força constante com magnitude ≠ 0 recebida ainda."]
        out = [f"[ffb-dump] lados da força constante ({n} pacotes ≠ 0): magnitude + {self.mag_pos} / − {self.mag_neg} "
               f"(faixa {self.mag_min}…{self.mag_max})",
               "[ffb-dump]   direções vistas: " + ", ".join(f"{k} ×{v}" for k, v in self.dir_seen.most_common(6))]
        for conv, label in (("east", "zero=leste (padrão)"), ("north", "zero=norte (DirectInput)")):
            c = self.sides[conv]
            out.append(f"[ffb-dump]   {label}: esquerda {c[-1]} / direita {c[1]}")
        e, no = self.sides["east"], self.sides["north"]
        one = lambda c: (c[-1] == 0) != (c[1] == 0)
        if one(e) and not one(no):
            out.append("[ffb-dump]   → só uma convenção produz os dois lados: 'north' (aba Force Feedback → Zero da direção polar).")
        elif one(no) and not one(e):
            out.append("[ffb-dump]   → só uma convenção produz os dois lados: 'east' (padrão atual).")
        elif one(e) and one(no):
            out.append("[ffb-dump]   → as duas convenções dão um lado só: o próprio jogo manda força de um lado só "
                       "(dirija virando para os dois lados durante a captura).")
        return out

    def consume(self, q) -> List[str]:
        """Esvazia a fila de eventos e devolve as linhas a imprimir."""
        lines = []
        while True:
            try:
                ev = q.get_nowait()
            except Exception:
                break
            self.total += 1
            self.by_kind[ev[0]] += 1
            self._track(ev)
            lines.append("[ffb-dump] " + format_event(ev))
        return lines

    def periodic(self) -> List[str]:
        now = self._clock()
        out: List[str] = []
        if self.total == 0 and not self._warned and now - self.start >= self.warn_after:
            self._warned = True
            out.append("[ffb-dump] nenhum pacote recebido ainda. Entre numa corrida no jogo; se continuar "
                       "vazio, o jogo não está mandando FFB ao vJoy (ver Plano B no PLANO.md).")
        if now >= self._next_summary:
            self._next_summary = now + self.interval
            if self.total:
                out.append("[ffb-dump] resumo: " + self.summary())
                out.extend(self.side_summary())
        return out

    def summary(self) -> str:
        if not self.total:
            return "0 pacotes"
        kinds = ", ".join(f"{k}={n}" for k, n in sorted(self.by_kind.items()))
        return f"{self.total} pacotes ({kinds})"
