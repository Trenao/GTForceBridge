"""Aba HidHide: esconder o volante físico dos jogos e registrar a ponte."""
from __future__ import annotations

import json
import os
import sys
import subprocess


class HidHideTabMixin:
    """Aba HidHide: esconder o volante físico dos jogos e registrar a ponte."""

    def find_hidhide_cli(self):
        if os.name!="nt": return None
        candidates=[os.path.join(os.environ.get("ProgramFiles",r"C:\Program Files"),"Nefarius Software Solutions","HidHide","HidHideCLI.exe"),
                    os.path.join(os.environ.get("ProgramFiles",r"C:\Program Files"),"Nefarius Software Solutions","HidHide","x64","HidHideCLI.exe")]
        return next((x for x in candidates if os.path.isfile(x)),None)

    def hidhide(self,*args):
        if not self.hidhide_cli:
            self.messagebox.showerror("HidHide não encontrado","Instale o HidHide oficial."); return ""
        try:
            p=subprocess.run([self.hidhide_cli,*args],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=15)
            out=(p.stdout or "")+(p.stderr or "")
            if p.returncode: self.write_log(f"HidHide retornou {p.returncode}: {out.strip()}")
            return out.strip()
        except Exception as e:
            self.write_log(f"Falha ao executar HidHideCLI: {e}"); return ""

    def build_hidhide(self):
        ttk, tk = self.ttk, self.tk
        box=self.section(self.tab_hide,"ESCOLHA O QUE OCULTAR DOS JOGOS")
        ttk.Label(box,textvariable=self.cloak_var,background="#141d2b",foreground="#ff914d",font=("Segoe UI",11,"bold")).pack(anchor="w",pady=(0,4))
        ttk.Label(box,text="Selecione na lista e use os botões. O vJoy é protegido.",background="#141d2b",foreground="#8d9bb0").pack(anchor="w",pady=(0,6))
        style=ttk.Style()
        style.configure("Hid.Treeview",background="#080d14",fieldbackground="#080d14",foreground="#e8edf5",rowheight=26,borderwidth=0)
        style.configure("Hid.Treeview.Heading",background="#263449",foreground="#e8edf5",font=("Segoe UI",9,"bold"))
        style.map("Hid.Treeview",background=[("selected","#f47721")],foreground=[("selected","#111827")])
        wrap=ttk.Frame(box,style="Card.TFrame"); wrap.pack(fill="both",expand=True)
        self.hid_tree=ttk.Treeview(wrap,columns=("estado","nome","caminho"),show="headings",height=8,selectmode="extended",style="Hid.Treeview")
        for col,txt,w in (("estado","Estado",90),("nome","Dispositivo",250),("caminho","Caminho (instância)",520)):
            self.hid_tree.heading(col,text=txt); self.hid_tree.column(col,width=w,anchor="w")
        self.hid_tree.tag_configure("hidden",foreground="#ff914d")
        self.hid_tree.tag_configure("protected",foreground="#6fcf97")
        sb=ttk.Scrollbar(wrap,orient="vertical",command=self.hid_tree.yview); self.hid_tree.configure(yscrollcommand=sb.set)
        self.hid_tree.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
        row=ttk.Frame(box,style="Card.TFrame"); row.pack(fill="x",pady=8)
        ttk.Button(row,text="Ocultar volante GT Force",style="Accent.TButton",command=self.hide_wheel_auto).pack(side="left",padx=3)
        ttk.Button(row,text="Ocultar selecionados",command=lambda:self.hide_selected(True)).pack(side="left",padx=3)
        ttk.Button(row,text="Mostrar selecionados",command=lambda:self.hide_selected(False)).pack(side="left",padx=3)
        ttk.Button(row,text="Autorizar esta ponte",command=self.register_bridge).pack(side="left",padx=3)
        ttk.Button(row,text="Atualizar lista",command=self.inspect_hidhide).pack(side="left",padx=3)
        row2=ttk.Frame(box,style="Card.TFrame"); row2.pack(fill="x",pady=(0,8))
        ttk.Button(row2,text="Desativar ocultação",command=lambda:self.apply_hidhide(["--cloak-off"])).pack(side="left",padx=3)
        self.hid_apps=tk.StringVar(value="Aplicativos autorizados: —")
        ttk.Label(box,textvariable=self.hid_apps,background="#141d2b",foreground="#8d9bb0",wraplength=1000,justify="left").pack(anchor="w")
        self.hid_devices={}

    @staticmethod
    def _norm_path(p):
        return p.strip().strip('"').upper()

    def parse_hid_devices(self,text):
        found=[]
        try:
            for grp in json.loads(text):
                for d in grp.get("devices",[]):
                    path=d.get("deviceInstancePath","")
                    if path:
                        name=(d.get("product") or grp.get("friendlyName") or path).strip()
                        vendor=(d.get("vendor") or "").strip()
                        found.append((f"{vendor} {name}".strip() if vendor and vendor not in name else name,path))
            return found
        except (ValueError,AttributeError,TypeError):
            pass
        import re
        for m in re.finditer(r'"deviceInstancePath"\s*:\s*"((?:[^"\\]|\\.)*)"',text):
            path=m.group(1).replace("\\\\","\\")
            found.append((path,path))
        return found

    def inspect_hidhide(self):
        if not self.hidhide_cli:
            self.refresh_hidhide_state(); return
        import re
        gaming=self.parse_hid_devices(self.hidhide("--dev-gaming"))
        hidden_out=self.hidhide("--dev-list")
        hidden={self._norm_path(x) for x in re.findall(r'"([^"]+)"',hidden_out)}
        apps=re.findall(r'"([^"]+)"',self.hidhide("--app-list"))
        self.hid_apps.set("Aplicativos autorizados: "+(" | ".join(os.path.basename(a) for a in apps) if apps else "nenhum"))
        self.hid_devices={}
        for item in self.hid_tree.get_children(): self.hid_tree.delete(item)
        seen=set()
        for name,path in gaming:
            key=self._norm_path(path); seen.add(key)
            protected=("VJOY" in name.upper()) or key.startswith("HID\\HIDCLASS")
            state="Protegido" if protected else ("Oculto" if key in hidden else "Visível")
            tag="protected" if protected else ("hidden" if key in hidden else "")
            iid=self.hid_tree.insert("", "end", values=(state,name,path),tags=(tag,) if tag else ())
            self.hid_devices[iid]=(path,protected)
        for key in sorted(hidden-seen):
            real=next((x for x in re.findall(r'"([^"]+)"',hidden_out) if self._norm_path(x)==key),key)
            iid=self.hid_tree.insert("", "end", values=("Oculto","(outro / pai USB)",real),tags=("hidden",))
            self.hid_devices[iid]=(real,False)
        self.refresh_hidhide_state()

    def refresh_hidhide_state(self):
        if self.hidhide_cli:
            state=self.hidhide("--cloak-state")
            self.cloak_var.set("HidHide: ocultação ATIVA" if "--cloak-on" in state else "HidHide: ocultação desativada / indisponível")
        else:
            self.cloak_var.set("HidHide não encontrado")

    def apply_hidhide(self,args):
        out=self.hidhide(*args)
        self.write_log("HidHide: "+(out or "comando enviado")); self.inspect_hidhide()

    def register_bridge(self):
        self.apply_hidhide(["--app-reg",os.path.abspath(sys.executable)])

    def hide_selected(self,hide):
        paths=[self.hid_devices[i][0] for i in self.hid_tree.selection() if i in self.hid_devices and not self.hid_devices[i][1]]
        if not paths:
            self.messagebox.showinfo("HidHide","Selecione um ou mais dispositivos (vJoy é protegido)."); return
        if hide:
            if not self.messagebox.askyesno("Confirmar",f"Ocultar {len(paths)} dispositivo(s)?"): return
            args=["--app-reg",os.path.abspath(sys.executable),"--inv-off"]
            for p in paths: args+=["--dev-hide",p]
            args.append("--cloak-on")
            self.apply_hidhide(args)
        else:
            args=[]
            for p in paths: args+=["--dev-unhide",p]
            self.apply_hidhide(args)

    def hide_wheel_auto(self):
        match=str(self.cfg.get("device_match","")).lower()
        target=[i for i,(path,prot) in self.hid_devices.items()
                if not prot and path.upper().startswith("HID\\") and match and match in str(self.hid_tree.set(i,"nome")).lower()]
        if not target:
            self.messagebox.showinfo("HidHide",f"Nenhum HID com '{match}'. Atualize a lista ou selecione manualmente."); return
        self.hid_tree.selection_set(target)
        self.hide_selected(True)
