# v0.4 — o que mudou

## Corrigido
- FFB: parâmetros do jogo esperavam 100 ms de "silêncio" antes de ir ao volante; com fluxo contínuo de força
  (o normal) a força nunca chegava ao motor. Agora são aplicados na hora.
- FFB: coeficientes de mola/amortecedor podiam ser trocados entre si quando o jogo alternava os dois.
- FFB: forças pequenas (ex.: 200 de 10000) eram lidas como escala de 8 bits e amplificadas ~39x. Não se presume mais 8 bits.
- FFB: `min_effective_magnitude`/`min_effect_mode` (gravados pela autocal) eram ignorados; agora aplicados (stretch).
- Loop: falha do vJoy (SetAxis) derrubava a ponte; agora loga e readquire o device.
- Timer: `timeBeginPeriod` nunca era desfeito (agora pareado com `timeEndPeriod`); `winutil.py` reescrito (o antigo não funcionava).
- `config.json`: chaves de versões antigas eram ignoradas em silêncio; agora são listadas no log.
- Testes: `test_ffb_translator` (12) não rodava; `test_all` estava obsoleto e foi removido. Suíte: 50 testes OK.

## Novo
- `ffb`: `update_hz`, `slew_per_sec`, `const_deadzone_pct`, `magnitude_scale`, `disable_autocenter`; raiz: `high_priority`.
- `controls.py` / `sinks.py`: fronteira entrada → saída (base para Xbox/teclado).

## Removido (código morto, nunca usado pelo programa)
`ffb_mixer.py`, `ffb_model.py`, `haptic_out.py`, `ffb_decode.py`, `tests/test_all.py`
(apague-os da sua pasta ao copiar esta versão por cima).
