"""Controle do processo da ponte: iniciar/parar subprocesso, log e fila de saída."""
from __future__ import annotations

import os
import queue
import sys
import subprocess
import threading

from ..paths import MAIN_SCRIPT, STOP_PATH, TELEMETRY_PATH


class ProcessMixin:
    """Controle do processo da ponte: iniciar/parar subprocesso, log e fila de saída."""

    def write_log(self,message):
        self.log.configure(state="normal"); self.log.insert("end",str(message).rstrip()+"\n"); self.log.see("end"); self.log.configure(state="disabled")

    def launch(self,argument):
        if self.proc and self.proc.poll() is None:
            self.write_log("Já existe uma operação em andamento.");return
        if getattr(sys,"frozen",False):
            command=[sys.executable,argument]
        else:
            command=[sys.executable,"-u",MAIN_SCRIPT,argument]
        if argument in ("--run","--ffb-dump"):
            if argument=="--run" and self.verbose_var.get():command.append("--verbose")
            if argument=="--run" and self.noffb_var.get():command.append("--no-ffb")
            for stale in (STOP_PATH,TELEMETRY_PATH):
                try:
                    if os.path.exists(stale):os.remove(stale)
                except OSError:pass
        flags=(getattr(subprocess,"CREATE_NO_WINDOW",0) | getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)) if os.name=="nt" else 0
        try:self.proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,text=True,encoding="utf-8",errors="replace",bufsize=1,creationflags=flags)
        except Exception as e:self.write_log(f"Falha ao iniciar: {e}");return
        self._last_arg = argument; self._user_stopped = False
        self.status_var.set(f"Executando {argument}");self.set_busy(True);self.write_log(f"> {argument} iniciado")
        def reader(proc):
            try:
                for line in proc.stdout:
                    self.output_q.put(line)
            except Exception as e:self.output_q.put(f"\n[leitura] {e}\n")
            finally:self.output_q.put(("finished",proc))
        self.reader_thread=threading.Thread(target=reader,args=(self.proc,),daemon=True);self.reader_thread.start()

    def set_busy(self,busy):
        self.btn_run.configure(state="disabled" if busy else "normal");self.btn_stop.configure(state="normal" if busy else "disabled")
        self.set_run_state("busy" if busy else "idle")

    def drain_output(self):
        chunks=[]; done=[]
        try:
            for _ in range(400):
                item=self.output_q.get_nowait()
                if isinstance(item,tuple) and item[0]=="finished":done.append(item[1])
                else:chunks.append(str(item))
        except queue.Empty:pass
        if chunks:
            self.log.configure(state="normal");self.log.insert("end","".join(chunks))
            extra=int(self.log.index("end-1c").split(".")[0])-1500
            if extra>0:self.log.delete("1.0",f"{extra+1}.0")
            self.log.see("end");self.log.configure(state="disabled")
        for proc in done:
            code=proc.poll();self.write_log(f"> Operação encerrada (código {code}).");self.status_var.set("Pronto" if code==0 else f"Finalizado com código {code}")
            if self.proc is proc:self.proc=None
            hook=getattr(self,"on_process_finished",None)
            if hook:hook(code)
            self.set_busy(False)
        self.root.after(50 if not self.output_q.empty() else 120,self.drain_output)

    def stop_process(self):
        if self.proc and self.proc.poll() is None:
            self._user_stopped=True
            self.write_log("Solicitando encerramento limpo da ponte…")
            try:
                with open(STOP_PATH,"w",encoding="utf-8") as f:f.write("stop")
            except OSError as e:self.write_log(f"Não foi possível sinalizar parada: {e}")

    def on_close(self):
        if hasattr(self,"shutdown_tray"):self.shutdown_tray()
        if self.proc and self.proc.poll() is None:
            try:
                with open(STOP_PATH,"w",encoding="utf-8") as f:f.write("stop")
            except OSError:pass
        self.root.destroy()
