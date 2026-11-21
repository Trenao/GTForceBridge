"""Aba Perfis: salvar, carregar, atualizar e apagar perfis do config."""
from __future__ import annotations

import json
import os

from ..config import DEFAULT_CONFIG, _sanitize_ffb, deep_merge
from ..paths import PROFILES_DIR


class ProfilesTabMixin:
    """Aba Perfis: salvar, carregar, atualizar e apagar perfis do config."""

    def build_profiles(self):
        box=self.section(self.tab_profiles,"PERFIS DE CONFIGURAÇÃO")
        self.ttk.Label(box,text="Cada perfil guarda mapeamento, calibração e Force Feedback.",background="#141d2b").pack(anchor="w",pady=(0,8))
        row=self.ttk.Frame(box,style="Card.TFrame"); row.pack(fill="x")
        self.profile_name=self.tk.StringVar(value="Forza Horizon 4")
        self.ttk.Entry(row,textvariable=self.profile_name,width=32).pack(side="left",padx=4)
        self.ttk.Button(row,text="Salvar como novo",style="Accent.TButton",command=self.save_profile).pack(side="left",padx=4)
        self.ttk.Button(row,text="Atualizar selecionado",command=self.update_profile).pack(side="left",padx=4)
        self.ttk.Button(row,text="Excluir",command=self.delete_profile).pack(side="left",padx=4)
        self.profile_list=self.tk.Listbox(box,height=8,bg="#080d14",fg="#e8edf5",selectbackground="#f47721",relief="flat")
        self.profile_list.pack(fill="both",expand=True,pady=10)
        self.refresh_profiles()

    def profile_names(self):
        os.makedirs(PROFILES_DIR,exist_ok=True)
        return sorted(os.path.splitext(x)[0] for x in os.listdir(PROFILES_DIR) if x.lower().endswith(".json"))

    def refresh_profiles(self):
        names=self.profile_names(); self.profile_box.configure(values=names)
        if hasattr(self,"profile_list"):
            self.profile_list.delete(0,"end")
            for n in names:self.profile_list.insert("end",n)

    def profile_path(self,name):
        safe="".join(c for c in name if c.isalnum() or c in " -_().").strip()
        if not safe: raise ValueError("Dê um nome válido ao perfil.")
        return os.path.join(PROFILES_DIR,safe+".json"),safe

    def save_profile(self):
        try:
            path,name=self.profile_path(self.profile_name.get()); os.makedirs(PROFILES_DIR,exist_ok=True)
            with open(path,"w",encoding="utf-8") as f:json.dump(self.cfg,f,indent=2,ensure_ascii=False)
            self.profile_var.set(name); self.refresh_profiles(); self.write_log(f"Perfil salvo: {name}")
        except Exception as e:self.messagebox.showerror("Perfil",str(e))

    def update_profile(self):
        name=self.profile_var.get()
        if not name or name=="Padrão":return self.save_profile()
        self.profile_name.set(name); self.save_profile()

    def load_profile(self):
        name=self.profile_var.get()
        try:
            path,_=self.profile_path(name)
            with open(path,encoding="utf-8") as f:self.cfg=deep_merge(DEFAULT_CONFIG,json.load(f))
            self.cfg = _sanitize_ffb(self.cfg)
            self.save_config(reload_widgets=True); self.write_log(f"Perfil carregado: {name}")
        except Exception as e:self.messagebox.showerror("Perfil",str(e))

    def delete_profile(self):
        name=self.profile_var.get()
        if not name:return
        if self.messagebox.askyesno("Excluir perfil",f"Excluir '{name}'?"):
            try:os.remove(self.profile_path(name)[0]);self.profile_var.set("");self.refresh_profiles()
            except Exception as e:self.messagebox.showerror("Perfil",str(e))
