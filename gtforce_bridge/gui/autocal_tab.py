"""Aba Autocalibração FFB: executar, revisar, aplicar e zerar."""
from __future__ import annotations

import json
import threading

from ..autocal import FfbAutocal
from ..autocal_profile import apply_autocal_profile, pid_key as make_pid_key, reset_autocal
from ..paths import AUTOCAL_REPORT_PATH
from ..wheel import Wheel, init_sdl


class AutocalTabMixin:
    """Aba Autocalibração FFB: executar, revisar, aplicar e zerar."""

    def build_autocal(self):
        ttk, tk = self.ttk, self.tk
        box = self.section(self.tab_autocal, "AUTOCALIBRAÇÃO DE FORCE FEEDBACK")
        ttk.Label(box, text=("Mede a resposta REAL do volante (sensor hall) a comandos conhecidos e sugere fatores\n"
                             "de correção. Detecta saturação e rejeita testes inválidos. Nada é aplicado sem aprovação.\n\n"
                             "Pré-requisitos: jogos FECHADOS, volante SOLTO, autocenter do driver OFF\n"
                             "(ou HidHide ativo), ponte PARADA."),
                  background="#141d2b", foreground="#cbd5e1", justify="left", wraplength=1000).pack(anchor="w", pady=(0,10))
        self.autocal_btn = ttk.Button(box, text="▶  Rodar autocalibração (~45 s)", style="Accent.TButton", command=self.run_autocal_gui)
        self.autocal_btn.pack(anchor="w", pady=6)
        self.autocal_prog = ttk.Progressbar(box, maximum=100, length=600)
        self.autocal_prog.pack(anchor="w", pady=6)
        self.autocal_status = ttk.Label(box, text="Pronto.", background="#141d2b", foreground="#8d9bb0")
        self.autocal_status.pack(anchor="w")
        self.autocal_suggested = None
        actions = ttk.Frame(self.tab_autocal)
        actions.pack(fill="x", pady=(4, 0))   # logo abaixo do painel: sempre visível sem rolar
        self.reset_autocal_btn = ttk.Button(actions, text="↺  Zerar calibração", command=self.reset_autocal_gui)
        self.reset_autocal_btn.pack(side="left")
        self.apply_btn = ttk.Button(actions, text="✔  Aplicar sugestões", state="disabled", command=self.apply_autocal_gui)
        self.apply_btn.pack(side="right")
        self.autocal_report_box = tk.Text(self.tab_autocal, height=6, wrap="word", state="disabled",
                                          font=("Consolas", 9), bg="#080d14", fg="#cbd5e1", relief="flat")
        self.autocal_report_box.pack(fill="both", expand=True, pady=(10, 6))

    def _append_autocal(self, text):
        self.autocal_report_box.configure(state="normal")
        self.autocal_report_box.insert("end", text + "\n")
        self.autocal_report_box.see("end")
        self.autocal_report_box.configure(state="disabled")

    def run_autocal_gui(self):
        if self.proc and self.proc.poll() is None:
            self.messagebox.showwarning("Autocalibração", "Pare a ponte antes de autocalibrar.")
            return
        if not self.messagebox.askyesno("Autocalibração",
            "Jogos fechados? Volante SOLTO? Autocenter do driver OFF?\n\nO volante vai se mover sozinho por ~45 s. Continuar?"):
            return
        self.autocal_btn.configure(state="disabled")
        self.apply_btn.configure(state="disabled")
        self.autocal_suggested = None
        self.autocal_report_box.configure(state="normal")
        self.autocal_report_box.delete("1.0", "end")
        self.autocal_report_box.configure(state="disabled")
        self.autocal_prog["value"] = 0
        self.autocal_status.configure(text="Iniciando…")

        def worker():
            try:
                sdl2 = init_sdl()
                wheel = Wheel(sdl2, self.cfg["device_match"], self.cfg.get("device_pids"))
                if not wheel.haptic:
                    self.root.after(0, lambda: self._autocal_done(None, None, "Volante sem haptic."))
                    sdl2.SDL_Quit(); return
                def progress(label, frac):
                    self.root.after(0, lambda: self._autocal_progress(label, frac))
                ac = FfbAutocal(sdl2, wheel, self.cfg, self.verbose_var.get(), progress_cb=progress)
                report, suggested = ac.run()
                try:
                    with open(AUTOCAL_REPORT_PATH, "w", encoding="utf-8") as f:
                        json.dump(report, f, indent=2, ensure_ascii=False)
                except OSError:
                    pass
                wheel.close(); sdl2.SDL_Quit()
                self.root.after(0, lambda: self._autocal_done(report, suggested, None))
            except Exception as e:
                self.root.after(0, lambda err=e: self._autocal_done(None, None, f"Erro: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def _autocal_progress(self, label, frac):
        if frac is not None:
            self.autocal_prog["value"] = frac * 100
        self.autocal_status.configure(text=label)

    def _autocal_done(self, report, suggested, error):
        self.autocal_btn.configure(state="normal")
        if error:
            self.autocal_status.configure(text="Falhou.")
            self._append_autocal(error)
            return
        self.autocal_status.configure(text="Concluído.")
        self.autocal_prog["value"] = 100
        self.autocal_suggested = suggested
        try:
            self.autocal_pid = int(((report or {}).get("device") or {}).get("pid", 0))
        except (TypeError, ValueError):
            self.autocal_pid = 0
        self.apply_btn.configure(state="normal" if suggested else "disabled")
        if not report:
            self._append_autocal("(sem relatório)")
            return
        t = report.get("tests", {})
        self._append_autocal("=== MEDIÇÕES ===")
        for k in ("rest","const_pos","const_neg","const_strong","spring_off0","spring_off_pos","spring_off_neg","deadband"):
            d = t.get(k, {})
            if "median" in d:
                sat = " SATURADO" if d.get("saturated") else ""
                self._append_autocal(f"  {k:18s} median={d['median']:+.4f}  span={d.get('span',0):.4f}  n={d.get('n',0)}{sat}")
            elif "min_magnitude" in d:
                status = d.get("status", "")
                extra = (f"  +/-=({d.get('positive_displacement',0):.4f}/"
                         f"{d.get('negative_displacement',0):.4f})  {status}")
                self._append_autocal(f"  {k:18s} min_magnitude={d['min_magnitude']:.3f}  disp={d.get('displacement',0):.4f}{extra}")
        self._append_autocal("")
        self._append_autocal("=== SUGESTÕES (não aplicadas) ===")
        if suggested:
            for k, v in suggested.items():
                if k == "diagnostics":
                    self._append_autocal("  diagnósticos:")
                    for kk, vv in v.items():
                        self._append_autocal(f"    {kk}: {vv}")
                else:
                    self._append_autocal(f"  {k}: {v}")
            if suggested.get("warning"):
                self._append_autocal("")
                reason = (suggested.get("diagnostics", {}) or {}).get("warning_reason", "medição fora do esperado")
                self._append_autocal(f"*** AVISO: {reason}. A decisão de aplicar é sua. ***")
            self._append_autocal("Use 'Aplicar sugestões' para gravar ou 'Zerar calibração' para voltar aos padrões.")

    def reset_autocal_gui(self):
        if self.proc and self.proc.poll() is None:
            self.messagebox.showwarning("Zerar calibração", "Pare a ponte antes de resetar.")
            return
        if not self.messagebox.askyesno("Zerar calibração FFB",
            "Remover os perfis de autocalibração por PID e restaurar os fatores FFB padrão?\n\nIsso não altera a configuração de eixos ou pedais."):
            return
        reset_autocal(self.cfg["ffb"])
        self.save_config()
        self.autocal_suggested = None
        self.apply_btn.configure(state="disabled")
        self.autocal_status.configure(text="Calibração FFB zerada.")
        self._append_autocal("\n[RESET] Perfis por PID removidos e fatores FFB restaurados aos padrões.")
        self.write_log("Autocalibração FFB zerada; perfis por PID removidos.")

    def apply_autocal_gui(self):
        if not self.autocal_suggested:
            return
        if not self.messagebox.askyesno("Aplicar fatores",
            "Aplicar os fatores sugeridos em config.json?"):
            return
        sug = self.autocal_suggested
        # O PID vem do relatório da própria autocal (a telemetria não existe com a ponte parada).
        pid = getattr(self, "autocal_pid", 0)
        if not pid:
            self.messagebox.showerror("Autocalibração", "PID do volante desconhecido; rode a autocalibração novamente.")
            return
        pid_key = make_pid_key(pid)
        apply_autocal_profile(self.cfg["ffb"], pid_key, sug)
        self.save_config()
        self.write_log(f"Autocalibração aplicada (PID {pid_key}).")
        self.apply_btn.configure(state="disabled")
        self.messagebox.showinfo("Autocalibração", "Fatores aplicados em config.json.")
