> **Documento histórico (roteiro original).** A arquitetura real está em `ARCHITECTURE.md`. Divergências
> principais: o Mixer/slots fixos (`ffb_mixer`, `ffb_model`, `haptic_out`, `ffb_decode`) foi **descartado** em favor
> do `ffb_translator` (um efeito SDL por idx+categoria); os comandos hoje são `--run`, `--list`, `--monitor`,
> `--ffb-test`, `--ffb-dump`, `--ffb-autocal`, `--gui` (não existem `diag`, `map` nem `init-config`; o mapeamento
> é feito pela GUI).

# gtforce_bridge — Plano de estrutura e etapas

Ponte em Python para usar o **Logitech GT Force (LPRC-10000)** no **Forza Horizon 4 (Microsoft Store)** com ajustes feitos no programa (não no jogo) e **force feedback (FFB) preservado**.

---

## 1. Objetivo e escopo

| Item | Decisão |
|---|---|
| Entrada | Ler o GT Force (DirectInput via SDL2), aplicar calibração, zona morta, saturação, curva e inversão, e publicar num **vJoy** |
| Saída de FFB | Receber os efeitos HID PID que o jogo manda ao vJoy (`FfbRegisterGenCB`), traduzir e tocar no GT Force (SDL2 haptic → DirectInput) |
| Ajustes | Tudo em `config.json`, recarregado a quente (sem reiniciar) |
| Fora do escopo da v0.1 | Driver HID próprio, GUI, telemetria UDP, hat/POV, perfis por jogo |

**Premissa não verificada:** o FH4 UWP precisa tratar o vJoy como volante (e mandar FFB a ele). Isso só se confirma testando — por isso a Etapa 0 é um teste de viabilidade, antes de investir no resto.

---

## 2. Arquitetura

```
 GT Force (USB)                                              Forza Horizon 4
      │  DirectInput (SDL2)                                        ▲   │
      ▼                                                            │   │ efeitos FFB (HID PID)
 ┌──────────┐   estado cru   ┌───────────┐  eixos/botões   ┌───────┴───▼──────┐
 │ wheel.py │ ─────────────► │ curves.py │ ──────────────► │ vjoy.py (vJoy)   │
 └──────────┘                └───────────┘                 └───────┬──────────┘
      ▲                                                            │ callback (thread do driver)
      │ SDL haptic (efeitos DirectInput)                           ▼
 ┌────────────────┐   MixOut   ┌──────────────┐  eventos   ┌──────────────┐
 │ haptic_out.py  │ ◄───────── │ ffb_mixer.py │ ◄───────── │ ffb_decode / │
 └────────────────┘            └──────────────┘ EffectBank │ ffb_model.py │
                                                           └──────────────┘
                   bridge.py = loop principal (500 Hz) que liga tudo
```

**Fluxo de entrada (por tick):** `SDL_JoystickUpdate` → eixos crus → normalização/calibração → deadzone → saturação → curva → vJoy `UpdateVJD`.

**Fluxo de FFB:**
1. O jogo escreve efeitos no vJoy; o driver chama nosso callback (thread do driver).
2. O callback só **decodifica** o pacote (`Ffb_h_*`) e enfileira um evento (`SimpleQueue`) — nunca toca no hardware.
3. O loop principal drena a fila e atualiza o `EffectBank` (estado de cada efeito: tipo, magnitude, duração, se está tocando).
4. O `Mixer` agrega os efeitos ativos em **poucos slots fixos** (constante, mola, amortecedor, atrito, 2 senoides), aplica ganhos, inversão, força mínima e limite de variação.
5. O `HapticOut` mantém esses slots como efeitos SDL infinitos e só chama `SDL_HapticUpdateEffect` quando o valor muda (limitado a ~100 Hz).

**Por que slots fixos e não um efeito SDL por efeito do jogo:** o GT Force tem poucos slots de efeito e é USB 1.1; criar/destruir efeitos em ritmo de jogo causa travadas. Agregar é mais estável.

---

## 3. Estrutura de pastas

```
gtforce_bridge/
├── PLANO.md                  este documento
├── README.md                 uso rápido
├── requirements.txt          pysdl2, pysdl2-dll
├── config.json               criado na primeira execução (defaults + seus ajustes)
├── main.py                   CLI: run | diag | map | ffb-test | ffb-dump | init-config
├── gtforce_bridge/
│   ├── config.py             defaults, merge, load/save, watcher de mtime
│   ├── curves.py             deadzone, saturação, expo/gamma, curva por pontos, pedais
│   ├── wheel.py              SDL2: achar/abrir o GT Force, ler eixos e botões
│   ├── vjoy.py               ctypes do vJoyInterface.dll: acquire, UpdateVJD, callback FFB
│   ├── ffb_decode.py         structs C do vJoy + decodificação de pacote → eventos
│   ├── ffb_model.py          EffectBank: estado dos efeitos, start/stop/expiração, envelope
│   ├── ffb_mixer.py          agrega efeitos em slots + ganhos/min_force/slew (puro, testável)
│   ├── haptic_out.py         SDL haptic: slots fixos, update por mudança, autocenter off
│   ├── winutil.py            timeBeginPeriod(1), prioridade do processo
│   └── bridge.py             loop principal, hot reload, reconexão, estatísticas
└── tests/                    unittest (roda sem Windows e sem volante)
```

