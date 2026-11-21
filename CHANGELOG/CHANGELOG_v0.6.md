# v0.6 — auditoria de GUI, autocalibração e FFB

## FFB (conferido com vjoyinterface.h / public.h do vJoy 2.2.x, PID 1.0 e docs do SDL2)
- **Corrigido:** `FFB_EFF_REPORT` não tinha `StartDelay` nem `AxesEnabledDirection`, e `Direction/DirY` eram BYTE (no 2.2.x são WORD).
  Com a struct errada, `Gain` e `Direction` eram lidos de bytes errados. Agora há layout novo (2.2.x) e legado (2.1.x), escolhido
  pela presença de `Ffb_h_EffectBlockIndex` na DLL. Direção polar normalizada (0x7FFF = 360°; legado 255 = 360°).
- **Corrigido:** fase de efeitos periódicos agora é repassada (centésimos de grau, igual ao SDL); antes era sempre 0.
- **Corrigido:** nota da GUI dizia que o vJoy não repassa envelope; o header expõe `FFB_EFF_ENVLP`. A ponte é que ainda não o aplica.
- Confirmados sem mudança: tipos/valores `FFBEType`, `FFBPType`, `FFBOP`, `FFB_CTRL`; escalas ±10000; coeficientes/saturação/deadband/center do SDL.
- Pendências/dúvidas (não inventadas): SDL2 não tem onda quadrada (usa SENOIDE); comentário do header diz DeadBand 0–1000 (os demais 0–10000);
  Gain: faixa depende do descriptor do vJoy (a ponte usa /255). `--ffb-dump` no Windows mostra os valores reais.

## Autocalibração
- Perfil guardado por PID e aplicado ao iniciar a ponte (já funcionava via CLI); pela GUI ia para a chave `"unknown"` e nunca era usado. Corrigido (PID vem do relatório).
- `center_offset` era somado ao centro do spring (compensava ao contrário); agora é subtraído.
- A sugestão só contém chaves MEDIDAS; `condition_scale`/`periodic_scale` nunca são tocados e valores não medidos não sobrescrevem os do usuário.
- Lista de chaves única em `autocal_profile.py` (bridge, CLI e GUI). Salvar FFB na GUI sincroniza `constant_scale`/`invert` no perfil.
- Precedência: DEFAULT < config.json < perfil do PID (aplicado ao iniciar).
- Testes novos: `tests/test_autocal.py`.

## GUI
- Log do sistema sempre visível; abas com rolagem; janela limitada ao tamanho da tela; botões da autocalibração visíveis;
  sliders FFB com valor; linha de ações cabe em 980 px (checkboxes em 2ª linha, "Perfil:" na ordem certa); colunas de Alcance/HidHide sem corte.
