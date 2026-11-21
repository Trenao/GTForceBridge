# v0.9 — GUI redesenhada (Control Center)

Só a interface mudou; ponte, FFB, perfis e configuração continuam iguais.

## Novo layout
- **Barra superior**: página atual, indicador de estado (cinza = parado, laranja = executando, verde = ponte ativa),
  seletor de perfil e botões INICIAR PONTE / PARAR sempre à vista.
- **Menu lateral** no lugar das abas (atalhos `Ctrl+1` … `Ctrl+9`), com a página ativa destacada e as ferramentas
  (Detectar volante, Teste FFB, Capturar FFB do jogo, Log detalhado, Sem FFB) no rodapé.
- **Gaveta de log** recolhível, com botão limpar.
- **Painel (nova página inicial)**: cartões de estado, medidor de direção, barras de acelerador/freio,
  medidor de Force Feedback e osciloscópio (direção × força, últimos 8 s), tudo ao vivo a partir da telemetria.

## Interface adaptável
| Largura da janela | Comportamento |
|---|---|
| ≥ 1000 px | menu lateral completo; Painel em 3 colunas + osciloscópio |
| 700–999 px | menu compacto; ferramentas passam a um menu "Ferramentas" se a altura for < 720 px |
| < 700 px | menu lateral vira lista suspensa; Painel em 1–2 colunas com rolagem |
Cada página rola sozinha quando o conteúdo não cabe. Tamanho mínimo: 560×460 px.

## Técnico
- `gui/theme.py` (paleta e estilos ttk, único lugar com cores), `gui/widgets.py` (instrumentos em canvas),
  `gui/dashboard_tab.py` (página Painel). As demais páginas só herdaram o tema.
- Fonte: Segoe UI/Consolas no Windows; cai para uma fonte instalada em outros sistemas.

# v0.9.1 — bandeja do sistema e inicialização com o Windows

- **Modo bandeja**: minimizar e/ou fechar (X) enviam o painel para a bandeja (ambos configuráveis). Ícone com o estado
  (cinza parado / laranja executando / verde ponte ativa) e menu: Abrir painel, Iniciar ponte, Parar ponte, Sair.
  Também há "Ocultar na bandeja" no menu lateral. Requer `pystray` e `Pillow` (já no `requirements.txt` para Windows);
  sem eles a GUI funciona normalmente e fechar/minimizar se comportam como antes.
- **Iniciar com o Windows** (página *Sistema*): grava `HKCU\...\Run` (sem administrador) com `--gui --tray`,
  abrindo já oculto na bandeja e sem janela de console (usa `pythonw.exe`). Desmarcar remove a entrada.
- **Iniciar a ponte automaticamente** ao abrir a GUI (opcional, desligado por padrão). Espera 3 s e, se a ponte falhar
  (vJoy/volante ainda não prontos no boot), tenta de novo até 3 vezes a cada 10 s. Parar pelo painel/bandeja não repete.
- **Instância única** no Windows: abrir o programa de novo avisa que ele já está na bandeja, em vez de abrir uma 2ª cópia.
- Novo argumento `--tray` (abre a GUI oculta). Nova seção `app` no `config.json`
  (`minimize_to_tray`, `close_to_tray`, `autorun_bridge`).

# v0.9.2 — diagnóstico do lado do FFB + pequenas correções

- **Painel**: osciloscópio e medidor mostram também a magnitude **bruta do jogo** (cinza tracejado / triângulo) ao lado
  do que é **enviado ao volante** (azul), mais o texto "direção polar N° (sinal ±)". Comparar os dois mostra se o
  jogo manda os dois lados e a interpretação da direção achata um deles.
- **`--ffb-dump`**: passa a cruzar a *direção* de cada efeito com a *magnitude* das forças constantes e imprime
  "lados da força constante" (esquerda/direita sob `zero=leste` e `zero=norte`) a cada resumo e ao final.
- Regra de sinal da direção extraída para `vjoy_protocol.direction_sign` (uma só fonte para tradutor e dump; comportamento igual).
- Telemetria: `ffb.const` agora é a **soma** dos efeitos constantes tocando (antes: só o último); novos campos `game`, `sign`, `dir`.
- GUI: `config.json` salvo de forma atômica. Testes: +10 (`tests/test_ffb_side_diag.py`). Análise completa em `ANALISE.md`.

