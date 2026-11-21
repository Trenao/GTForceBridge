"""Instrumentos desenhados em canvas (volante, pedais, força, osciloscópio). Redesenham ao redimensionar."""
from __future__ import annotations

import math
import tkinter as tk
from collections import deque

from . import theme as T


class _Instrument(tk.Canvas):
    def __init__(self, master, height=180, **kw):
        super().__init__(master, bg=T.CARD, highlightthickness=0, bd=0, height=height, **kw)
        self.bind("<Configure>", lambda _e: self.redraw())

    def size(self):
        return max(self.winfo_width(), 1), max(self.winfo_height(), 1)

    def redraw(self):  # pragma: no cover - sobrescrito
        pass


class SteeringDial(_Instrument):
    """Marcador de 270° com agulha. Valor em -1..+1 (None = sem sinal)."""

    def __init__(self, master, **kw):
        super().__init__(master, height=210, **kw)
        self.value = None

    def set(self, v):
        if v is not None:
            v = max(-1.0, min(1.0, float(v)))
        if v != self.value:
            self.value = v
            self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.size()
        if w < 60 or h < 60:
            return
        cx, cy = w / 2, (h - 26) / 2 + 6
        r = max(min(w / 2 - 30, (h - 26) / 2 - 10), 24)
        box = (cx - r, cy - r, cx + r, cy + r)
        self.create_arc(*box, start=225, extent=-270, style="arc", width=12, outline=T.TRACK)
        for i in range(7):                                 # marcas a cada 45°
            a = math.radians(225 - i * 45)
            self.create_line(cx + (r + 14) * math.cos(a), cy - (r + 14) * math.sin(a),
                             cx + (r + 20) * math.cos(a), cy - (r + 20) * math.sin(a), fill="#4a5a75", width=1)
        v = self.value
        if v is None:
            self.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, outline="#cbd5e1", width=2)
            self.create_text(cx, cy + r * 0.62, text="—", fill=T.MUTED, font=(T.FONT, 10))
            return
        if abs(v) > 0.004:
            self.create_arc(*box, start=90, extent=-v * 135, style="arc", width=12, outline=T.ACCENT)
        a = math.radians(90 - v * 135)
        self.create_line(cx, cy, cx + (r - 6) * math.cos(a), cy - (r - 6) * math.sin(a),
                         fill="#ffffff", width=3, capstyle="round")
        self.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, fill=T.CARD, outline="#ffffff", width=2)
        self.create_text(cx, cy + r * 0.62, text=f"{v * 100:+.0f}%", fill=T.TEXT, font=(T.FONT, 10, "bold"))


class PedalBars(_Instrument):
    """Duas barras verticais: acelerador (verde) e freio (vermelho). Valores 0..1."""

    def __init__(self, master, **kw):
        super().__init__(master, height=210, **kw)
        self.thr = self.brk = None

    def set(self, thr, brk):
        t = None if thr is None else max(0.0, min(1.0, float(thr)))
        b = None if brk is None else max(0.0, min(1.0, float(brk)))
        if (t, b) != (self.thr, self.brk):
            self.thr, self.brk = t, b
            self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.size()
        if w < 60 or h < 60:
            return
        bw = max(28, min(70, w * 0.22))
        top, bot = 8, h - 40
        for cx, val, label, color in ((w * 0.30, self.thr, "ACEL.", T.OK), (w * 0.70, self.brk, "FREIO", T.BAD)):
            x0, x1 = cx - bw / 2, cx + bw / 2
            self.create_rectangle(x0, top, x1, bot, fill=T.TRACK, outline="")
            if val:
                self.create_rectangle(x0, bot - (bot - top) * val, x1, bot, fill=color, outline="")
            self.create_text(cx, bot + 14, text=label, fill=T.MUTED, font=(T.FONT, 9))
            self.create_text(cx, bot + 30, text="—" if val is None else f"{val * 100:.0f}%", fill=T.TEXT,
                             font=(T.FONT, 9, "bold"))


