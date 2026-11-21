# v0.7 — autocalibração: teste de força constante refeito

## Problema (medido no hardware, GT Force / WingMan Formula Force GP, PID 0xC293)
- Constante +15% levou o volante ao batente esquerdo (−0.99); spring com offset +50% foi para a direita (+0.52).
  Ou seja, **o sinal da constante é oposto ao do eixo** neste volante, e o spring não diz nada sobre ele.
- A v0.6 derivava `invert` do spring → sugeriria `invert=False` e, no jogo, a força de curva empurraria
  o volante para fora do centro.
- Os testes de constante também eram inválidos: sem força restauradora o volante só anda até o batente, cada teste
  começava de onde o anterior parou, e a "mediana final" não mede nada (daí `SATURADO`, `span` 0.4–0.6 etc.).
- O teste de deadband herdava o mesmo problema (resposta só num sentido, +0.21 / +0.02).

## Mudanças (`autocal.py`)
- `_recenter()`: spring forte (offset 0) leva o volante ao centro e espera estabilizar antes de cada teste de
  constante e de cada repetição do deadband.
- `_measure_const_direction()`: janela de 1 s a partir do centro; mede deslocamento **assinado** e velocidade
  inicial; encerra perto do batente. Bater no batente não invalida mais o teste.
- `invert` vem da **constante** (+ deve ir ao lado positivo e − ao negativo). Se +15%/−15% não moverem, usa o +25%.
  Spring continua só para `center_offset` e retorno ao centro; a GUI/relatório mostra se spring e constante concordam.
- `constant_scale` **não é mais derivado** (a posição final não dá escala confiável); fica com o valor do usuário.
- Simetria passa a ser razão das velocidades iniciais (−/+).
- Avisos novos: constante não moveu o volante, ou foi para o mesmo lado nos dois sentidos.
- Testes: `tests/test_autocal.py` (caso real medido, fallback 25%, sem movimento). 86 testes OK.

## Não validado
Rodar `--ffb-autocal` de novo no Windows. Esperado: `invert: True`, `const_+15` negativo / `const_-15` positivo,
deadband com resposta nos dois sentidos. Se `const_+15` não mover, o relatório avisa e o 25% decide.

## Ajuste pós-teste real (deadband)
- Rodada real: invert=True OK, mas deadband "0.010" tinha deslocamento 0.0375/0.0385 igual nos dois sentidos (ruído).
  Agora exige |Δ assinado| > 0.08 e sentidos opostos.
- Achado: assimetria da constante (vel0 −0.61 vs +0.31, razão 0.51). Não compensada ainda.
