"""Janela principal da GUI (GT Force Control Center) e launch_gui().

Layout: barra superior (estado, perfil, iniciar/parar) + menu lateral + página ativa + gaveta de log.
Responsivo: >=1000 px largo; 700-999 compacto; <700 mínimo (menu lateral vira lista suspensa).
"""
from __future__ import annotations

import json
import queue

from ..config import load_config
from ..paths import CONFIG_PATH
from . import theme as T
from .dashboard_tab import DashboardMixin
from .monitor_tab import MonitorTabMixin
from .calibration_tab import CalibrationTabMixin
from .mapping_tab import MappingTabMixin
from .ffb_tab import FfbTabMixin
from .autocal_tab import AutocalTabMixin
from .hidhide_tab import HidHideTabMixin
from .profiles_tab import ProfilesTabMixin
from .process_ctl import ProcessMixin
from .settings_tab import SettingsMixin
from . import tray as _tray

PAGES = [("tab_dash", "Painel"), ("tab_monitor", "Monitor"), ("tab_cal", "Calibração"),
         ("tab_range", "Alcance dos eixos"), ("tab_map", "Mapeamento"), ("tab_ffb", "Force Feedback"),
         ("tab_autocal", "Autocalibração FFB"), ("tab_hide", "HidHide"), ("tab_profiles", "Perfis"), ("tab_settings", "Sistema")]
TOOLS = [("Detectar volante", "--list"), ("Teste FFB", "--ffb-test"), ("Capturar FFB do jogo", "--ffb-dump")]
STATE_COLOR = {"idle": "#6b7a90", "running": T.OK, "busy": T.ACCENT}


