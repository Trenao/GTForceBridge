# FFB — o que foi conferido, contra quê

## Hardware (GT Force LPRC-10000)
- É o Logitech **WingMan Formula GP/Force GP** com outra cor de empunhadura (Wikipedia, "Gran Turismo official steering
  wheel"); bate com o log: `WingMan Formula Force GP VID=0x046D PID=0xC293`. Curso ~200° (modo de compatibilidade).
- **Não achei documentação oficial da Logitech** com a lista de efeitos/slots deste modelo (o PDF do manual só cobre
  instalação). O que se sabe vem do driver: use `--list`/aba FFB para ler efeitos suportados, nº de efeitos na memória e
  simultâneos direto do DirectInput (via SDL). Nada disso é presumido no código.
- Relatos da comunidade (não oficiais) dizem que volantes Logitech antigos têm poucos "slots" de força e sem
  temporização própria; por isso o tradutor mantém **um efeito SDL por tipo** e faz duração/atraso em software.

## vJoy (`vjoyinterface.h`, vJoy 2.x) — oficial
| Item | Valor no header | No projeto |
|---|---|---|
| `Duration` | WORD, ms, **0xFFFF = infinito** | respeitado (v0.8) |
| `Direction` (Polar=1) | 0x0000–0x7FFF = 0–360° | normalizado p/ 0–255 |
| `DirX` (Polar=0) | positivo = direita, negativo em complemento de 2 | usado p/ o sinal (v0.8) |
| Constante / rampa | −10000…10000 | escala 10000 (auto 32767) |
| Condição (offset/coef.) | −10000…10000; saturação 0…10000 | mapeado p/ SDL |
| Condição `DeadBand` | comentário diz 0…1000 (outros 0…10000) | **dúvida do header**; `--ffb-dump` resolve |
| Periódico | Magnitude 0…10000, Offset ±10000, Phase 0…35999, Period 0…32767 | repassado ao SDL |
| Envelope (`FFB_EFF_ENVLP`) | Attack/Fade level 0…10000, tempos em ms | **não aplicado** (pendente) |
| Op / Ctrl | START=1 SOLO=2 STOP=3; ENACT..DEVCONT = 1..6 | conferido (bate com PID 1.0) |

## USB PID 1.0 (usb.org) — oficial
- Selectores de Device Control (1–6) e Effect Operation (1–3) **conferem** com o código.
- `Loop Count` 255 = infinito → respeitado. Ramp **não** pode ter duração infinita → respeitado.
- O PID 1.0 **não define**: o zero do ângulo polar, o sinal de magnitude de força constante, nem o valor numérico de
  INFINITE (é "o máximo da faixa"). Por isso `polar_zero` é opção e o 0xFFFF vem do header do vJoy.
- Gain: faixa depende do descritor (exemplo da spec usa 0–127; vJoy entrega BYTE). O projeto usa /255 e trata 0 como
  "não informado" (1.0). **Não conferido**: se o FH4 manda Gain=0 de propósito, o efeito tocaria com força cheia.

## DirectInput / SDL (Microsoft, libsdl.org) — oficial
- Magnitude constante −10000…10000; magnitude negativa inverte a força. ✔
- Condições: força = coef × (posição − (offset ± deadband)); saturação ≥ 0. ✔
- Direção polar: centésimos de grau **a partir do norte (0,−1), no sentido horário; 90° = leste = +X**. Isto é do
  DirectInput; a conversão que o driver HID PID do Windows faz para o campo do vJoy não está documentada.
  → `ffb.polar_zero` (padrão `east` = como era). Para decidir: `--ffb-dump` com o FH4 e ver `dir=` de efeitos que o
  jogo manda para esquerda e direita.
- SDL2 não tem onda quadrada: `SQUARE` vira seno (aproximação, já documentada).

## Pendências (nada inventado)
1. `--ffb-dump` real do FH4 (zero polar, Gain, DeadBand 0…1000 vs 10000).
2. Envelope (attack/fade) do `FFB_EFF_ENVLP`: decodificar e aplicar.
3. Assimetria medida na autocal (≈2× entre sentidos): compensação por sentido ainda não implementada.