# v0.9.3 — Painel: direções vistas e aviso de direção ambígua

- Telemetria `ffb`: novos campos `dirs` (ângulos polares vistos nas forças constantes, passo de 5°, com contagem), `amb`
  (direção cai perto do eixo Y sob a convenção atual ⇒ sinal fixo +1) e `inv` (inversão do FFB ligada).
- Painel (cartão Force Feedback): mostra "Direções vistas: 90°×N · 270°×M", o estado da inversão e, com `zero=leste` e
  direção ≈ 90°/270°, um aviso para testar `north`. Nenhum padrão foi alterado.
- `vjoy_protocol.direction_ambiguous` (mesma regra de `direction_sign`).
- Testes: `tests/test_ffb_invert.py` (+6) — inverter é negar qualquer valor/sinal (incl. escala 255 e *stretch*).

# v0.9.4 — Corrige "o volante pesa sempre para o mesmo lado" (zero polar padrão = north)

- **Causa**: o padrão `ffb.polar_zero = "east"` (nunca provado) tratava 90° e 270° como direção "ambígua" e fixava o sinal em +1.
  O Windows entrega a força do FH4 como direção DirectInput (9000 = 89°, leste = +X; 270° = oeste = −X) e magnitude ≥ 0:
  os dois lados caíam em +1, então a força era sempre do mesmo lado e *Inverter* só trocava esse lado fixo.
- **Correção**: o padrão agora é `north` (convenção DirectInput, documentada pela Microsoft). `config.json` antigo com `east` é
  migrado uma vez (`cfg_version` 2) — também na recarga a quente e ao carregar perfis. Quem escolher `east` depois continua com `east`.
- Painel: o aviso de direção ambígua só sugere `north` quando o padrão antigo está ativo; telemetria ganhou `zero`.
- Testes: `tests/test_ffb_race_sign.py` (+8) simula uma volta com a config padrão (lado só na direção; lado só no sinal da
  magnitude; os dois juntos; inverter espelha a volta) e a migração do `config.json`.

# v0.9.5 — Corrige o sinal perdido do vJoy (a causa real do "só um lado")

- **Causa (provada por capturas reais, Assetto Corsa Rally e Wreckfest 2)**: o vJoy entrega `Magnitude` int16 SEM sinal.
  Força positiva chega como 0…10000; força negativa chega como 55536…65535 (= 65536 + valor), nunca como número negativo
  (≈ metade dos pacotes nos dois logs, nada entre 10001 e 55535). O tradutor lia 65429 como "força enorme positiva" (e ainda
  trocava a escala para 32767) ⇒ sempre o mesmo lado.
- **Correção**: `vjoy_protocol.s16` restaura o sinal (32768…65535 → −65536); aplicado em constante, rampa (start/end),
  offset periódico e centro/coeficientes de condição no `ffb_receiver`.
- A v0.9.4 (`polar_zero = north`) NÃO era a causa: os dois jogos mandam direção ≈ +X fixa e o lado vem da magnitude.
  Mantida por ser a convenção documentada do DirectInput.
- Testes: `tests/test_ffb_receiver_sign.py` (valores reais dos logs).

# v0.9.6 — Ícone no exe/janela/bandeja e BATs corrigidos

- `3-compilar_gtforce_bridge.bat`: passa `--icon GTFB.ico` ao PyInstaller (ícone do .exe) e `--add-data` (arquivo junto do app);
  aborta se `GTFB.ico` faltar. Corrigido: chamava `PREPARAR_GTForceBridge.bat`, que não existe (o arquivo é `1-PREPARAR_...`),
  então o preparo automático do `.venv` falhava.
- Janela (`iconbitmap`) e bandeja usam `GTFB.ico` (`paths.resource_path` acha o arquivo no exe e no código-fonte); a bandeja
  mantém a bolinha de estado. `GTFB.ico` agora tem 16/24/32/48/64/128/256 px (antes só 256).
- `GTForceBridge.spec` atualizado (ícone; sem caminho `D:/` fixo; sem UPX). Mensagens/README apontam para os nomes `1-`/`2-`/`3-`.
- Testes: `tests/test_icon.py`.

