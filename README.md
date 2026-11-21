# GTForce Bridge

**Ponte em Python que faz o Logitech GT Force (LPRC-10000) funcionar com jogos modernos, com force feedback (FFB) preservado.**

> 🇬🇧 *Python bridge that reads a Logitech GT Force / WingMan Formula Force GP wheel via SDL2, publishes it to a virtual vJoy device and translates the game's vJoy force-feedback effects back to the real wheel (SDL haptic). Includes a Tk control-center GUI, calibration, curves, profiles, tray mode and an FFB auto-calibration.*

Criado por **Sthevan P.K. (oTrenao)**.

---

## O que é

O GT Force é lido via **SDL2/DirectInput**, processado no programa (calibração, zona morta, curvas, mapeamento) e publicado num **vJoy**. Os efeitos de FFB que o jogo envia ao vJoy são **traduzidos e tocados no volante físico** (SDL haptic).

Alvo principal: **Forza Horizon 4 (Microsoft Store)**. Qualquer jogo que use vJoy com FFB deve funcionar em princípio, mas isso não foi testado.

```
GT Force ──SDL2/DirectInput──► wheel.py ──► controls.py ──► sinks.py ──┬─► vJoy ──► jogo (com FFB)
                                          (ControlState)  (outputs.*)  ├─► teclado (SendInput)
                                                                       └─► Xbox 360 virtual (ViGEm)
                                                                          │
jogo ──efeitos FFB──► vJoy ──callback──► ffb_receiver.py (fila)           │
GT Force ◄──SDL haptic── ffb_translator.py ◄──── bridge.py (loop, 500 Hz) ◄┘
```

Detalhes de arquitetura: [`ARCHITECTURE.md`](ARCHITECTURE.md). O que foi conferido contra fontes oficiais (vJoy, USB PID 1.0, DirectInput, SDL2): [`FFB_REFERENCIAS.md`](FFB_REFERENCIAS.md).

## Recursos

- **Painel (Control Center)** em Tk: estado da ponte, medidor de direção, pedais, medidor de FFB e osciloscópio direção × força.
- **Calibração**, zona morta, expo/ganho/inversão por eixo, **mapeamento** de eixos e botões, **perfis**.
- **FFB traduzido**: constante, rampa, periódicos e condições (mola, amortecedor, inércia, fricção), com duração, loops e atraso do jogo respeitados, suavização (`slew`) e compensação da zona morta do motor.
- **Autocalibração do FFB** (`--ffb-autocal`), com perfil por PID do volante.
- **Reconexão automática** do volante e do vJoy.
- **Saídas extras**: teclado (SendInput) e controle Xbox 360 virtual (ViGEm, opcional).
- **Bandeja do sistema**, iniciar com o Windows (sem admin), instância única.
- **Aba HidHide**: oculta o volante físico do jogo e autoriza a ponte.
- **Hot reload** do `config.json` (~0,5 s) com a ponte rodando.
- Log em arquivo com rotação (`logs/bridge.log`).

## Requisitos

| Item | Detalhe |
|---|---|
| Sistema | Windows |
| Python (só para rodar do código) | 3.10+ **64 bits**, com `tkinter` |
| **vJoy** | fork **njz3 2.2.x** (ex.: `v2.2.1.1`), device 1 com eixos **X, RZ e SL0**, **32 botões** e **todos os efeitos FFB marcados**. A 2.1.8 original **não** é suportada. |
| HidHide (recomendado) | Para esconder o volante físico do jogo. O pacote winget é `Nefarius.HidHide`. |
| ViGEmBus (opcional) | Só para a saída de controle Xbox 360. |

Hardware medido: GT Force LPRC-10000, que o sistema enxerga como **WingMan Formula Force GP** (VID `0x046D`, PID `0xC293`).

## Instalação

### Opção A — executável (sem instalar Python)

1. Baixe o `GTForceBridge-vX.Y.Z.zip` na aba **[Releases](../../releases)** e extraia numa pasta fixa.
2. Instale o **vJoy** (fork njz3) e o **HidHide**, e configure o vJoy (veja abaixo).
3. Abra `GTForceBridge.exe`.
4. Se usar o HidHide, na aba **HidHide** clique em **Autorizar esta ponte**.

