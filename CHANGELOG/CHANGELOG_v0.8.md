# v0.8 — auditoria do FFB contra fontes oficiais + painel FFB na GUI

Fontes: `vjoyinterface.h` (vJoy 2.x), USB PID 1.0 (usb.org), documentação DirectInput (Microsoft) e SDL2 Haptic.
Detalhe de cada valor conferido/não conferido: `FFB_REFERENCIAS.md`.

## Corrigido (tradutor)
- **Duração, loops e atraso do jogo eram ignorados.** Todos os efeitos SDL eram infinitos, então um efeito com
  duração finita (impacto, zebra) só parava se o jogo mandasse STOP — e o DirectInput não manda quando o prazo acaba.
  Agora: `Duration` (ms; 0xFFFF e 0 = infinito, conforme o header), `LoopCount` (255 = infinito, PID 1.0) e
  `StartDelay` são respeitados. Desligável: `ffb.honor_duration=false`.
- **Rampa** usava duração infinita (não rampava). PID 1.0: rampa não pode ser infinita; agora usa `Duration` do jogo.
- **Direção cartesiana** (`Polar=0`) era lida como polar: `DirX` negativo (complemento de 2) virava +máximo e o lado
  esquerdo se perdia. Agora o sinal vem de `DirX` (header: positivo = direita).
- **Convenção do zero polar**: o PID 1.0 não define; o DirectInput define 0°=norte, 90°=leste=+X. Nova opção
  `ffb.polar_zero` (`east` = comportamento antigo, padrão; `north` = DirectInput). Mudar o padrão exige um `--ffb-dump`
  real do FH4 — ver `FFB_REFERENCIAS.md`.

## Diagnóstico
- `--ffb-dump`: mostra ângulo em graus com o lado X sob as duas convenções, `DirX`, duração (ms/infinita) e atraso.
- `--list` e GUI: capacidades reportadas pelo driver (efeitos, nº de efeitos na memória, simultâneos, eixos).

## GUI (aba Force Feedback)
- Painel **ao vivo**: força constante enviada (barra −100…+100%), efeitos tocando, capacidades do volante.
- Controles **avançados**: atualizações/s, suavização, zona morta, escala forçada, modo de direção, zero polar,
  respeitar duração, desligar autocenter; valores medidos pela autocal visíveis.
- Telemetria da ponte ganhou `ffb` e `caps` (a GUI antiga continua funcionando com telemetria sem esses campos).

## Testes
104 (eram 86): `test_ffb_duration.py` (13), `test_gui_ffb_tab.py` (5; widgets falsos, sem tkinter), autocal.
A GUI não pôde ser renderizada neste ambiente (sem tkinter): validar visualmente no Windows.
