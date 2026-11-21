"""Aba Mapeamento: eixos físicos -> eixos do vJoy."""
from __future__ import annotations


class MappingTabMixin:
    """Aba Mapeamento: eixos físicos -> eixos do vJoy."""

    def build_mapping(self):
        box=self.section(self.tab_map,"MAPEAMENTO SDL → vJoy")
        self.map_vars={}
        fields=[("steering","Direção SDL (A#)","axes","steering"),("pedals","Acelerador / eixo combinado (A#)","axes","pedals"),("brake","Freio SDL (A#)","axes","brake")]
        for key,label,group,sub in fields:
            row=self.ttk.Frame(box,style="Card.TFrame"); row.pack(fill="x",pady=4)
            self.ttk.Label(row,text=label,background="#141d2b",width=34).pack(side="left")
            v=self.tk.IntVar(value=int(self.cfg[group][sub])); self.map_vars[key]=v
            self.ttk.Spinbox(row,from_=0,to=15,textvariable=v,width=7).pack(side="left")
        row=self.ttk.Frame(box,style="Card.TFrame"); row.pack(fill="x",pady=4)
        self.ttk.Label(row,text="Modo dos pedais",background="#141d2b",width=34).pack(side="left")
        self.pedals_mode=self.tk.StringVar(value=self.cfg.get("pedals_mode","combined"))
        self.ttk.Combobox(row,textvariable=self.pedals_mode,values=["combined","separate"],state="readonly",width=15).pack(side="left")
        for key,label in [("steering","Direção"),("throttle","Acelerador"),("brake","Freio")]:
            row=self.ttk.Frame(box,style="Card.TFrame"); row.pack(fill="x",pady=4)
            self.ttk.Label(row,text=f"Saída vJoy — {label}",background="#141d2b",width=34).pack(side="left")
            v=self.tk.StringVar(value=self.cfg["vjoy_axes"][key]); self.map_vars["vjoy_"+key]=v
            self.ttk.Combobox(row,textvariable=v,values=["X","Y","Z","RX","RY","RZ","SL0","SL1"],state="readonly",width=15).pack(side="left")
        self.ttk.Button(self.tab_map,text="Salvar mapeamento",style="Accent.TButton",command=self.save_mapping).pack(anchor="e")

    def save_mapping(self):
        for key in ("steering","pedals","brake"): self.cfg["axes"][key]=int(self.map_vars[key].get())
        self.cfg["pedals_mode"]=self.pedals_mode.get()
        for key in ("steering","throttle","brake"): self.cfg["vjoy_axes"][key]=self.map_vars["vjoy_"+key].get()
        self.save_config()
