"""Log em arquivo com rotação: duplica tudo que o programa imprime (stdout/stderr) em logs/bridge.log.

Mantém o comportamento atual (a GUI lê o stdout do subprocesso) e acrescenta um histórico em disco,
com data/hora por linha, para diagnosticar problemas depois de uma sessão de jogo.
"""
from __future__ import annotations

import os
import sys
import time
from logging.handlers import RotatingFileHandler
import logging

from .paths import BASE_DIR


class _Tee:
    """Escreve no stream original e, linha a linha, no arquivo de log."""

    def __init__(self, original, logger: logging.Logger, level: int):
        self._orig = original
        self._log = logger
        self._level = level
        self._buf = ""

    def write(self, s):
        try:
            self._orig.write(s)
        except Exception:
            pass
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            line = line.rstrip("\r")
            if line.strip():
                self._log.log(self._level, line)
        return len(s)

    def flush(self):
        try:
            self._orig.flush()
        except Exception:
            pass

    def __getattr__(self, name):          # encoding, isatty, fileno...
        return getattr(self._orig, name)


_installed = False


def resolve_log_path(log_cfg) -> str:
    path = log_cfg.get("file") or "logs/bridge.log"
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


def setup_logging(log_cfg, tag: str = "bridge") -> str | None:
    """Instala o tee de stdout/stderr. Retorna o caminho do arquivo ou None se desativado/falhou."""
    global _installed
    if _installed or not log_cfg.get("enabled", True):
        return None
    path = resolve_log_path(log_cfg)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handler = RotatingFileHandler(
            path, maxBytes=int(float(log_cfg.get("max_mb", 2.0)) * 1024 * 1024),
            backupCount=int(log_cfg.get("backups", 3)), encoding="utf-8")
    except OSError as exc:
        print(f"[log] não foi possível abrir {path}: {exc}")
        return None
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger = logging.getLogger("gtforce_bridge.file")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)
    sys.stdout = _Tee(sys.stdout, logger, logging.INFO)
    sys.stderr = _Tee(sys.stderr, logger, logging.ERROR)
    _installed = True
    logger.info("=== sessão '%s' iniciada (%s) ===", tag, time.strftime("%Y-%m-%d %H:%M:%S"))
    return path
