# gtforce_bridge — Arquitetura (v0.5)

Documento do que **existe hoje**. O `PLANO.md` é o roteiro original (histórico); onde ele diverge, vale este arquivo.

## Fluxo

```
GT Force ──SDL2/DirectInput──► wheel.py ──► controls.py ──► sinks.py ──┬─► vJoy ──► jogo (com FFB)
                                          (ControlState)  (outputs.*)  ├─► teclado (SendInput)
                                                                       └─► Xbox 360 virtual (ViGEm)
                                                                          │
jogo ──efeitos FFB──► vJoy ──callback (thread do driver)──► ffb_receiver.py (fila)
                                                                          │
GT Force ◄──SDL haptic── ffb_translator.py ◄──── bridge.py (loop, 500 Hz) ◄┘
```

- `bridge.py` é o loop: hot reload do `config.json` (0,5 s), parada limpa via `bridge.stop` (a GUI usa),
  telemetria em `telemetry.json` (a GUI lê), **reconexão do volante** (`reconnect.WheelLink`).
- O callback do vJoy só decodifica e enfileira; quem toca no hardware é o loop principal.
- `controls.compute_controls()` devolve um `ControlState` (direção, pedais, botões) já calibrado; `sinks.OutputSink` publica
  esse estado. É o ponto de extensão para Xbox/teclado (ver Roadmap). O `VJoySink` **não derruba a ponte** se o vJoy falhar:
  loga com limite de frequência e tenta readquirir o device a cada ~1 s (`VJoy.reacquire`).
- `ffb_translator.py`: um efeito SDL por (idx do vJoy, categoria), mantido vivo; `EFF_STOP` para só a categoria certa.
  Parâmetros são aplicados **na hora** quando o tipo já é conhecido (um fluxo contínuo de força chega ao volante); só os que
  vêm antes do `EFF_REPORT` esperam por ele (descartados após 250 ms). Atualizações respeitam `update_hz`; a força constante
  pode ter rampa (`slew_per_sec`), zona morta de ruído e *stretch* da zona morta do motor (`min_effective_magnitude`).
  O Mixer/slots fixos do PLANO foi **descartado** (código removido): o tradutor por categoria é o caminho validado.

## Módulos

| Arquivo | Função |
|---|---|
| `paths.py` | caminhos (config, perfis, telemetria, stop, relatório de autocal) |
| `controls.py` | `ControlState` (direção, pedais, botões já calibrados), independente de destino |
| `sinks.py` | saídas: `VJoySink`, `KeyboardSink` (SendInput), `XboxSink` (vgamepad/ViGEm); `build_sinks()` |
| `mapping.py` | fontes (`steering+`, `button:N`…), histerese e tabela de teclas (scancodes) |
| `winutil.py` | timer de 1 ms (`timeBeginPeriod`/`timeEndPeriod` pareados) e prioridade do processo |
| `config.py`, `constants.py` | defaults + merge + saneamento; constantes de eixos e escalas |
| `curves.py` | calibração, zona morta, expo/ganho, conversão p/ vJoy |
| `wheel.py`, `device_table.py` | SDL2 (abrir, ler, `attached()`); tabela de modelos Logitech |
| `vjoy_protocol.py`, `vjoy.py` | structs/constantes FFB; DLL do vJoy (inclui `reacquire`) |
| `ffb_receiver.py`, `ffb_translator.py` | decodifica pacotes; traduz p/ SDL haptic |
| `ffb_dump.py` | formata/conta o que o jogo manda (`--ffb-dump`) |
| `reconnect.py` | máquina de estados de reconexão (pura, testada) |
| `logsetup.py` | espelha stdout/stderr em `logs/bridge.log` (rotação 2 MB × 3) |
| `autocal.py`, `ffb_test.py`, `diag.py` | autocalibração, teste de FFB, `--list`/`--monitor` |
| `bridge.py`, `cli.py` | loop principal; linha de comando |
| `gui/` | `app.py` + uma aba por arquivo (mixins) |

## Comandos

```
python main.py                    # GUI
python main.py --gui              # ou sem argumentos
python main.py --list | --monitor
python main.py --ffb-test
python main.py --ffb-autocal [--apply] | --reset-autocal
python main.py --run [--no-ffb] [--verbose]
python main.py --ffb-dump         # só captura o que o jogo manda ao vJoy
```

