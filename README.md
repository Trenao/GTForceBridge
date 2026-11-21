# gtforce_bridge — Ponte em Python para Logitech GT Force

Ponte universal para o **Logitech GT Force (LPRC-10000)** em qualquer jogo, com ajustes feitos no
programa (calibração, zona morta, curvas) e **force feedback (FFB) preservado**.

Independente de jogo: o volante é lido, processado e exposto ao sistema como um dispositivo
virtual, então qualquer título que aceite controle funciona sem configuração específica.

**Testado em:** Assetto Corsa Rally, Wreckfest 2, Forza Horizon 4 (Microsoft Store).
Outros jogos com suporte a controle devem funcionar da mesma forma.

O volante é lido via SDL2/DirectInput, processado e publicado num **vJoy**; os efeitos de FFB que o jogo
manda ao vJoy são traduzidos e tocados no volante (SDL haptic).

## Requisitos
- Windows, Python 3.10+ **64 bits** (`tkinter` incluso para a GUI)
- **vJoy 2.2.x (fork njz3)** com device 1, eixos X, RZ e SL0 (ou os de `vjoy_axes`), 32 botões e **todos os efeitos FFB marcados**
  (a 2.1.8 original tem structs de FFB diferentes e não é suportada)
- Opcional: HidHide (a GUI tem uma aba para isso) para esconder o volante físico do jogo

```bash
pip install -r requirements.txt
```

## Uso
```bash
python main.py                      # abre a GUI (padrão)
python main.py --list               # dispositivos e capacidades de haptic
python main.py --monitor            # eixos/botões em tempo real
python main.py --run                # executa a ponte (com FFB)
python main.py --gui --tray         # abre a GUI já oculta na bandeja (usado na inicialização com o Windows)
python main.py --run --no-ffb       # só entrada, sem force feedback
python main.py --run --verbose      # loga os pacotes FFB do jogo
python main.py --ffb-dump           # só captura o que o jogo manda ao vJoy
python main.py --ffb-test           # toca forças no volante, sem o jogo
python main.py --ffb-autocal [--apply]   # autocalibração do FFB
python main.py --reset-autocal
python -m unittest discover -s tests     # testes (não precisam de Windows nem de volante)
```

## Configuração (`config.json`)
Recarregada a quente (~0,5 s) com a ponte rodando. Só precisa conter o que você muda; o resto vem dos
defaults. Chaves desconhecidas (ex.: de versões antigas) são **ignoradas** e listadas no log na partida.

Parâmetros de suavização do FFB (bloco `ffb`):

| Chave | Padrão | O que faz |
|---|---|---|
| `update_hz` | 100 | máx. de atualizações/s por efeito (o GT Force é USB 1.1); 0 = sem limite |
| `slew_per_sec` | 0.0 | força constante: variação máxima (fração da escala por segundo); evita trancos. 0 = desligado; ~2–4 é um bom começo |
| `const_deadzone_pct` | 0.0 | ignora força constante abaixo de X % (ruído com o carro parado) |
| `magnitude_scale` | 0 | 0 = automático (10000 ou 32767); um valor força a escala (ex.: 255) |
| `disable_autocenter` | true | desliga o autocenter do driver ao abrir o volante |
| `honor_duration` | true | efeitos do jogo com duração finita, loops e atraso (`StartDelay`) param/começam sozinhos (o vJoy não avisa o fim). `false` = comportamento antigo (só para ao receber STOP) |
| `polar_zero` | `east` | zero da direção polar: `east` (a partir de +X, até a v0.6) ou `north` (convenção DirectInput). O PID 1.0 não define; use `--ffb-dump` para ver o que o jogo manda |
| `min_effective_magnitude` / `min_effect_mode` | gravados pela autocal | compensa a zona morta do motor (modo `stretch`) |

`high_priority` (raiz do config): eleva a prioridade do processo.

## Saídas: vJoy, teclado e controle Xbox (`outputs` no config.json)
O volante processado pode ir para mais de um destino ao mesmo tempo. Cada saída tem `enabled` e **vale na hora**
(hot reload). Padrão: só o vJoy ligado.

- **vJoy** — o caminho para jogos com FFB (Forza Horizon 4).
- **Teclado** (`outputs.keyboard`) — transforma direção/pedais/botões em teclas (SendInput por scancode, funciona com
  DirectInput). Cada binding: `{"source": "steering-", "key": "left", "on": 0.35, "off": 0.25}`. Fontes: `steering+`,
  `steering-`, `throttle`, `brake`, `button:N`. Teclas: letras, números, setas, `space`, `enter`, `esc`, `tab`,
  `shift`, `ctrl`, `alt`, `f1`…`f12` etc. `on`/`off` formam a histerese (a tecla não "pisca" no limiar). As teclas
  são **soltas** ao desligar a saída, perder o volante ou encerrar. Se o jogo rodar como administrador, rode a ponte
  também como administrador (o Windows bloqueia a injeção em janelas de privilégio maior).
- **Xbox 360** (`outputs.xbox`) — direção → analógico esquerdo X, acelerador → RT, freio → LT, botões conforme
  `buttons` (`{"1": "A", "2": "B", ...}`; `""` remove um mapeamento). Requer `pip install -r requirements-xbox.txt` e o
  driver **ViGEmBus** instalado. O Xbox 360 **não tem FFB de volante**.

Evite ligar vJoy **e** Xbox/teclado no mesmo jogo ao mesmo tempo: o jogo receberia a mesma entrada duas vezes. Para usar só
teclado ou só Xbox, ponha `"vjoy": {"enabled": false}`.

## Estrutura
Veja `ARCHITECTURE.md` (arquitetura real, módulos, fluxo, roadmap).

## Licença
MIT
