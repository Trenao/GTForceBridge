"""Simulação de corrida: o volante tem de ser puxado para os DOIS lados com a configuração PADRÃO.

Sintoma relatado (v0.9.2/0.9.3): em pista o volante pesava sempre para o mesmo lado; inverter só trocava o lado fixo.
Causa: o padrão `polar_zero="east"` tratava 90° e 270° (DirectInput: leste/oeste = +X/-X) como "ambíguos" e fixava +1.
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from gtforce_bridge import config as cfgmod
from gtforce_bridge.config import DEFAULT_CONFIG
from gtforce_bridge.vjoy_protocol import EFF_START, ET_CONST
from tests.test_ffb_translator import Rig

EAST_BYTE, WEST_BYTE = 63, 191          # 89° e 269° na escala 0-255 (o que o Windows manda p/ DirectInput 9000 e 27000)


def lap(rig, frames):
    """frames: lista de (byte_direcao, magnitude). Devolve o nível final enviado ao volante em cada quadro."""
    out = []
    rig.put("report", 1, ET_CONST, 255, 1, frames[0][0], 0)
    rig.put("constant", 1, frames[0][1])
    rig.put("op", 1, EFF_START, 1)
    rig.run(0.03)
    for byte, mag in frames:
        rig.put("report", 1, ET_CONST, 255, 1, byte, 0)     # o Windows reenvia o Set Effect a cada mudança de lado
        rig.put("constant", 1, mag)
        rig.run(0.03)
        out.append(rig.levels()[-1])
    return out


class DefaultConfigReachesBothSides(unittest.TestCase):
    def test_default_is_directinput_convention(self):
        self.assertEqual(DEFAULT_CONFIG["ffb"]["polar_zero"], "north")

    def test_game_encodes_side_in_direction_only(self):
        # magnitude SEMPRE >= 0; o lado vem da direção (89° = +X, 269° = -X)
        r = Rig()
        lv = lap(r, [(EAST_BYTE, 4000), (WEST_BYTE, 4000), (EAST_BYTE, 6000), (WEST_BYTE, 2500)])
        self.assertGreater(lv[0], 0); self.assertLess(lv[1], 0)
        self.assertGreater(lv[2], 0); self.assertLess(lv[3], 0)
        self.assertEqual(lv[0], -lv[1])                      # mesma magnitude => mesmo módulo, lado oposto

    def test_game_encodes_side_in_magnitude_sign(self):
        # direção fixa ~90° (+X) e magnitude com sinal (o que o vJoy entrega a muitos jogos)
        r = Rig()
        lv = lap(r, [(EAST_BYTE, 4000), (EAST_BYTE, -4000), (EAST_BYTE, 3000)])
        self.assertGreater(lv[0], 0); self.assertLess(lv[1], 0); self.assertGreater(lv[2], 0)

    def test_both_sign_sources_combine_like_directinput(self):
        # força = magnitude x direção: (-,+X) e (+,-X) puxam para a esquerda; (-,-X) puxa para a direita
        r = Rig()
        lv = lap(r, [(EAST_BYTE, -4000), (WEST_BYTE, 4000), (WEST_BYTE, -4000)])
        self.assertLess(lv[0], 0); self.assertLess(lv[1], 0); self.assertGreater(lv[2], 0)

    def test_invert_mirrors_a_full_lap(self):
        frames = [(EAST_BYTE, 4000), (WEST_BYTE, 5000), (EAST_BYTE, 1500), (WEST_BYTE, 9000)]
        normal, inverted = lap(Rig(invert=False), frames), lap(Rig(invert=True), frames)
        self.assertEqual(inverted, [-x for x in normal])
        self.assertTrue(any(x > 0 for x in normal) and any(x < 0 for x in normal))

    def test_legacy_east_still_available_but_loses_the_side(self):
        # documenta POR QUE o padrão antigo falhava: com zero=leste os dois lados caem no mesmo sinal
        lv = lap(Rig(polar_zero="east"), [(EAST_BYTE, 4000), (WEST_BYTE, 4000)])
        self.assertEqual(lv[0], lv[1])


class ConfigMigration(unittest.TestCase):
    def load(self, user):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "config.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(user, f)
            with mock.patch.object(cfgmod, "CONFIG_PATH", path):
                cfg = cfgmod.load_config()
                with open(path, encoding="utf-8") as f:
                    saved = json.load(f)
            return cfg, saved

    def test_old_config_with_east_is_migrated_and_persisted(self):
        cfg, saved = self.load({"ffb": {"polar_zero": "east", "invert": True}})
        self.assertEqual(cfg["ffb"]["polar_zero"], "north")
        self.assertTrue(cfg["ffb"]["invert"])                 # o resto do usuário é preservado
        self.assertEqual(saved["ffb"]["polar_zero"], "north")
        self.assertEqual(saved["cfg_version"], cfgmod.DEFAULT_CONFIG["cfg_version"])

    def test_choice_made_after_migration_is_respected(self):
        cfg, _ = self.load({"cfg_version": cfgmod.DEFAULT_CONFIG["cfg_version"], "ffb": {"polar_zero": "east"}})
        self.assertEqual(cfg["ffb"]["polar_zero"], "east")


if __name__ == "__main__":
    unittest.main()