class ForceMeter(_Instrument):
    """Barra horizontal centrada para a força constante (-1..+1)."""

    def __init__(self, master, **kw):
        super().__init__(master, height=70, **kw)
        self.value = None
        self.raw = None          # magnitude bruta do jogo (antes do sinal/ganhos), só como referência

    def set(self, v, raw=None):
        if v is not None:
            v = max(-1.0, min(1.0, float(v)))
        if raw is not None:
            raw = max(-1.0, min(1.0, float(raw)))
        if (v, raw) != (self.value, self.raw):
            self.value, self.raw = v, raw
            self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.size()
        if w < 80:
            return
        x0, x1, y0, y1 = 6, w - 6, 8, 26
        mid = (x0 + x1) / 2
        self.create_rectangle(x0, y0, x1, y1, fill=T.TRACK, outline="")
        v = self.value
        if v:
            self.create_rectangle(mid, y0, mid + v * (x1 - x0) / 2, y1, fill=T.INFO, outline="")
        if self.raw is not None:                    # triângulo cinza sob a barra = o que o jogo pediu (bruto)
            rx = mid + self.raw * (x1 - x0) / 2
            self.create_polygon(rx, y1 + 2, rx - 4, y1 + 9, rx + 4, y1 + 9, fill=T.MUTED, outline="")
        mx = mid + (v or 0) * (x1 - x0) / 2
        self.create_line(mx, y0 - 3, mx, y1 + 3, fill="#ffffff", width=2)
        self.create_text(x0, y1 + 16, text="ESQ", fill=T.MUTED, font=(T.FONT, 8), anchor="w")
        self.create_text(x1, y1 + 16, text="DIR", fill=T.MUTED, font=(T.FONT, 8), anchor="e")
        self.create_text(mid, y1 + 16, text="—" if v is None else f"{v * 100:+.0f}%", fill=T.TEXT,
                         font=(T.FONT, 9, "bold"))


class Scope(_Instrument):
    """Osciloscópio: direção (laranja) × força constante (azul), janela rolante de ~8 s."""
    SAMPLES = 160

    def __init__(self, master, **kw):
        super().__init__(master, height=170, **kw)
        self.a = deque(maxlen=self.SAMPLES)
        self.b = deque(maxlen=self.SAMPLES)
        self.c = deque(maxlen=self.SAMPLES)      # magnitude bruta do jogo (referência)
        self._pending = False

    def push(self, a, b, c=None):
        self.a.append(a); self.b.append(b); self.c.append(b if c is None else c)
        if not self._pending:                      # no máximo ~20 quadros/s
            self._pending = True
            self.after(50, self._flush)

    def _flush(self):
        self._pending = False
        self.redraw()

    def clear(self):
        if self.a or self.b:
            self.a.clear(); self.b.clear(); self.c.clear()
            self.redraw()

    def redraw(self):
        self.delete("all")
        w, h = self.size()
        if w < 120 or h < 80:
            return
        left, right, top, bot = 40, w - 8, 8, h - 28
        for val in (100, 50, 0, -50, -100):
            y = top + (100 - val) / 200 * (bot - top)
            self.create_line(left, y, right, y, fill=T.TRACK if val == 0 else "#1f2b3d", dash=() if val == 0 else (2, 4))
            self.create_text(left - 6, y, text=f"{val:+d}" if val else "0", fill=T.MUTED, font=(T.FONT, 8), anchor="e")
        dx = (right - left) / (self.SAMPLES - 1)
        for data, color, dash in ((self.c, T.MUTED, (3, 3)), (self.a, T.ACCENT, ()), (self.b, T.INFO, ())):
            n = len(data)
            if n < 2:
                continue
            pts = []
            for i, v in enumerate(data):
                v = max(-100.0, min(100.0, v))
                pts += [right - (n - 1 - i) * dx, top + (100 - v) / 200 * (bot - top)]
            self.create_line(*pts, fill=color, width=1 if dash else 2, dash=dash)
        self.create_text(left, h - 10, text="direção", fill=T.ACCENT, font=(T.FONT, 9), anchor="w")
        self.create_text(left + 70, h - 10, text="enviado ao volante", fill=T.INFO, font=(T.FONT, 9), anchor="w")
        self.create_text(left + 190, h - 10, text="- - jogo (bruto)", fill=T.MUTED, font=(T.FONT, 9), anchor="w")
        self.create_text(right, h - 10, text="últimos 8 s", fill=T.MUTED, font=(T.FONT, 9), anchor="e")
