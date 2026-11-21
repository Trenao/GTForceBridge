"""Aba Monitor: cartões de eixos ao vivo e leitura da telemetria da ponte."""
from __future__ import annotations

import json
import os

from ..paths import TELEMETRY_PATH


class MonitorTabMixin:
    """Aba Monitor: cartões de eixos ao vivo e leitura da telemetria da ponte."""

    def build_monitor(self):
        f=self.section(self.tab_monitor,"ENTRADAS DO VOLANTE FÍSICO")
        self.monitor_labels={}; self.monitor_bars={}
        for i in range(4):
            row=self.ttk.Frame(f,style="Card.TFrame"); row.pack(fill="x",pady=4)
            self.ttk.Label(row,text=f"Eixo A{i}",background="#141d2b",width=12).pack(side="left")
            bar=self.ttk.Progressbar(row,maximum=100,length=500); bar.pack(side="left",fill="x",expand=True,padx=10)
            val=self.ttk.Label(row,text="0.000",background="#141d2b",width=9); val.pack(side="right")
            self.monitor_bars[i]=bar; self.monitor_labels[i]=val
        b=self.section(self.tab_monitor,"SAÍDAS PROCESSADAS PARA vJoy")
        self.output_labels={}
        for name in ("steering","throttle","brake"):
            row=self.ttk.Frame(b,style="Card.TFrame"); row.pack(fill="x",pady=4)
            self.ttk.Label(row,text=name.upper(),background="#141d2b",width=12).pack(side="left")
            v=self.ttk.Label(row,text="aguardando ponte…",background="#141d2b",foreground="#ff914d"); v.pack(side="left")
            self.output_labels[name]=v
        self.button_state=self.ttk.Label(self.tab_monitor,text="Botões: —",style="Muted.TLabel"); self.button_state.pack(anchor="w",pady=8)

    def poll_telemetry(self):
        try:
            if os.path.exists(TELEMETRY_PATH):
                with open(TELEMETRY_PATH,encoding="utf-8") as f:d=json.load(f)
                self.device_card.set(d.get("device","Volante conectado")); self.bridge_card.set("ATIVA")
                for i in range(4):
                    v=float(d.get("physical",{}).get(f"A{i}",0)); self.monitor_labels[i].configure(text=f"{v:+.3f}"); self.monitor_bars[i]["value"]=(v+1)*50
                for k,v in d.get("output",{}).items():
                    if k in self.output_labels:self.output_labels[k].configure(text=f"{v:+.3f}" if k=="steering" else f"{v:.3f}")
                self.update_capture(d)
                self.update_ffb_live(d)
                self.update_dashboard(d)
                if self.proc and self.proc.poll() is None: self.set_run_state("running")
                self.button_state.configure(text="Botões: "+" ".join(f"B{i+1}:{'●' if x else '○'}" for i,x in enumerate(d.get("buttons",[]))))
            elif not (self.proc and self.proc.poll() is None):
                self.bridge_card.set("PARADA"); self.dashboard_idle()
        except (OSError,ValueError,KeyError):pass
        self.root.after(50,self.poll_telemetry)