## Estado do PLANO

| Etapa | Estado |
|---|---|
| 0 Pré-requisitos / viabilidade | **você precisa rodar** (vJoy, FH4 reconhece o vJoy?) |
| 1 Mapeamento do volante | feito pela GUI (abas Calibração/Mapeamento) |
| 2 Entrada pura | feito: `--run --no-ffb` |
| 3 Captura do FFB do jogo | feito: `--ffb-dump` / botão "Capturar FFB do jogo" — **resultado depende de rodar no seu PC** |
| 4 Saída de FFB no GT Force | feito (translator + `--ffb-test` + autocal) — validar no hardware |
| 5 Ajuste fino | feito via GUI (aba Force Feedback) |
| 6 Robustez | reconexão ✔, parada limpa ✔, log em arquivo ✔; atalho p/ iniciar com o Windows ✘ |
| 7 Evoluções | perfis ✔, autocal ✔; backend ViGEm ✘ (ver Roadmap); Mixer/slots fixos: descartado |

## O que foi aproveitado do cp2077-wheel-mod (MIT; só ideias, o código é C++)

| Ideia | Situação |
|---|---|
| Detectar o modelo/capacidades e avisar quando não bate | ✔ `device_table.py` (usado em `--list` e `--run`) |
| Log em arquivo | ✔ `logsetup.py` |
| Zerar forças e voltar neutro quando o volante some (watchdog) | ✔ no `bridge.py` (perda de USB); watchdog por "jogo parou de mandar" ✘ |
| Esconder na GUI o que o hardware não tem | ✘ (GUI ainda mostra tudo) |
| Escalar FFB pelo curso do volante | ✘ — o GT Force tem ~200–240° e o jogo assume mais; o sentido e o tamanho da correção precisam de teste no volante |
| FFB composto (centragem, carga em curva, textura, impacto, perda de aderência) | ✘ — só faz sentido no **Plano B** (telemetria), porque o mod sintetiza a força a partir da física do jogo |
| `ARCHITECTURE.md` | ✔ este arquivo |

## Plano B (só se `--ffb-dump` não receber nada)

`telemetry.py` ouviria o *Data Out* UDP do FH4 (formato do pacote a confirmar na sua versão) e alimentaria um
sintetizador de força (centragem proporcional à velocidade, carga lateral, perda de aderência, impacto) que
tocaria no GT Force pelo mesmo caminho SDL haptic. Não implementado: depende do resultado da Etapa 3.

## Saídas e roadmap

Feito (v0.5): `KeyboardSink` e `XboxSink` ligáveis por `outputs.<nome>.enabled` (hot reload), com histerese, soltura
garantida de teclas (desligar/perder volante/encerrar) e falha de driver tratada sem derrubar a ponte. Vários destinos
ao mesmo tempo funcionam (o loop itera a lista de sinks).

Observações de projeto:
- O Xbox 360 não tem FFB de volante: só 2 motores de vibração. Para FFB real no jogo o caminho continua sendo o vJoy.
- O **ViGEmBus foi aposentado pelo autor em 2023** (sem novas atualizações; instalações existentes continuam
  funcionando — [aviso oficial](https://docs.nefarius.at/projects/ViGEm/End-of-Life/)); confira o estado atual antes de
  depender dele. O `vgamepad` (MIT) é só um adaptador em cima dele.

Pendente:
1. **Importar `x360ce.ini`** — o formato do arquivo varia entre versões do x360ce (a documentação oficial não o
   descreve). Falta um `x360ce.ini` real para implementar e testar o importador, e entregar o resultado via `XboxSink`.
   Se for reaproveitar código do x360ce, confira a licença antes.
2. **Camada de mapeamento geral** — hoje o mapeamento é fixo por saída (direção/pedais/botões). O passo seguinte é uma
   tabela `origem física → destino` por perfil (inversão, zona morta e curva por binding; eixo→eixo, hat, rumble).
3. **Aba "Saídas" na GUI** — hoje se configura editando `config.json` (recarrega na hora).
4. Pendente de rodar no seu PC: Etapa 0/3 (o FH4 reconhece o vJoy? chega FFB?), SendInput num jogo real e o
   ajuste de `slew_per_sec`.
