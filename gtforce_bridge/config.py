"""Configuração: valores padrão, mescla com o config.json do usuário e saneamento defensivo."""
from __future__ import annotations

import json
import os

from .paths import CONFIG_PATH


DEFAULT_CONFIG = {
    "cfg_version": 2,   # 2 (v0.9.4): polar_zero passou a "north"; configs antigas com "east" são migradas uma vez
    "device_match": "Formula Force",
    "device_pids": [0xC291, 0xC293, 0xC294, 0xC298, 0xCA03, 0xCA04, 0xC299, 0xC29B],
    "vjoy_device_id": 1,
    "vjoy_dll": r"C:\Program Files\vJoy\x64\vJoyInterface.dll",
    "loop_hz": 500,
    "app": {                         # comportamento da janela (GUI)
        "minimize_to_tray": True,    # botão minimizar envia para a bandeja
        "close_to_tray": True,       # botão X envia para a bandeja (Sair pelo menu do ícone)
        "autorun_bridge": False,     # inicia a ponte sozinho ao abrir a GUI
    },
    "high_priority": False,          # eleva a prioridade do processo (opcional)
    "axes": {"steering": 0, "pedals": 1, "brake": 2},
    "pedals_mode": "separate",
    "vjoy_axes": {"steering": "X", "throttle": "RZ", "brake": "SL0"},
    "steering": {"deadzone": 0.0, "expo": 0.25, "gain": 1.0, "invert": False},
    "throttle": {"deadzone": 0.02, "expo": 0.0, "gain": 1.0, "invert": False},
    "brake": {"deadzone": 0.02, "expo": 0.0, "gain": 1.0, "invert": False},
    "calibration": {
        "steering": {"min": -1.0, "center": 0.0, "max": 1.0},
        "throttle": {"min": -1.0, "max": 1.0},
        "brake": {"min": -1.0, "max": 1.0}
    },
    "buttons_map_all": True,
    # Saídas dos controles. vJoy = jogo com FFB. Teclado e Xbox vêm DESLIGADOS (ligue e salve:
    # vale na hora). Fontes: steering+ steering- throttle brake button:N  (ver mapping.py)
    "outputs": {
        "vjoy": {"enabled": True},
        "keyboard": {
            "enabled": False,
            "bindings": [
                {"source": "steering-", "key": "left", "on": 0.35, "off": 0.25},
                {"source": "steering+", "key": "right", "on": 0.35, "off": 0.25},
                {"source": "throttle", "key": "up", "on": 0.30, "off": 0.20},
                {"source": "brake", "key": "down", "on": 0.30, "off": 0.20},
                {"source": "button:1", "key": "space"}
            ]
        },
        "xbox": {
            "enabled": False,
            # botão físico (1 = primeiro) -> botão do controle; "" = sem mapeamento
            "buttons": {"1": "A", "2": "B", "3": "X", "4": "Y", "5": "LB", "6": "RB", "7": "BACK", "8": "START"}
        }
    },
    "ffb": {
        "enabled": True,
        "master_gain": 1.0,
        "constant_scale": 1.0,
        "condition_scale": 1.0,
        "periodic_scale": 1.0,
        # "steering" = SDL_HAPTIC_STEERING_AXIS (atual). "cartesian" = direção (1,0) em 2 eixos,
        # como o SDK da Logitech faz (o driver do GT Force anuncia 2 eixos com FF).
        "direction_mode": "steering",
        # 0 = desligado. >0 = período mínimo (ms) dos efeitos periódicos (evita "trepidação").
        "periodic_min_period_ms": 0,
        "ramp_scale": 1.0,
        "invert": False,
        "center_offset": 0.0,
        "min_effective_magnitude": 0.0,
        "min_effect_mode": "stretch",
        # suavização / taxa (o GT Force é USB 1.1: poucas atualizações por segundo)
        "update_hz": 100,            # máx. de atualizações/s por efeito (0 = sem limite)
        "slew_per_sec": 0.0,         # força constante: variação máx. (fração da escala/s); 0 = desligado
        "const_deadzone_pct": 0.0,   # ignora força constante abaixo de X% (ruído com carro parado)
        "magnitude_scale": 0,        # 0 = automático (10000 ou 32767); 255 etc. força uma escala
        "disable_autocenter": True,
        # Duração/atraso/loops do jogo (PID 1.0 / vjoyinterface.h): efeito com duração finita para sozinho.
        "honor_duration": True,
        # Zero da direção polar: "north" = convenção do DirectInput (0° = norte, 90° = leste = +X, 270° = -X;
        # componente X = sen) — PADRÃO desde a v0.9.4: o Windows manda 89° (DirectInput 9000) e o FH4 usa 90°/270°
        # para o lado da força. "east" = ângulo a partir de +X (até a v0.9.3): 90° e 270° viram "ambíguos" e
        # fixam o sinal em +1 => o volante pesa sempre para o mesmo lado.
        "polar_zero": "north",
        "autocal_by_pid": {}
    },
    # log em arquivo (cópia de tudo que a ponte imprime), com rotação
    "logging": {"enabled": True, "file": "logs/bridge.log", "max_mb": 2.0, "backups": 3}
}


