"""Página Painel: visão geral ao vivo (direção, pedais, FFB, osciloscópio) que reorganiza as colunas conforme a largura."""
from __future__ import annotations

from . import theme as T
from .widgets import ForceMeter, PedalBars, Scope, SteeringDial


class DashboardMixin:
    def metric_card(self, parent, title, value):
        f = self.ttk.Frame(parent, style="Card.TFrame", padding=(14, 10))
        self.ttk.Label(f, text=title, style="Eyebrow.TLabel").pack(anchor="w")
        v = self.tk.StringVar(value=value)
        self.ttk.Label(f, textvariable=v, background=T.CARD, foreground="#f5f7fb",
                       font=(T.FONT, 13, "bold")).pack(anchor="w", pady=(4, 0))
        self._metric_frames.append(f)
        return v

    def dash_card(self, title, hint=""):
        f = self.ttk.Frame(self.dash_main, style="Card.TFrame", padding=14)
        head = self.ttk.Frame(f, style="Card.TFrame"); head.pack(fill="x", pady=(0, 6))
        self.ttk.Label(head, text=title, style="Section.TLabel").pack(side="left")
        if hint:
            self.ttk.Label(head, text=hint, style="Eyebrow.TLabel").pack(side="right")
        self._dash_frames.append(f)
        return f

    def build_dashboard(self):
        ttk = self.ttk
        page = self.tab_dash
        self._metric_frames, self._dash_frames = [], []
        self._dash_layout = None
        self._dash_idle = False
        self.dash_metrics = ttk.Frame(page)
        self.dash_metrics.pack(fill="x", pady=(0, 12))
        self.device_card = self.metric_card(self.dash_metrics, "DISPOSITIVO", "WingMan Formula Force GP")
        self.bridge_card = self.metric_card(self.dash_metrics, "PONTE", "PARADA")
        self.ffb_card = self.metric_card(self.dash_metrics, "FORCE FEEDBACK", self._ffb_idle_text())
        self.vjoy_card = self.metric_card(self.dash_metrics, "DESTINO", f"vJoy #{self.cfg.get('vjoy_device_id', 1)}")

        self.dash_main = ttk.Frame(page)
        self.dash_main.pack(fill="both", expand=True)
        c = self.dash_card("DIREÇÃO", "saída vJoy")
        self.dial = SteeringDial(c); self.dial.pack(fill="both", expand=True)
        c = self.dash_card("PEDAIS", "saída vJoy")
        self.pedal_bars = PedalBars(c); self.pedal_bars.pack(fill="both", expand=True)
        c = self.dash_card("FORCE FEEDBACK", "do jogo → volante")
        self.force_meter = ForceMeter(c); self.force_meter.pack(fill="x")
        self.ffb_fx_var = self.tk.StringVar(value="Efeitos: —")
        self.ffb_cap_var = self.tk.StringVar(value="Inicie a ponte para ler as capacidades do volante.")
        ttk.Label(c, textvariable=self.ffb_fx_var, background=T.CARD, foreground=T.ACCENT_HI,
                  font=(T.FONT, 9, "bold"), wraplength=260, justify="left").pack(anchor="w", pady=(4, 2))
        self.ffb_cap_lbl = ttk.Label(c, textvariable=self.ffb_cap_var, background=T.CARD, foreground=T.MUTED,
                                     font=(T.FONT, 9), wraplength=260, justify="left")
        self.ffb_cap_lbl.pack(anchor="w")
        c.bind("<Configure>", lambda e: self._wrap_ffb(e.width))
        c = self.dash_card("OSCILOSCÓPIO", "direção × força")
        self.scope = Scope(c); self.scope.pack(fill="both", expand=True)

        page.bind("<Configure>", lambda e: self.reflow_dashboard(e.width))
        self.reflow_dashboard(1000)

    def _wrap_ffb(self, width):
        wrap = max(width - 40, 120)
        self.ffb_cap_lbl.configure(wraplength=wrap)

    def _ffb_idle_text(self):
        return "Habilitado" if self.cfg.get("ffb", {}).get("enabled", True) else "Desativado"

    # ---- layout responsivo ----
    def reflow_dashboard(self, width):
        """Escolhe 4/2/1 cartões de métricas e 3/2/1 colunas de instrumentos conforme a largura útil."""
        mcols = 4 if width >= 860 else 2 if width >= 420 else 1
        icols = 3 if width >= 720 else 2 if width >= 480 else 1
        key = (mcols, icols)
        if key == self._dash_layout:
            return
        self._dash_layout = key
        for f in self._metric_frames:
            f.grid_forget()
        for i in range(4):
            self.dash_metrics.columnconfigure(i, weight=0, uniform="")
        for i, f in enumerate(self._metric_frames):
            f.grid(row=i // mcols, column=i % mcols, sticky="nsew", padx=(0 if i % mcols == 0 else 5, 0), pady=(0 if i < mcols else 5, 0))
        for i in range(mcols):
            self.dash_metrics.columnconfigure(i, weight=1, uniform="m")

        for f in self._dash_frames:
            f.grid_forget()
        for i in range(4):
            self.dash_main.columnconfigure(i, weight=0, uniform="")
            self.dash_main.rowconfigure(i, weight=0)
        dial, pedals, ffb, scope = self._dash_frames
        if icols == 3:
            spec = [(dial, 0, 0, 1), (pedals, 0, 1, 1), (ffb, 0, 2, 1), (scope, 1, 0, 3)]
        elif icols == 2:
            spec = [(dial, 0, 0, 1), (pedals, 0, 1, 1), (ffb, 1, 0, 2), (scope, 2, 0, 2)]
        else:
            spec = [(dial, 0, 0, 1), (pedals, 1, 0, 1), (ffb, 2, 0, 1), (scope, 3, 0, 1)]
        rows = max(r for _f, r, _c, _s in spec) + 1
        for f, r, c, span in spec:
            f.grid(row=r, column=c, columnspan=span, sticky="nsew",
                   padx=(0 if c == 0 else 5, 0), pady=(0 if r == 0 else 5, 0))
        for i in range(icols):
            self.dash_main.columnconfigure(i, weight=1, uniform="i")
        self.root.after(40, lambda: self.page_fit["tab_dash"]())   # a altura requisitada mudou com o reflow
        for r in range(rows):                     # a última linha (osciloscópio) estica; as demais ficam na altura natural
            self.dash_main.rowconfigure(r, weight=1 if r == rows - 1 else 0)

    # ---- atualização ----
    def update_dashboard(self, d):
        self._dash_idle = False
        out = d.get("output") or {}
        s, t, b = out.get("steering"), out.get("throttle"), out.get("brake")
        self.dial.set(s)
        self.pedal_bars.set(t, b)
        ffb = d.get("ffb")
        c = ffb.get("const") if ffb else None
        self.force_meter.set(c)
        if ffb is None:
            self.ffb_card.set("Desligado")
            self.ffb_fx_var.set("Efeitos: —")
        else:
            act = ffb.get("active") or []
            self.ffb_card.set(f"Ativo • {len(act)} efeito(s)" if act else "Ativo • sem efeitos")
            self.ffb_fx_var.set("Efeitos: " + (", ".join(act) if act else "nenhum"))
        caps = d.get("caps")
        if caps:
            n = len(caps.get("effects") or [])
            txt = f"Volante suporta {n} tipos"
            if caps.get("num_effects") is not None:
                txt += f" • {caps['num_effects']} efeitos em memória"
            self.ffb_cap_var.set(txt)
        if s is not None:
            self.scope.push(float(s) * 100, float(c or 0.0) * 100)

    def dashboard_idle(self):
        if self._dash_idle:
            return
        self._dash_idle = True
        self.dial.set(None); self.pedal_bars.set(None, None); self.force_meter.set(None)
        self.scope.clear()
        self.ffb_fx_var.set("Efeitos: —")
        self.ffb_card.set(self._ffb_idle_text())
