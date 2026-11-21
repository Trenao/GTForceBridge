"""Página Sistema: bandeja do sistema e inicialização com o Windows."""
from __future__ import annotations

from . import theme as T
from . import tray


class SettingsMixin:
    def build_settings(self):
        tk, ttk = self.tk, self.ttk
        app = self.cfg.setdefault("app", {})
        box = self.section(self.tab_settings, "BANDEJA DO SISTEMA")
        self.app_vars = {
            "minimize_to_tray": tk.BooleanVar(value=bool(app.get("minimize_to_tray", True))),
            "close_to_tray": tk.BooleanVar(value=bool(app.get("close_to_tray", True))),
            "autorun_bridge": tk.BooleanVar(value=bool(app.get("autorun_bridge", False))),
        }
        ttk.Checkbutton(box, text="Minimizar para a bandeja", variable=self.app_vars["minimize_to_tray"],
                        command=self.save_app_options).pack(anchor="w", pady=3)
        ttk.Checkbutton(box, text="Botão fechar (X) envia para a bandeja  (para sair de verdade: menu do ícone da bandeja, Sair)",
                        variable=self.app_vars["close_to_tray"], command=self.save_app_options).pack(anchor="w", pady=3)
        row = ttk.Frame(box, style="Card.TFrame"); row.pack(fill="x", pady=(8, 0))
        ttk.Button(row, text="Ocultar na bandeja agora", command=self.hide_to_tray).pack(side="left")
        self.tray_status = ttk.Label(row, text="", background=T.CARD, foreground=T.MUTED); self.tray_status.pack(side="left", padx=12)

        box2 = self.section(self.tab_settings, "INICIALIZAÇÃO")
        self.autostart_var = tk.BooleanVar(value=tray.is_autostart())
        self.autostart_chk = ttk.Checkbutton(box2, text="Iniciar com o Windows (abre minimizado na bandeja)",
                                             variable=self.autostart_var, command=self.toggle_autostart)
        self.autostart_chk.pack(anchor="w", pady=3)
        ttk.Checkbutton(box2, text="Iniciar a ponte automaticamente ao abrir (tenta de novo até 3x se o vJoy/volante ainda não estiver pronto)",
                        variable=self.app_vars["autorun_bridge"], command=self.save_app_options).pack(anchor="w", pady=3)
        self.autostart_note = ttk.Label(box2, text="", background=T.CARD, foreground=T.MUTED, wraplength=760, justify="left")
        self.autostart_note.pack(anchor="w", pady=(6, 0))
        self.refresh_settings_notes()

    def refresh_settings_notes(self):
        self.tray_status.configure(text="Bandeja ativa." if self.tray_ok else
                                   "Bandeja indisponível — instale:  pip install pystray pillow  (Windows).")
        if not tray.IS_WINDOWS:
            self.autostart_chk.state(["disabled"])
            self.autostart_note.configure(text="A inicialização automática só funciona no Windows.")
        else:
            self.autostart_note.configure(text="Grava uma entrada em HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run "
                                               "(sem precisar de administrador). Desmarcar remove a entrada.")

    def save_app_options(self):
        app = self.cfg.setdefault("app", {})
        for k, v in self.app_vars.items():
            app[k] = bool(v.get())
        self.save_config()

    def toggle_autostart(self):
        want = bool(self.autostart_var.get())
        try:
            tray.set_autostart(want)
            self.write_log("Inicialização com o Windows " + ("ativada." if want else "desativada."))
        except OSError as e:
            self.autostart_var.set(not want)
            self.messagebox.showerror("Inicialização", str(e))