`config.json`, `profiles/` e `logs/` ficam **ao lado do exe**.

### Opção B — a partir do código

```bat
1-PREPARAR_GTForceBridge.bat
2-INICIAR_GTForceBridge.bat
```

O `1-PREPARAR_GTForceBridge.bat`:

- procura Python 3.10+ 64 bits com tkinter (e tenta instalar o 3.12 pelo winget se não achar);
- cria/valida o `.venv` e instala o `requirements.txt`;
- verifica as importações;
- detecta HidHide e vJoy e **oferece instalar** (pergunta S/N, com pedido de administrador).

Opções: `1-PREPARAR_GTForceBridge.bat --xbox` (instala também o `requirements-xbox.txt`) e `--sem-drivers` (pula a verificação de HidHide/vJoy).

Manualmente:

```bash
pip install -r requirements.txt
python main.py
```

### Configurar o vJoy

No **vJoyConf**: Device **1**, eixos **X, RZ e Slider0 (SL0)**, **32 botões** e **todos os efeitos FFB** habilitados. Reinicie o Windows depois de instalar o driver.

> O vJoy é instalado em modo normal (não silencioso) de propósito: há relatos de instalação travando ou falhando no Windows 11 e você precisa ver a janela.

## Uso

```bash
python main.py                          # abre a GUI (padrão)
python main.py --list                   # dispositivos e capacidades de haptic
python main.py --monitor                # eixos/botões em tempo real
python main.py --run                    # executa a ponte (com FFB)
python main.py --run --no-ffb           # só entrada, sem force feedback
python main.py --run --verbose          # loga os pacotes FFB do jogo
python main.py --gui --tray             # GUI já oculta na bandeja
python main.py --ffb-dump               # captura o que o jogo manda ao vJoy
python main.py --ffb-test               # toca forças no volante, sem o jogo
python main.py --ffb-autocal [--apply]  # autocalibração do FFB
python main.py --reset-autocal
```

No exe, os mesmos argumentos valem: `GTForceBridge.exe --gui --tray`.

Fluxo típico:

1. Conecte o volante e clique em **Detectar volante** (a lista deve mostrar o GT Force).
2. Calibre e ajuste curvas, depois salve.
3. **Iniciar ponte**.
4. No jogo, escolha o **vJoy** como volante.

## Configuração (`config.json`)

Só precisa conter o que você muda; o resto vem dos padrões. Chaves desconhecidas são **ignoradas** e listadas no log.

| Chave | Padrão | O que faz |
|---|---|---|
| `device_match` | `"Formula Force"` | trecho do nome do volante |
| `device_pids` | PIDs Logitech | fallback por VID `0x046D` + PID |
| `vjoy_dll` | `C:\Program Files\vJoy\x64\vJoyInterface.dll` | caminho da DLL |
| `vjoy_device_id` | `1` | device vJoy usado |
| `loop_hz` | `500` | frequência do loop |
| `ffb.update_hz` | `100` | máx. de atualizações/s por efeito (o GT Force é USB 1.1) |
| `ffb.slew_per_sec` | `0.0` | rampa da força constante (0 = desligado; ~2–4 é um bom começo) |
| `ffb.honor_duration` | `true` | respeita duração, loops e atraso dos efeitos do jogo |
| `ffb.polar_zero` | `east` | zero da direção polar: `east` ou `north` (DirectInput) |
| `ffb.min_effective_magnitude` / `min_effect_mode` | gravados pela autocal | compensa a zona morta do motor |
| `high_priority` | `false` | eleva a prioridade do processo |

Saídas (`outputs`): `vjoy`, `keyboard` (bindings com histerese `on`/`off`) e `xbox` (direção → analógico esquerdo, acelerador → RT, freio → LT). Evite ligar vJoy **e** teclado/Xbox no mesmo jogo ao mesmo tempo. Parâmetros adicionais de cada versão estão nos `CHANGELOG_v*.md`.

## HidHide

O HidHide libera o volante físico só para os executáveis **autorizados**, por caminho. Ao usar o exe, é preciso autorizar o `GTForceBridge.exe`:

