"""Bandeja do sistema, inicialização com o Windows e instância única.

A bandeja usa pystray + Pillow (opcionais: sem eles a GUI funciona normalmente, só sem bandeja).
Os callbacks do pystray rodam em outra thread; eles apenas colocam um comando numa fila que o Tk lê.
"""
from __future__ import annotations

import os
import queue
import sys

from . import theme as T
from ..paths import BASE_DIR, MAIN_SCRIPT

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_NAME = "GTForceControlCenter"
IS_WINDOWS = os.name == "nt"

try:                                    # opcionais
    import pystray
    from PIL import Image, ImageDraw
except Exception:                       # pragma: no cover - depende do ambiente
    pystray = Image = ImageDraw = None


# ------------------------------------------------------------------ inicialização com o Windows
def autostart_command():
    """Comando gravado no registro: abre a GUI já oculta na bandeja (sem janela de console)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --gui --tray'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    return f'"{exe}" "{MAIN_SCRIPT}" --gui --tray'


def is_autostart():
    if not IS_WINDOWS:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            return bool(winreg.QueryValueEx(k, RUN_NAME)[0])
    except OSError:
        return False


def set_autostart(enabled):
    """Liga/desliga a entrada em HKCU\\...\\Run (não precisa de administrador). Levanta OSError se falhar."""
    if not IS_WINDOWS:
        raise OSError("A inicialização automática só existe no Windows.")
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, RUN_NAME, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(k, RUN_NAME)
            except FileNotFoundError:
                pass


# ------------------------------------------------------------------ instância única
_mutex = None


def acquire_single_instance():
    """True se esta é a única instância da GUI. Fora do Windows sempre True."""
    global _mutex
    if not IS_WINDOWS:
        return True
    import ctypes
    k32 = ctypes.windll.kernel32
    _mutex = k32.CreateMutexW(None, False, "Local\\GTForceControlCenter")
    return k32.GetLastError() != 183          # ERROR_ALREADY_EXISTS


# ------------------------------------------------------------------ ícone
def make_icon(state="idle", size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 64
    d.rounded_rectangle((2 * s, 2 * s, 62 * s, 62 * s), radius=14 * s, fill=T.SIDEBAR, outline=T.BORDER, width=max(1, int(2 * s)))
    d.ellipse((12 * s, 12 * s, 52 * s, 52 * s), outline=T.ACCENT, width=max(2, int(6 * s)))      # aro do volante
    d.ellipse((27 * s, 27 * s, 37 * s, 37 * s), fill=T.ACCENT)                                  # centro
    d.line((32 * s, 37 * s, 32 * s, 52 * s), fill=T.ACCENT, width=max(2, int(5 * s)))
    dot = {"running": T.OK, "busy": T.ACCENT_HI}.get(state, "#6b7a90")
    d.ellipse((42 * s, 42 * s, 60 * s, 60 * s), fill=dot, outline=T.SIDEBAR, width=max(1, int(2 * s)))
    return img


class TrayMixin:
    tray_icon = None
    tray_ok = False

    # ---- ciclo de vida
    def init_tray(self, start_hidden=False):
        self._tray_q = queue.Queue()
        self._tray_hint_shown = False
        self._user_stopped = False
        self._autorun_tries = 0
        if pystray is not None and (IS_WINDOWS or os.environ.get("GTFORCE_TRAY_TEST")):
            try:
                self.tray_icon = pystray.Icon("gtforce", make_icon("idle"), "GT Force Control Center", self._tray_menu())
                self.tray_icon.run_detached()
                self.tray_ok = True
            except Exception as e:
                self.tray_icon = None
                self.write_log(f"Bandeja indisponível: {e}")
        elif IS_WINDOWS:
            self.write_log("Bandeja indisponível: instale com  pip install pystray pillow")
        self.root.bind("<Unmap>", self._on_unmap, add="+")
        self.root.after(150, self._drain_tray)
        if start_hidden:
            if self.tray_ok:
                self.hide_to_tray(notify=False)
            else:
                self.root.deiconify()          # sem bandeja, esconder deixaria o app invisível
        if self.cfg.get("app", {}).get("autorun_bridge"):
            self.root.after(3000, self._autorun_start)

    def shutdown_tray(self):
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
            self.tray_ok = False

    # ---- menu do ícone
    def _tray_menu(self):
        def running(_i=None):
            return bool(self.proc and self.proc.poll() is None)
        item = pystray.MenuItem
        return pystray.Menu(
            item("Abrir painel", lambda *_: self._tray_q.put("show"), default=True),
            pystray.Menu.SEPARATOR,
            item("Iniciar ponte", lambda *_: self._tray_q.put("start"), enabled=lambda _i: not running()),
            item("Parar ponte", lambda *_: self._tray_q.put("stop"), enabled=lambda _i: running()),
            pystray.Menu.SEPARATOR,
            item("Sair", lambda *_: self._tray_q.put("quit")),
        )

    def _drain_tray(self):
        try:
            while True:
                cmd = self._tray_q.get_nowait()
                if cmd == "show": self.show_from_tray()
                elif cmd == "start": self.launch("--run")
                elif cmd == "stop": self.stop_process()
                elif cmd == "quit": self.on_close()
        except queue.Empty:
            pass
        try:
            self.root.after(150, self._drain_tray)
        except Exception:
            pass

    def tray_update(self):
        if self.tray_icon is None:
            return
        state = self._run_state or "idle"
        try:
            self.tray_icon.icon = make_icon(state)
            self.tray_icon.title = {"running": "GT Force — ponte ativa", "busy": "GT Force — executando"}.get(state, "GT Force — parado")
            self.tray_icon.update_menu()
        except Exception:
            pass

    # ---- esconder / mostrar
    def hide_to_tray(self, notify=True):
        if not self.tray_ok:
            self.write_log("Bandeja indisponível (instale pystray e Pillow).")
            return False
        self.root.withdraw()
        if notify and not self._tray_hint_shown:
            self._tray_hint_shown = True
            try:
                self.tray_icon.notify("O painel continua na bandeja. Clique no ícone para abrir.", "GT Force Control Center")
            except Exception:
                pass
        return True

    def show_from_tray(self):
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass

    def _on_unmap(self, e):
        if e.widget is self.root and self.tray_ok and self.cfg.get("app", {}).get("minimize_to_tray", True):
            if self.root.state() == "iconic":
                self.root.after(10, self.hide_to_tray)

    def request_close(self):
        """Botão X: vai para a bandeja (se ligado) ou encerra."""
        if self.tray_ok and self.cfg.get("app", {}).get("close_to_tray", True):
            self.hide_to_tray()
        else:
            self.on_close()

    # ---- iniciar a ponte sozinho (com repetição: no boot o vJoy/USB pode demorar)
    def _autorun_start(self):
        if self.proc and self.proc.poll() is None:
            return
        self.write_log("Início automático da ponte…")
        self.launch("--run")

    def on_process_finished(self, code):
        if (self.cfg.get("app", {}).get("autorun_bridge") and getattr(self, "_last_arg", "") == "--run"
                and code not in (0, None) and not self._user_stopped and self._autorun_tries < 3):
            self._autorun_tries += 1
            self.write_log(f"Ponte encerrou com erro; nova tentativa {self._autorun_tries}/3 em 10 s…")
            self.root.after(10000, self._autorun_start)