---

## 4. Módulos e responsabilidades

| Módulo | Responsabilidade | Depende de hardware? |
|---|---|---|
| `config.py` | `DEFAULTS` + merge com `config.json`; `Watcher` detecta mudança de arquivo | não |
| `curves.py` | `SteeringProcessor`, `PedalProcessor` (separado ou combinado) | não |
| `wheel.py` | Inicia SDL com dicas p/ DirectInput e eventos em segundo plano; **ignora dispositivos "vJoy"**; `poll()` | sim (SDL) |
| `vjoy.py` | Carrega a DLL, confere versão/FFB, adquire o device, `send()`, registra callback | sim (Windows+vJoy) |
| `ffb_decode.py` | Structs idênticas ao `vjoyinterface.h` + `decode(api, pacote)` | não (testável com API falsa) |
| `ffb_model.py` | `EffectBank.apply(evento)`, `active(now)` | não |
| `ffb_mixer.py` | `Mixer.step()` → `MixOut` | não |
| `haptic_out.py` | Converte `MixOut` em efeitos SDL | sim (SDL haptic) |
| `bridge.py` | Orquestra, recarrega config, reconecta | sim |

---

## 5. Configuração (`config.json`)

Principais blocos (todos com default; só precisa escrever o que mudar):

- `wheel`: `name_contains`, `steering_axis`, `pedal_mode` (`separate`/`combined`), `throttle_axis`, `brake_axis`, `combined_axis`, calibrações (`steering_cal`, `throttle_cal`, `brake_cal`, `combined_cal`). **Preenchido pelo comando `map`.**
- `steering`: `invert`, `range_pct`, `deadzone_pct`, `saturation_pct`, `expo` (0–1), `gamma`, `curve_points`, `smoothing`.
- `throttle` / `brake`: `deadzone_pct`, `saturation_pct`, `gamma`.
- `vjoy`: `dll_path`, `device_id`, `axes` (qual eixo vJoy recebe direção/acelerador/freio).
- `ffb`: `enabled`, `invert`, `master_gain`, ganhos por tipo, `min_force`, `max_force`, `slew_per_sec`, `update_hz`, `use_direction`.
- `loop_hz`, `logging`.

---

## 6. Modelo de FFB (mapeamento PID → SDL)

| Efeito do jogo (HID PID) | Slot no GT Force | Observações |
|---|---|---|
| Constant / Ramp | `SDL_HAPTIC_CONSTANT` | soma dos efeitos ativos, × ganho do efeito × envelope; sinal = direção da força |
| Spring | `SDL_HAPTIC_SPRING` | domina o de maior coeficiente; centro e saturação repassados |
| Damper / Inertia | `SDL_HAPTIC_DAMPER` | inércia aproximada como amortecedor |
| Friction | `SDL_HAPTIC_FRICTION` | |
| Sine / Square / Triangle / Sawtooth | `SDL_HAPTIC_SINE` (2 slots) | os 2 periódicos mais fortes; outras formas aproximadas por senoide |
| Device Control (enable/disable/stop/reset/pause) | liga/desliga tudo | |
| Device Gain | multiplica tudo | |

Pós-processamento do slot constante: `master × constant_gain` → inversão → `min_force` (vence a zona morta do motor do GT Force) → `max_force` → limite de variação (`slew_per_sec`, evita trancos).

**Limitações assumidas:** 200° de curso e motor fraco; o jogo "acha" que fala com um volante maior, então a mola/centro são só repassados (não há reescala angular na v0.1).

---

## 7. Etapas

Cada etapa tem um **critério de aceite** — só avançar quando passar.

### Etapa 0 — Pré-requisitos e viabilidade
1. Python 3.10+ **64 bits**; `pip install -r requirements.txt`.
2. Instalar **vJoy 2.2.x (fork njz3)**; no `vJoyConf`: device 1, eixos X, Y, Z (e demais se quiser), 32 botões, **todos os efeitos de FFB marcados**. A versão original 2.1.8 tem structs de FFB diferentes e não é suportada aqui.
3. Fechar DXTweak2, Steam Input para este jogo, forza_emuwheel e qualquer outro remapeador.
4. **Teste de viabilidade:** com o vJoy ativo, abrir o FH4 e ver se a tela de controles reconhece um volante/dispositivo novo. Se o FH4 UWP ignorar o vJoy, ver o Plano B (seção 9).

**Aceite:** `python main.py diag` lista o GT Force, mostra vJoy habilitado, versão e `FFB: sim`.

### Etapa 1 — Mapeamento do volante
`python main.py map`: o assistente pede "solte tudo / esquerda / direita / acelerador / freio", detecta quais eixos SDL mexem (o GT Force pode expor pedais combinados ou separados — isso não é assumido) e grava as calibrações no `config.json`.

