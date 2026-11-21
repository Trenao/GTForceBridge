# v0.5 — saídas de teclado e Xbox

## Novo
- `outputs.keyboard`: direção/pedais/botões -> teclas (SendInput por scancode), com histerese. Teclas sempre soltas
  ao desligar, perder o volante ou encerrar (testado no loop real).
- `outputs.xbox`: controle Xbox 360 virtual (direção->LX, acelerador->RT, freio->LT, botões configuráveis) via
  `vgamepad`/ViGEm. Dependência opcional: `requirements-xbox.txt`.
- `outputs.vjoy.enabled`: permite desligar o vJoy (usar só teclado ou só Xbox).
- `mapping.py`: fontes, histerese e tabela de teclas.

## Testes
- 74 testes OK (eram 50). Inclui: loop real com teclado (tecla apertada, solta ao perder o volante e ao encerrar),
  layout da struct `INPUT` do SendInput (40 bytes em 64 bits), adaptador `vgamepad` contra a API conferida no código-fonte.
- O harness `test_bridge_loop` travava quando um assert do cenário falhava; agora sempre encerra o loop.

## Não verificado (precisa do Windows)
SendInput num jogo real, driver ViGEmBus + vgamepad reais, GUI.
