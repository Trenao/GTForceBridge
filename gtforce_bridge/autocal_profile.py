"""Perfis de autocalibração FFB: UMA lista de chaves e UM ponto de aplicação/reset.

Precedência (da menor para a maior):
  DEFAULT_CONFIG < config.json["ffb"] < perfil autocal_by_pid["0xPID"] (aplicado ao iniciar a ponte)
Só chaves MEDIDAS entram no perfil (veja autocal._derive); o resto fica com o valor do usuário.
"""
from __future__ import annotations

from .config import DEFAULT_CONFIG

AUTOCAL_KEYS = ("invert", "center_offset", "min_effective_magnitude",
                "min_effect_mode", "constant_scale")


def pid_key(pid):
    return f"0x{int(pid):04X}"


def profile_for(ffb_cfg, pid):
    return (ffb_cfg.get("autocal_by_pid") or {}).get(pid_key(pid)) or {}


def apply_autocal_profile(ffb_cfg, key, suggestion):
    """Guarda a sugestão em autocal_by_pid[key] e a copia (só chaves medidas) para ffb_cfg."""
    ffb_cfg.setdefault("autocal_by_pid", {})[key] = suggestion
    return overlay_profile(ffb_cfg, suggestion)


def overlay_profile(ffb_cfg, suggestion):
    applied = []
    for k in AUTOCAL_KEYS:
        if k in suggestion:
            ffb_cfg[k] = suggestion[k]
            applied.append(k)
    return applied


def reset_autocal(ffb_cfg):
    for k in AUTOCAL_KEYS:
        ffb_cfg[k] = DEFAULT_CONFIG["ffb"][k]
    ffb_cfg["autocal_by_pid"] = {}