**Aceite:** `diag --live` mostra direção indo de −1 a +1 e pedais de 0 a 1 nos eixos certos.

### Etapa 2 — Entrada pura (sem FFB)
`python main.py run --no-ffb`: curvas → vJoy. Conferir em `joy.cpl` (propriedades do vJoy) e no FH4.

**Aceite:** direção centrada e linear; pedais chegam a 0 e 100%; ajustar `deadzone/expo/gamma` e ver o efeito ao salvar o arquivo (hot reload).

### Etapa 3 — Captura do que o jogo manda (FFB)
`python main.py ffb-dump` com o FH4 rodando: registra no log cada pacote decodificado (tipos de efeito, magnitudes, durações, direções).

**Aceite:** o log mostra efeitos chegando. Se não chegar **nada**, o jogo não está tratando o vJoy como volante com FFB → Plano B.

### Etapa 4 — Saída de FFB no GT Force
1. `python main.py ffb-test`: toca constante (direita/esquerda), mola, amortecedor e senoide **sem o jogo**; pergunta se o volante foi para a direita e grava `ffb.invert` sozinho.
2. `python main.py run`: o caminho completo com o jogo.

**Aceite:** força de curva sente-se no sentido certo; centro do volante firme; sem trancos ao acelerar/frear.

### Etapa 5 — Ajuste fino
Ordem: `master_gain` → `constant_gain` → `min_force` → `slew_per_sec` → ganhos de mola/amortecedor → `periodic_gain`. Usar o log de estatísticas (loop Hz, pacotes/s, última força).

### Etapa 6 — Robustez
Reconexão se o volante sair da USB, parada limpa (zera forças e libera o vJoy no Ctrl+C), log em arquivo, ícone/atalho para iniciar com o Windows (opcional).

### Etapa 7 — Evoluções (fora da v0.1)
- Curvas por carro/jogo (perfis), GUI (tkinter ou página local).
- Envelope/“direção” refinados com base no que o `ffb-dump` mostrar.
- Auto-calibração de FFB (a sua versão atual já tem; portar a ideia para um módulo `autocal.py`).
- Backend alternativo ViGEm (entrada Xbox, sem FFB) atrás de uma interface `VirtualPad`.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| FH4 UWP não trata o vJoy como volante | Sem FFB (ou sem detecção) | Etapa 0/3 detectam cedo; Plano B |
| Struct de FFB difere entre versões do vJoy | Valores lixo no callback | Structs conferidas contra o `vjoyinterface.h` do njz3; `ffb-dump` mostra os valores reais; testes de `sizeof` |
| Sinal da força invertido | Volante "foge" do centro | `ffb-test` calibra `ffb.invert` |
| Zona morta do motor do GT Force | Forças fracas somem | `min_force` |
| Latência (Python + vJoy + USB 1.1) | FFB "mole" | loop 500 Hz com `timeBeginPeriod(1)`, update por mudança, 100 Hz de teto no hardware |
| SDL pegar o volante por outro driver (HIDAPI/RawInput) | Sem haptic | dicas SDL forçando DirectInput |
| SDL listar o próprio vJoy como joystick | Loop de realimentação | `wheel.py` ignora nomes com "vjoy" |
| Python 32 bits com DLL 64 bits | DLL não carrega | checagem e mensagem clara |

---

## 9. Plano B (se o FH4 não mandar FFB ao vJoy)

1. **Telemetria UDP:** o FH4 tem a opção *Data Out* (a verificar na sua versão). Com ela, o programa pode **sintetizar** o FFB (força lateral/auto-alinhante, perda de aderência, impacto) a partir da física, em vez de receber efeitos do jogo — é a mesma ideia do mod de Cyberpunk que você citou (FFB derivado da física do jogo). Entraria como um módulo `telemetry.py` alimentando o mesmo `Mixer`.
2. **Entrada via ViGEm (Xbox 360)** + FFB sintetizado pela telemetria.
3. Driver HID virtual próprio (VHF/UMDF) com descritor de volante — só se 1 e 2 não servirem; exige assinatura/modo de teste.

---

## 10. O que aproveitar do mod de Cyberpunk (`cp2077-wheel-mod`)

- **Aproveitável como ideia:** detectar capacidades do hardware e mostrar só o que existe; escalar o FFB pela faixa de rotação; FFB composto (centralização, carga em curva, textura, impacto, perda de aderência); logs em arquivo; `ARCHITECTURE.md`.
- **Não reaproveitável:** o código (C++/RED4ext/redscript) e o **Logitech Steering Wheel SDK**, que não cobre o GT Force.

---

## 11. Comandos

```
pip install -r requirements.txt
python main.py diag [--live]     # dispositivos SDL, vJoy, eixos ao vivo
python main.py map               # assistente de calibração → config.json
python main.py ffb-test          # testa forças no volante (sem jogo) e calibra o sinal
python main.py ffb-dump          # loga o que o jogo manda ao vJoy
python main.py run [--no-ffb] [-v]
python -m unittest discover -s tests
```
