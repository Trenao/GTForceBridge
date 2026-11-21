"""Aba Force Feedback: ganhos, inversão, opções avançadas e painel ao vivo do que o jogo manda ao volante."""
from __future__ import annotations

GAINS = [("master_gain", "Ganho geral"), ("constant_scale", "Força constante"),
         ("condition_scale", "Mola / amortecimento"), ("periodic_scale", "Efeitos periódicos"),
         ("ramp_scale", "Rampa (start/end)")]

# (chave, rótulo, mín., máx., passo, dica)
NUMBERS = [
    ("update_hz", "Atualizações/s por efeito", 0, 1000, 10, "0 = sem limite. O GT Force é USB 1.1: 60–100 costuma bastar."),
    ("slew_per_sec", "Suavização da força (fração/s)", 0, 100, 0.5, "0 = desligada. Evita trancos; valores baixos deixam a força 'mole'."),
    ("const_deadzone_pct", "Ignorar força abaixo de (%)", 0, 50, 0.5, "Ruído com o carro parado."),
    ("magnitude_scale", "Escala de magnitude forçada", 0, 65535, 1, "0 = automática (10000 ou 32767). 255 só se o ffb-dump mostrar 8 bits."),
]


class FfbTabMixin:
    """Aba Force Feedback."""

    def build_ffb(self):
        tk, ttk = self.tk, self.ttk
        ffb = self.cfg["ffb"]

        # ---- ao vivo ----
        live = self.section(self.tab_ffb, "AO VIVO (ponte em execução)")
        row = ttk.Frame(live, style="Card.TFrame"); row.pack(fill="x", pady=4)
        ttk.Label(row, text="Força constante", background="#141d2b", width=24).pack(side="left")
        self.ffb_live_bar = ttk.Progressbar(row, maximum=200, length=360); self.ffb_live_bar.pack(side="left", fill="x", expand=True, padx=10)
        self.ffb_live_val = ttk.Label(row, text="—", background="#141d2b", width=8); self.ffb_live_val.pack(side="right")
        self.ffb_live_bar["value"] = 100
        row = ttk.Frame(live, style="Card.TFrame"); row.pack(fill="x", pady=4)
        ttk.Label(row, text="Efeitos tocando", background="#141d2b", width=24).pack(side="left")
        self.ffb_live_active = ttk.Label(row, text="—", background="#141d2b", foreground="#ff914d"); self.ffb_live_active.pack(side="left")
        row = ttk.Frame(live, style="Card.TFrame"); row.pack(fill="x", pady=4)
        ttk.Label(row, text="Capacidades do volante", background="#141d2b", width=24).pack(side="left", anchor="n")
        self.ffb_caps_lbl = ttk.Label(row, text="(inicie a ponte ou use 'Detectar volante')", background="#141d2b",
                                      wraplength=640, justify="left"); self.ffb_caps_lbl.pack(side="left")

        # ---- ganhos ----
        box = self.section(self.tab_ffb, "GANHOS")
        self.ffb_enabled = tk.BooleanVar(value=bool(ffb.get("enabled", True)))
        ttk.Checkbutton(box, text="Ativar repasse de Force Feedback", variable=self.ffb_enabled).pack(anchor="w")
        self.ffb_vars = {}
        for key, label in GAINS:
            row = ttk.Frame(box, style="Card.TFrame"); row.pack(fill="x", pady=5)
            ttk.Label(row, text=label, background="#141d2b", width=24).pack(side="left")
            v = tk.DoubleVar(value=float(ffb.get(key, 1)))
            val = ttk.Label(row, text=f"{v.get():.2f}", background="#141d2b", width=5); val.pack(side="right")
            ttk.Scale(row, from_=0, to=1.5, variable=v,
                      command=lambda _x, v=v, val=val: val.configure(text=f"{v.get():.2f}")).pack(side="left", fill="x", expand=True, padx=8)
            self.ffb_vars[key] = v
        self.ffb_invert = tk.BooleanVar(value=bool(ffb.get("invert", False)))
        ttk.Checkbutton(box, text="Inverter sinal da força constante (a autocalibração mede isto)", variable=self.ffb_invert).pack(anchor="w", pady=(6, 0))
        self.ffb_min_lbl = ttk.Label(box, text="", background="#141d2b", foreground="#8d9bb0"); self.ffb_min_lbl.pack(anchor="w")
        self.refresh_ffb_measured()

        # ---- avançado ----
        adv = self.section(self.tab_ffb, "AVANÇADO")
        self.ffb_num = {}
        for key, label, lo, hi, step, tip in NUMBERS:
            row = ttk.Frame(adv, style="Card.TFrame"); row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, background="#141d2b", width=32).pack(side="left")
            v = tk.StringVar(value=str(ffb.get(key, 0)))
            ttk.Spinbox(row, from_=lo, to=hi, increment=step, textvariable=v, width=9).pack(side="left", padx=6)
            ttk.Label(row, text=tip, background="#141d2b", foreground="#8d9bb0").pack(side="left", padx=8)
            self.ffb_num[key] = (v, lo, hi)
        self.ffb_choice = {}
        for key, label, options, tip in [
            ("direction_mode", "Direção dos efeitos no volante", ("steering", "cartesian"),
             "steering = eixo de direção do SDL (padrão); cartesian = vetor (1,0)."),
            ("polar_zero", "Zero da direção polar do jogo", ("east", "north"),
             "north = convenção DirectInput (padrão; 90° = +X, 270° = −X); east = a partir de +X (perde o lado em 90°/270°).")]:
            row = ttk.Frame(adv, style="Card.TFrame"); row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, background="#141d2b", width=32).pack(side="left")
            v = tk.StringVar(value=str(ffb.get(key, options[0])))
            ttk.Combobox(row, textvariable=v, values=options, state="readonly", width=10).pack(side="left", padx=6)
            ttk.Label(row, text=tip, background="#141d2b", foreground="#8d9bb0").pack(side="left", padx=8)
            self.ffb_choice[key] = v
        self.ffb_flags = {}
        for key, label, default in [
            ("honor_duration", "Respeitar duração, loops e atraso dos efeitos do jogo (PID 1.0)", True),
            ("disable_autocenter", "Desligar o autocenter do driver ao abrir o volante", True)]:
            v = tk.BooleanVar(value=bool(ffb.get(key, default)))
            ttk.Checkbutton(adv, text=label, variable=v).pack(anchor="w", pady=2)
            self.ffb_flags[key] = v

        ttk.Button(self.tab_ffb, text="Salvar FFB", style="Accent.TButton", command=self.save_ffb).pack(anchor="e", pady=(6, 0))
        ttk.Label(self.tab_ffb, text="Nota: envelopes (attack/fade) ainda não são aplicados pela ponte. O autocenter do driver Logitech "
                  "deve ser desligado no LGS/G HUB ou o volante ocultado via HidHide. As opções valem a quente (sem reiniciar a ponte), "
                  "exceto 'Desligar o autocenter', que é lida ao abrir o volante.",
                  style="Muted.TLabel", wraplength=900, justify="left").pack(anchor="w", pady=6)

    # ---- helpers ----
    def refresh_ffb_measured(self):
        ffb = self.cfg["ffb"]
        mm = float(ffb.get("min_effective_magnitude", 0) or 0)
        co = float(ffb.get("center_offset", 0) or 0)
        self.ffb_min_lbl.configure(
            text=f"Medido pela autocalibração: força mínima {mm*100:.1f}%  •  centro {co:+.3f}" if (mm or co)
            else "Autocalibração ainda não aplicada (força mínima 0%, centro 0).")

    def update_ffb_live(self, d):
        """Chamado a cada telemetria (monitor_tab.poll_telemetry)."""
        ffb = d.get("ffb")
        if ffb is None:
            self.ffb_live_val.configure(text="—"); self.ffb_live_bar["value"] = 100
            self.ffb_live_active.configure(text="FFB desligado ou sem efeitos")
        else:
            c = ffb.get("const")
            self.ffb_live_val.configure(text="—" if c is None else f"{c*100:+.0f}%")
            self.ffb_live_bar["value"] = 100 + (c or 0.0) * 100
            act = ffb.get("active") or []
            self.ffb_live_active.configure(text=", ".join(act) if act else "nenhum")
        caps = d.get("caps")
        if caps and caps != getattr(self, "_caps_shown", None):
            self._caps_shown = caps
            bits = [", ".join(caps.get("effects") or []) or "nenhum efeito"]
            for key, label in (("num_effects", "efeitos na memória do driver"), ("num_playing", "simultâneos"), ("axes", "eixos com FFB")):
                if caps.get(key) is not None:
                    bits.append(f"{label}: {caps[key]}")
            self.ffb_caps_lbl.configure(text="  •  ".join(bits))

    def save_ffb(self):
        ffb = self.cfg["ffb"]
        ffb["enabled"] = bool(self.ffb_enabled.get())
        for k, v in self.ffb_vars.items():
            ffb[k] = round(v.get(), 3)
        ffb["invert"] = bool(self.ffb_invert.get())
        for k, (v, lo, hi) in self.ffb_num.items():
            try:
                x = float(str(v.get()).replace(",", "."))
            except ValueError:
                self.messagebox.showwarning("Force Feedback", f"Valor inválido em '{k}'."); return
            ffb[k] = max(lo, min(hi, x))
            v.set(str(ffb[k]))
        for k, v in self.ffb_choice.items():
            ffb[k] = v.get()
        for k, v in self.ffb_flags.items():
            ffb[k] = bool(v.get())
        # o perfil da autocal é aplicado POR CIMA ao iniciar a ponte: sincroniza para não desfazer o que o usuário acabou de salvar
        for prof in (ffb.get("autocal_by_pid") or {}).values():
            for k in ("constant_scale", "invert"):
                if k in prof:
                    prof[k] = ffb[k]
        self.save_config()