# Limites defensivos para rejeitar autocal inválida vinda de configs antigos.
AUTOCAL_MAX_PLAUSIBLE_CONST_SCALE = 1.5
AUTOCAL_MAX_PLAUSIBLE_CENTER_OFFSET = 0.05


# Subárvores de formato livre (não geram aviso de chave desconhecida).
_FREE_FORM = {"autocal_by_pid", "buttons"}


def unknown_keys(user, defaults=None, prefix=""):
    """Chaves do config.json do usuário que o programa não reconhece (ficam ignoradas).

    Típico de configs de versões antigas (ex.: 'wheel', 'vjoy', 'ffb.constant_gain')."""
    defaults = DEFAULT_CONFIG if defaults is None else defaults
    out = []
    for k, v in (user or {}).items():
        if k not in defaults:
            out.append(prefix + k)
        elif k not in _FREE_FORM and isinstance(v, dict) and isinstance(defaults[k], dict):
            out += unknown_keys(v, defaults[k], prefix + k + ".")
    return out


def deep_merge(base, extra):
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def clamp_num(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def _sanitize_ffb(cfg):
    """Saneia apenas fatores globais fora de limites absurdos.

    Resultados de autocalibração por PID são sugestões escolhidas pelo usuário;
    medições saturadas geram aviso, não bloqueio automático.
    """
    ffb = cfg.setdefault("ffb", {})
    rejected = []

    cs = float(ffb.get("constant_scale", 1.0))
    if cs > AUTOCAL_MAX_PLAUSIBLE_CONST_SCALE:
        rejected.append(f"constant_scale={cs} (>{AUTOCAL_MAX_PLAUSIBLE_CONST_SCALE})")
        ffb["constant_scale"] = 1.0

    co = float(ffb.get("center_offset", 0.0))
    if abs(co) > AUTOCAL_MAX_PLAUSIBLE_CENTER_OFFSET:
        rejected.append(f"center_offset={co} (|.|>{AUTOCAL_MAX_PLAUSIBLE_CENTER_OFFSET})")
        ffb["center_offset"] = 0.0

    def _num(key, lo, hi, default):
        try:
            v = float(ffb.get(key, default))
        except (TypeError, ValueError):
            v = default
        v = clamp_num(v, lo, hi)
        if v != ffb.get(key):
            ffb[key] = v
        return v

    _num("update_hz", 0.0, 1000.0, 100.0)
    _num("slew_per_sec", 0.0, 100.0, 0.0)
    _num("const_deadzone_pct", 0.0, 50.0, 0.0)
    _num("magnitude_scale", 0.0, 65535.0, 0.0)
    for key, allowed, default in (("polar_zero", ("east", "north"), "north"),
                                  ("direction_mode", ("steering", "cartesian"), "steering")):
        if ffb.get(key) not in allowed:
            rejected.append(f"{key}={ffb.get(key)!r} (válidos: {', '.join(allowed)})")
            ffb[key] = default

    # Perfis por PID são mantidos mesmo quando medições anteriores receberam
    # aviso de saturação: a decisão de usar/aplicar pertence ao usuário.
    by_pid = ffb.get("autocal_by_pid") or {}
    by_pid.pop("unknown", None)
    ffb["autocal_by_pid"] = by_pid

    if rejected:
        print("[config] saneamento defensivo:")
        for r in rejected:
            print("  -", r)
    return cfg


def _migrate(cfg, user_cfg):
    """Migrações de uma vez só (config.json sem 'cfg_version' ou com versão menor). True se algo mudou."""
    if int(user_cfg.get("cfg_version", 1) or 1) >= DEFAULT_CONFIG["cfg_version"]:
        return False
    ffb = cfg.setdefault("ffb", {})
    if ffb.get("polar_zero") == "east":
        # o "east" antigo era só o valor padrão (nunca provado) e fixa o sinal em +1 para 90°/270°
        ffb["polar_zero"] = "north"
        print("[config] ffb.polar_zero: 'east' -> 'north' (convenção DirectInput; corrige o volante pesar sempre para um lado)")
    return True


def merge_user_config(user_cfg):
    """DEFAULT_CONFIG + config/perfil do usuário, já migrado (usado por config.json, recarga a quente e perfis)."""
    cfg = deep_merge(DEFAULT_CONFIG, user_cfg)
    _migrate(cfg, user_cfg)
    return cfg


def load_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        print(f"[config] criado {CONFIG_PATH} com valores padrão")
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        user_cfg = json.load(f)
    stale = unknown_keys(user_cfg)
    if stale:
        print("[config] chaves não reconhecidas (ignoradas; podem ser de uma versão antiga): "
              + ", ".join(stale))
    cfg = deep_merge(DEFAULT_CONFIG, user_cfg)
    migrated = _migrate(cfg, user_cfg)
    before = json.dumps(cfg, sort_keys=True)
    cfg = _sanitize_ffb(cfg)
    if migrated or json.dumps(cfg, sort_keys=True) != before:
        # Persiste o saneamento para a mensagem não reaparecer a cada execução.
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            print("[config] saneamento gravado em config.json")
        except OSError as e:
            print("[config] não consegui gravar o saneamento:", e)
    return cfg
