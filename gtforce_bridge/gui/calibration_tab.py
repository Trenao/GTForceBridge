"""Abas Calibração e Alcance dos eixos (centro, mín/máx, expo, zona morta)."""
from __future__ import annotations

from ..config import DEFAULT_CONFIG


class CalibrationTabMixin:
    """Abas Calibração e Alcance dos eixos (centro, mín/máx, expo, zona morta)."""

    def build_calibration(self):
        self.cal_vars={}
        for section in ("steering","throttle","brake"):
            box=self.section(self.tab_cal,section.upper())
            self.cal_vars[section]={}
            for key,label,mn,mx in [("deadzone","Zona morta",0,0.5),("expo","Curva / expo",0,1),("gain","Ganho",0.1,2)]:
                row=self.ttk.Frame(box,style="Card.TFrame"); row.pack(fill="x",pady=3)
                self.ttk.Label(row,text=label,background="#141d2b",width=18).pack(side="left")
                var=self.tk.DoubleVar(value=float(self.cfg[section].get(key,0)))
                self.ttk.Scale(row,from_=mn,to=mx,variable=var,command=lambda _v,s=section,k=key,v=var:self.set_curve(s,k,v.get())).pack(side="left",fill="x",expand=True,padx=8)
                out=self.ttk.Label(row,text=f"{var.get():.2f}",background="#141d2b",width=6); out.pack(side="right")
                self.cal_vars[section][key]=(var,out)
        self.ttk.Button(self.tab_cal,text="Salvar calibração",style="Accent.TButton",command=self.save_config).pack(anchor="e",pady=5)

    def build_range(self):
        ttk=self.ttk
        self.cal_axes=[("steering","Direção","steering"),("throttle","Acelerador","pedals"),("brake","Freio","brake")]
        self.cap_active={}; self.cap_range={}; self.last_raw={}; self.cal_live={}; self.cal_info={}; self.cap_btn={}
        box=self.section(self.tab_range,"CALIBRAR O ALCANCE REAL DOS EIXOS")
        ttk.Label(box,text="A ponte precisa estar rodando. Os valores lidos vêm da telemetria dela.",background="#141d2b",foreground="#8d9bb0",wraplength=1000,justify="left").pack(anchor="w",pady=(0,8))
        for name,label,_ in self.cal_axes:
            row=ttk.Frame(box,style="Card.TFrame"); row.pack(fill="x",pady=6)
            ttk.Label(row,text=label,background="#141d2b",width=12,font=("Segoe UI",10,"bold")).pack(side="left")
            live=ttk.Label(row,text="—",background="#141d2b",foreground="#ff914d",width=9); live.pack(side="left"); self.cal_live[name]=live
            info=ttk.Label(row,text="",background="#141d2b",width=30); info.pack(side="left",padx=8); self.cal_info[name]=info
            b=ttk.Button(row,text="Capturar curso" if name!="steering" else "Capturar giro",command=lambda n=name:self.toggle_capture(n)); b.pack(side="left",padx=3); self.cap_btn[name]=b
            if name=="steering":
                ttk.Button(row,text="Centro = atual",command=self.set_center_now).pack(side="left",padx=3)
            ttk.Button(row,text="Resetar",command=lambda n=name:self.reset_range(n)).pack(side="left",padx=3)
        self.refresh_cal_labels()

    def refresh_cal_labels(self):
        if not hasattr(self,"cal_info"):return
        cal=self.cfg.get("calibration",{})
        for name,_,_ in self.cal_axes:
            c=cal.get(name,{})
            txt=f"mín {c.get('min',-1):+.3f}  máx {c.get('max',1):+.3f}"
            if name=="steering":txt+=f"  centro {c.get('center',0):+.3f}"
            if self.cap_active.get(name):
                r=self.cap_range.get(name)
                if r:txt=f"CAPTURANDO… {r[0]:+.3f} .. {r[1]:+.3f}"
            self.cal_info[name].configure(text=txt)

    def update_capture(self,d):
        phys=d.get("physical",{})
        for name,_,akey in self.cal_axes:
            try:v=float(phys.get(f"A{int(self.cfg['axes'][akey])}",0.0))
            except (ValueError,KeyError,TypeError):continue
            self.last_raw[name]=v; self.cal_live[name].configure(text=f"{v:+.3f}")
            if self.cap_active.get(name):
                r=self.cap_range.setdefault(name,[v,v]); r[0]=min(r[0],v); r[1]=max(r[1],v)
        self.refresh_cal_labels()

    def toggle_capture(self,name):
        if name not in self.last_raw:
            self.messagebox.showinfo("Calibração","Inicie a ponte primeiro."); return
        if not self.cap_active.get(name):
            v=self.last_raw[name]; self.cap_range[name]=[v,v]; self.cap_active[name]=True
            self.cap_btn[name].configure(text="Parar e aplicar"); return
        self.cap_active[name]=False
        self.cap_btn[name].configure(text="Capturar giro" if name=="steering" else "Capturar curso")
        lo,hi=self.cap_range.get(name,[0,0])
        if hi-lo<0.2:
            self.messagebox.showwarning("Calibração","Movimento muito pequeno. Nada foi alterado."); self.refresh_cal_labels(); return
        c=self.cfg["calibration"][name]; c["min"]=round(lo,4); c["max"]=round(hi,4)
        if name=="steering" and not (lo<c.get("center",0.0)<hi):c["center"]=round((lo+hi)/2,4)
        self.save_config(); self.refresh_cal_labels()

    def set_center_now(self):
        if "steering" not in self.last_raw:
            self.messagebox.showinfo("Calibração","Inicie a ponte primeiro."); return
        self.cfg["calibration"]["steering"]["center"]=round(self.last_raw["steering"],4)
        self.save_config(); self.refresh_cal_labels()

    def reset_range(self,name):
        self.cap_active[name]=False
        self.cap_btn[name].configure(text="Capturar giro" if name=="steering" else "Capturar curso")
        self.cfg["calibration"][name]=dict(DEFAULT_CONFIG["calibration"][name])
        self.save_config(); self.refresh_cal_labels()

    def set_curve(self, section, key, value):
        self.cfg[section][key]=round(float(value),3)
        self.cal_vars[section][key][1].configure(text=f"{value:.2f}")