class BridgeGUI(DashboardMixin, MonitorTabMixin, CalibrationTabMixin, MappingTabMixin, FfbTabMixin, AutocalTabMixin,
                HidHideTabMixin, ProfilesTabMixin, SettingsMixin, _tray.TrayMixin, ProcessMixin):
    """Janela principal: monta o layout e herda o comportamento de cada página."""

    def __init__(self, root, start_hidden=False):
        import tkinter as tk
        from tkinter import ttk, messagebox, simpledialog
        self.tk, self.ttk = tk, ttk
        self.messagebox, self.simpledialog = messagebox, simpledialog
        self.root = root
        self.proc = None
        self.output_q = queue.Queue()
        self.reader_thread = None
        self.cfg = load_config()
        self.hidhide_cli = self.find_hidhide_cli()
        self.profile_var = tk.StringVar(value="Padrão")
        self.verbose_var = tk.BooleanVar(value=False)
        self.noffb_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Pronto para iniciar")
        self.cloak_var = tk.StringVar(value="HidHide: verificando…")
        self.page_title = tk.StringVar(value="Painel")
        self.mode, self._layout_key, self.compact = "wide", None, False
        self.pages, self.page_fit, self.nav_items, self.current_page = {}, {}, {}, None
        self._run_state = None
        self.root.title("GT Force Control Center")
        T.apply_theme(root, ttk)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(1240, sw - 40), min(800, sh - 90)          # nunca maior que a tela
        self.root.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//3)}")
        self.root.minsize(min(560, w), min(460, h))
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        if start_hidden:
            self.root.withdraw()
        root.columnconfigure(0, weight=1); root.rowconfigure(2, weight=1)

        self._build_topbar()
        self._build_navstrip()
        self._build_body()
        self._build_log()
        for attr, _label in PAGES:
            setattr(self, attr, self._scroll_page(attr))
        self.build_dashboard(); self.build_monitor(); self.build_calibration(); self.build_range(); self.build_mapping()
        self.build_ffb(); self.build_autocal(); self.build_hidhide(); self.build_profiles()
        self.init_tray(start_hidden)
        self.build_settings()
        self.show_page("tab_dash")

        root.bind("<Configure>", self._on_root_configure, add="+")
        root.bind_all("<MouseWheel>", self._wheel); root.bind_all("<Button-4>", self._wheel); root.bind_all("<Button-5>", self._wheel)
        for i, (attr, _l) in enumerate(PAGES[:9], 1):
            root.bind(f"<Control-Key-{i}>", lambda _e, a=attr: self.show_page(a))
        self.root.after(30, self.apply_layout)
        self.root.after(100, self.drain_output); self.root.after(100, self.poll_telemetry); self.root.after(1800, self.inspect_hidhide)
        self.write_log("Painel carregado.")
        if not self.hidhide_cli: self.write_log("HidHideCLI não encontrado.")

    # ------------------------------------------------------------------ construção
    def _build_topbar(self):
        tk, ttk = self.tk, self.ttk
        top = ttk.Frame(self.root, style="Top.TFrame", padding=(16, 9)); top.grid(row=0, column=0, sticky="ew")
        self.topbar = top
        self.btn_run = ttk.Button(top, text="INICIAR PONTE", style="Accent.TButton", command=lambda: self.launch("--run"))
        self.btn_run.pack(side="right")
        self.btn_stop = ttk.Button(top, text="PARAR", command=self.stop_process, state="disabled")
        self.btn_stop.pack(side="right", padx=(0, 8))
        self.profile_box = ttk.Combobox(top, textvariable=self.profile_var, state="readonly", width=14, values=self.profile_names())
        self.profile_box.pack(side="right", padx=(0, 14))
        self.profile_lbl = ttk.Label(top, text="Perfil", style="TopMuted.TLabel"); self.profile_lbl.pack(side="right", padx=(0, 6))
        self.profile_box.bind("<<ComboboxSelected>>", lambda e: self.load_profile())
        self.tools_btn = tk.Menubutton(top, text="Ferramentas ▾", bg=T.TRACK, fg=T.TEXT, activebackground="#344761",
                                       activeforeground=T.TEXT, relief="flat", bd=0, padx=10, pady=6, font=(T.FONT, 9, "bold"))
        self.tools_menu = tk.Menu(self.tools_btn, tearoff=0)
        for label, arg in TOOLS:
            self.tools_menu.add_command(label=label, command=lambda a=arg: self.launch(a))
        self.tools_menu.add_command(label="Ocultar na bandeja", command=self.hide_to_tray)
        self.tools_menu.add_separator()
        self.tools_menu.add_checkbutton(label="Log FFB detalhado", variable=self.verbose_var)
        self.tools_menu.add_checkbutton(label="Sem FFB", variable=self.noffb_var)
        self.tools_btn.configure(menu=self.tools_menu)
        self.title_lbl = ttk.Label(top, textvariable=self.page_title, style="Top.TLabel"); self.title_lbl.pack(side="left")
        self.dot = tk.Canvas(top, width=10, height=10, bg=T.SIDEBAR, highlightthickness=0)
        self.dot.pack(side="left", padx=(14, 6))
        self._dot_id = self.dot.create_oval(1, 1, 9, 9, fill=STATE_COLOR["idle"], outline="")
        self.status_lbl = ttk.Label(top, textvariable=self.status_var, style="TopMuted.TLabel"); self.status_lbl.pack(side="left")

    def _build_navstrip(self):
        ttk = self.ttk
        self.navstrip = ttk.Frame(self.root, style="Side.TFrame", padding=(16, 0, 16, 8))   # só no modo mínimo
        self.nav_combo = ttk.Combobox(self.navstrip, state="readonly", values=[l for _a, l in PAGES])
        self.nav_combo.pack(fill="x")
        self.nav_combo.bind("<<ComboboxSelected>>", lambda e: self.show_page(PAGES[self.nav_combo.current()][0]))

    def _build_body(self):
        tk, ttk = self.tk, self.ttk
        body = ttk.Frame(self.root); body.grid(row=2, column=0, sticky="nsew")
        body.columnconfigure(1, weight=1); body.rowconfigure(0, weight=1)
        self.body = body
        side = ttk.Frame(body, style="Side.TFrame"); side.grid(row=0, column=0, sticky="ns")
        self.sidebar = side
        brand = ttk.Frame(side, style="Side.TFrame", padding=(16, 16, 16, 10)); brand.pack(fill="x")
        tk.Label(brand, text="GT FORCE", bg=T.SIDEBAR, fg="#f5f7fb", font=(T.FONT, 11, "bold"), anchor="w").pack(fill="x")
        tk.Label(brand, text="CONTROL CENTER", bg=T.SIDEBAR, fg=T.MUTED, font=(T.FONT, 8), anchor="w").pack(fill="x")
        navbox = ttk.Frame(side, style="Side.TFrame", padding=(8, 4)); navbox.pack(fill="x")
        for attr, label in PAGES:
            self._make_nav(navbox, attr, label)
        self.side_tools = ttk.Frame(side, style="Side.TFrame", padding=(8, 14, 8, 8))
        tk.Label(self.side_tools, text="FERRAMENTAS", bg=T.SIDEBAR, fg=T.MUTED, font=(T.FONT, 8, "bold"), anchor="w",
                 padx=10).pack(fill="x", pady=(0, 4))
        for label, arg in TOOLS:
            self._make_link(self.side_tools, label, lambda a=arg: self.launch(a))
        self._make_link(self.side_tools, "Ocultar na bandeja", self.hide_to_tray)
        ttk.Checkbutton(self.side_tools, text="Log FFB detalhado", variable=self.verbose_var, style="Side.TCheckbutton").pack(anchor="w", padx=10, pady=(10, 2))
        ttk.Checkbutton(self.side_tools, text="Sem FFB", variable=self.noffb_var, style="Side.TCheckbutton").pack(anchor="w", padx=10)
        self.content = ttk.Frame(body, padding=(14, 14, 14, 6)); self.content.grid(row=0, column=1, sticky="nsew")

    def _make_nav(self, parent, attr, label):
        tk = self.tk
        row = tk.Frame(parent, bg=T.SIDEBAR, cursor="hand2")
        row.pack(fill="x", pady=1)
        bar = tk.Frame(row, bg=T.SIDEBAR, width=3); bar.pack(side="left", fill="y")
        lbl = tk.Label(row, text=label, bg=T.SIDEBAR, fg=T.MUTED, font=(T.FONT, 10), anchor="w", padx=14, pady=8)
        lbl.pack(side="left", fill="x", expand=True)
        item = {"row": row, "bar": bar, "lbl": lbl, "active": False}
        self.nav_items[attr] = item
        def paint(hover=False):
            bg = T.CARD if item["active"] else ("#101929" if hover else T.SIDEBAR)
            row.configure(bg=bg); lbl.configure(bg=bg, fg=T.ACCENT_HI if item["active"] else (T.TEXT if hover else T.MUTED))
            bar.configure(bg=T.ACCENT if item["active"] else bg)
        item["paint"] = paint
        for w in (row, lbl):
            w.bind("<Button-1>", lambda _e, a=attr: self.show_page(a))
            w.bind("<Enter>", lambda _e: paint(True)); w.bind("<Leave>", lambda _e: paint(False))

    def _make_link(self, parent, text, command):
        tk = self.tk
        lbl = tk.Label(parent, text=text, bg=T.SIDEBAR, fg=T.TEXT, font=(T.FONT, 10), anchor="w", padx=10, pady=6, cursor="hand2")
        lbl.pack(fill="x")
        lbl.bind("<Button-1>", lambda _e: command())
        lbl.bind("<Enter>", lambda _e: lbl.configure(fg=T.ACCENT_HI)); lbl.bind("<Leave>", lambda _e: lbl.configure(fg=T.TEXT))
        return lbl

    def _build_log(self):
        tk, ttk = self.tk, self.ttk
        wrap = ttk.Frame(self.root, padding=(14, 6, 14, 12)); wrap.grid(row=3, column=0, sticky="ew")
        self.logwrap = wrap
        head = ttk.Frame(wrap); head.pack(fill="x", pady=(0, 4))
        tk.Label(head, text="LOG DO SISTEMA", bg=T.BG, fg=T.MUTED, font=(T.FONT, 8, "bold")).pack(side="left")
        self.log_toggle = self._head_link(head, "recolher", self.toggle_log); self.log_toggle.pack(side="right", padx=(14, 0))
        self._head_link(head, "limpar", self.clear_log).pack(side="right")
        self.log_body = ttk.Frame(wrap); self.log_body.pack(fill="x")
        self.log = tk.Text(self.log_body, height=4, wrap="word", state="disabled", font=(T.MONO, 9), bg="#080d14", fg="#cbd5e1",
                           insertbackground="#fff", relief="flat", highlightthickness=1, highlightbackground=T.BORDER,
                           highlightcolor=T.BORDER, padx=8, pady=6)
        sb = ttk.Scrollbar(self.log_body, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self.log.pack(side="left", fill="both", expand=True)

    def _head_link(self, parent, text, command):
        lbl = self.tk.Label(parent, text=text, bg=T.BG, fg=T.MUTED, font=(T.FONT, 9), cursor="hand2")
        lbl.bind("<Button-1>", lambda _e: command())
        lbl.bind("<Enter>", lambda _e: lbl.configure(fg=T.ACCENT_HI)); lbl.bind("<Leave>", lambda _e: lbl.configure(fg=T.MUTED))
        return lbl

    def toggle_log(self):
        if self.log_body.winfo_ismapped():
            self.log_body.pack_forget(); self.log_toggle.configure(text="expandir")
        else:
            self.log_body.pack(fill="x"); self.log_toggle.configure(text="recolher")

    def clear_log(self):
        self.log.configure(state="normal"); self.log.delete("1.0", "end"); self.log.configure(state="disabled")

    # ------------------------------------------------------------------ páginas
    def _scroll_page(self, attr):
        """Página rolável: a barra só aparece quando o conteúdo é maior que a janela."""
        tk, ttk = self.tk, self.ttk
        outer = ttk.Frame(self.content)
        canvas = tk.Canvas(outer, highlightthickness=0, bg=T.BG, bd=0)
        bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas, padding=(0, 0, 6, 8))
        win = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=bar.set)
        canvas.pack(side="left", fill="both", expand=True)
        size = {"h": 1}
        def fit(e=None):
            if e is not None and e.widget is canvas:
                size["h"] = e.height                       # altura real vem só do evento do canvas (sem valores antigos)
            ch, need_h = size["h"], inner.winfo_reqheight()
            total = max(ch, need_h) if attr == "tab_dash" else need_h
            canvas.itemconfigure(win, width=canvas.winfo_width(), height=total)
            canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), total))
            need = need_h > ch
            if need and not bar.winfo_ismapped():
                bar.pack(side="right", fill="y")
            elif not need and bar.winfo_ismapped():
                bar.pack_forget()
        canvas.bind("<Configure>", fit); inner.bind("<Configure>", fit)
        self.pages[attr] = (outer, canvas, bar)
        self.page_fit[attr] = fit
        return inner

    def _wheel(self, e):
        cur = self.pages.get(self.current_page)
        if not cur:
            return
        w = e.widget
        if isinstance(w, (self.tk.Text, self.tk.Listbox, self.ttk.Treeview)):
            return
        _o, canvas, bar = cur
        if bar.winfo_ismapped():
            up = e.delta > 0 or getattr(e, "num", 0) == 4
            canvas.yview_scroll(-3 if up else 3, "units")

    def show_page(self, attr):
        if attr not in self.pages:
            return
        if self.current_page:
            self.pages[self.current_page][0].pack_forget()
            self.nav_items[self.current_page]["active"] = False; self.nav_items[self.current_page]["paint"]()
        self.current_page = attr
        self.pages[attr][0].pack(fill="both", expand=True)
        self.nav_items[attr]["active"] = True; self.nav_items[attr]["paint"]()
        label = dict(PAGES)[attr]
        self.page_title.set(label)
        self.nav_combo.set(label)
        self.pages[attr][1].yview_moveto(0)

    # ------------------------------------------------------------------ responsividade
    def _on_root_configure(self, e):
        if e.widget is self.root:
            if getattr(self, "_layout_job", None):
                self.root.after_cancel(self._layout_job)
            self._layout_job = self.root.after(60, self.apply_layout)

    def apply_layout(self):
        self._layout_job = None
        w, h = self.root.winfo_width(), self.root.winfo_height()
        mode = "wide" if w >= 1000 else "compact" if w >= 700 else "tiny"
        tools_in_menu = mode == "tiny" or h < 720
        key = (mode, tools_in_menu)
        if key == self._layout_key:
            return
        self._layout_key = key
        self.mode, self.compact = mode, mode != "wide"
        # menu lateral: visível em largo/compacto; no mínimo vira lista suspensa
        if mode == "tiny":
            self.sidebar.grid_remove(); self.navstrip.grid(row=1, column=0, sticky="ew"); self.title_lbl.pack_forget()
        else:
            self.navstrip.grid_remove(); self.sidebar.grid()
            if not self.title_lbl.winfo_ismapped():
                self.title_lbl.pack(side="left", before=self.dot)
        if mode == "tiny":                          # topo enxuto: só o ponto de estado
            self.status_lbl.pack_forget()
        elif not self.status_lbl.winfo_ismapped():
            self.status_lbl.pack(side="left", after=self.dot)
        for wdg in (self.btn_run, self.btn_stop, self.profile_box, self.profile_lbl, self.tools_btn):
            wdg.pack_forget()                       # reempilha o lado direito na ordem certa
        self.btn_run.pack(side="right"); self.btn_stop.pack(side="right", padx=(0, 8))
        self.profile_box.pack(side="right", padx=(0, 14 if mode != "tiny" else 8))
        if mode != "tiny":
            self.profile_lbl.pack(side="right", padx=(0, 6))
        if tools_in_menu:
            self.tools_btn.pack(side="right", padx=(0, 10))
        small = mode == "compact"
        for it in self.nav_items.values():
            it["lbl"].configure(font=(T.FONT, 9 if small else 10), padx=10 if small else 14, pady=6 if (small or tools_in_menu) else 8)
        # ferramentas: no menu lateral quando há altura; senão, menu suspenso na barra superior
        if tools_in_menu:
            self.side_tools.pack_forget()
        else:
            self.side_tools.pack(fill="x", side="bottom")
        self.profile_box.configure(width=10 if mode != "wide" else 14)
        self.log.configure(height=3 if (h < 620 or mode == "tiny") else 4)

    # ------------------------------------------------------------------ estado
    def set_run_state(self, state):
        if state == self._run_state:
            return
        self._run_state = state
        self.dot.itemconfigure(self._dot_id, fill=STATE_COLOR.get(state, STATE_COLOR["idle"]))
        self.tray_update()

    def section(self, parent, title):
        f = self.ttk.Frame(parent, style="Card.TFrame", padding=14); f.pack(fill="x", pady=(0, 10))
        self.ttk.Label(f, text=title, style="Section.TLabel").pack(anchor="w", pady=(0, 8)); return f

    def save_config(self,reload_widgets=False):
        try:
            with open(CONFIG_PATH,"w",encoding="utf-8") as f:json.dump(self.cfg,f,indent=2,ensure_ascii=False)
            self.write_log("Configuração salva em config.json.")
            if reload_widgets:
                for sec,vals in self.cal_vars.items():
                    for key,(var,label) in vals.items():var.set(float(self.cfg[sec].get(key,0)));label.configure(text=f"{var.get():.2f}")
                for key in ("steering","pedals","brake"):self.map_vars[key].set(self.cfg["axes"][key])
                self.pedals_mode.set(self.cfg["pedals_mode"])
                self.refresh_cal_labels()
                for key in ("steering","throttle","brake"):self.map_vars["vjoy_"+key].set(self.cfg["vjoy_axes"][key])
        except Exception as e:self.messagebox.showerror("Configuração",str(e))


def launch_gui(start_hidden=False):
    import tkinter as tk
    if not _tray.acquire_single_instance():          # já aberta (provavelmente na bandeja)
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showinfo("GT Force Control Center", "O painel já está em execução (veja o ícone na bandeja do sistema).")
        r.destroy(); return
    root = tk.Tk()
    BridgeGUI(root, start_hidden=start_hidden)
    root.mainloop()