- GUI → aba **HidHide** → **Autorizar esta ponte**; ou
- HidHide Configuration Client → *Applications* → adicionar o `GTForceBridge.exe`.

Se mover a pasta, autorize de novo. A gravação da whitelist pode exigir administrador.

## Solução de problemas

**`Volante contendo 'Formula Force' não encontrado`**
1. Clique em **Detectar volante** e veja se o GT Force aparece.
2. Se aparecer com outro nome, ajuste `device_match` no `config.json`.
3. Se não aparecer no exe mas aparecer rodando do código, é o HidHide: autorize o `GTForceBridge.exe`.
4. Se não aparecer em nenhum lugar: verifique cabo, driver e se outro programa está segurando o volante.

**`vJoy não está instalado/ativo` / device indisponível**
Confirme o fork njz3 2.2.x, o device 1 configurado como acima e o Windows reiniciado após o driver.

**Log com acentos quebrados ou atrasado no exe**
Use o exe gerado pelo `3-compilar_gtforce_bridge.bat` atual, que aplica um hook de UTF-8 e stdout em linha.

**Antivírus acusa o exe**
Executáveis gerados com PyInstaller costumam gerar falsos positivos. Compile você mesmo a partir do código se preferir.

## Compilar o executável

```bat
3-compilar_gtforce_bridge.bat
```

Gera `dist\GTForceBridge\GTForceBridge.exe` (PyInstaller, `--onedir --windowed`). O script usa o `.venv` (chama o `PREPARAR` se faltar), empacota SDL2 (`sdl2dll`), copia `config.json`/`profiles` para a pasta do exe e aborta se o exe estiver rodando.

Build de referência: Python 3.14, PySDL2 0.9.17 / pysdl2-dll 2.32.10, pystray 0.19.5, Pillow 13.0.0.

## Testes

```bash
python -m unittest discover -s tests
```

Os testes não precisam de Windows nem de volante.

## Estrutura

```
main.py                  ponto de entrada
gtforce_bridge/          pacote: bridge, wheel, vjoy, ffb_translator, autocal, config, gui/ ...
tests/                   testes unitários
1-PREPARAR_GTForceBridge.bat / 2-INICIAR_GTForceBridge.bat / 3-compilar_gtforce_bridge.bat
ARCHITECTURE.md · FFB_REFERENCIAS.md · PLANO.md · CHANGELOG_v*.md
```

## Limitações conhecidas

- O envelope de efeitos FFB do vJoy (`FFB_EFF_ENVLP`) ainda **não é aplicado**.
- O DeadBand de condição tem dúvida no header do vJoy (0…1000 vs 0…10000); o `--ffb-dump` ajuda a confirmar com o jogo real.
- O controle Xbox 360 virtual **não tem FFB de volante**.
- Testado em hardware só com o GT Force PID `0xC293`.

## Créditos

**Autor e mantenedor: Sthevan P.K. (oTrenao).**

Este projeto usa e agradece:

- [**vJoy**](https://github.com/njz3/vJoy) — Shaul Eizikovich (original) e njz3 (fork com melhorias de FFB).
- [**HidHide**](https://github.com/nefarius/HidHide) — Nefarius Software Solutions.
- [**SDL2**](https://www.libsdl.org/) e [**PySDL2**](https://github.com/py-sdl/py-sdl2) / `pysdl2-dll`.
- [**pystray**](https://github.com/moses-palmer/pystray) e [**Pillow**](https://python-pillow.org/).
- [**ViGEmBus**](https://github.com/nefarius/ViGEmBus) e [`vgamepad`](https://github.com/yannbouteiller/vgamepad) (saída Xbox opcional).
- Ideias do `cp2077-wheel-mod` (MIT; só conceitos, o código é C++).

Cada um desses projetos tem sua própria licença; **não** são redistribuídos neste repositório.

## Aviso

Projeto independente, **sem afiliação** com Logitech, Microsoft, Playground Games, Sony ou os autores do vJoy/HidHide. Marcas citadas pertencem aos seus donos. Force feedback move um motor real: use por sua conta e risco, com as mãos preparadas ao testar e sem deixar o volante sozinho com força aplicada.

## Licença

[MIT](LICENSE) © 2026 Sthevan P.K. (oTrenao)
