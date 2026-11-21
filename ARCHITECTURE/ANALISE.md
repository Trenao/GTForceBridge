# Análise geral — gtforce_bridge v0.9.4

Base: ~3 250 linhas no núcleo + ~2 400 na GUI; 118 testes (todos passam com `pysdl2` instalado).
Cada item abaixo diz **o que foi verificado** e o que ainda depende de dado real. Nada marcado como feito sem teste.

## 1. FFB — a linha azul só desce (investigado nesta versão)
**Não é desenho da GUI.** A GUI plota `snapshot()["const"]`, que é o nível da força constante *já com sinal* enviado ao
SDL (`ffb_translator.build`). Se ele nunca é positivo, o sinal que sai do tradutor nunca é positivo. O sinal é
`sinal(magnitude do jogo) × sinal(direção do efeito)`. Há três causas possíveis, e só os dados distinguem:

| # | Causa | Como aparece agora | O que fazer |
|---|---|---|---|
| A | O jogo manda magnitude nos dois sinais e a regra de direção achata um lado | Painel: linha cinza (jogo) vai pros dois lados, azul só para um | Já há opção: `ffb.polar_zero` |
| B | O jogo codifica o lado só na direção (90°/270°, magnitude sempre ≥ 0). Com `zero=leste` (padrão) 90° e 270° viram "indefinido" (+1) e o lado se perde. Com `zero=norte` (convenção DirectInput, documentada em `FFB_REFERENCIAS.md`) separam | `--ffb-dump`: "só uma convenção produz os dois lados" | Trocar para `north` na aba Force Feedback |
| C | O jogo realmente só manda um lado (ou o driver HID PID entrega assim) | Cinza também de um lado só; dump: "as duas convenções dão um lado só" | Nada a corrigir na ponte; conferir com `--ffb-test` que o motor puxa nos dois sentidos (ele aplica ±12000) |

**Como medir (2 min):** Ferramentas → *Capturar FFB do jogo*, entre numa corrida, vire para os dois lados, clique PARAR.
O log termina com o resumo "lados da força constante" (esquerda/direita sob cada convenção). Ou rode normal e observe o Painel.
Obs.: não mudei o padrão `east`: o `FFB_REFERENCIAS.md` já registra que isso exige captura real do FH4.

### v0.9.4 — causa encontrada e corrigida
Teste/AutoCal movem o volante nos dois lados (a cadeia SDL → motor está certa). Em corrida o sinal vinha fixo: magnitude ≥ 0
do jogo + direção ≈ 89° (leste DirectInput) e, no outro lado, ≈ 269°. Com `polar_zero = east`, `cos(89°) ≈ cos(269°) ≈ 0` ⇒
"ambíguo" ⇒ sinal +1 nos dois ⇒ sempre o mesmo lado; *Inverter* só espelhava esse lado (normal → esquerda, invertido → direita).
`tests/test_ffb_race_sign.py` reproduz isso com a config antiga e passa com `north` (padrão agora; config salva é migrada).
**Ainda não provado com o jogo**: que o FH4 envia 269° para o outro lado. Confirme em 1 volta: o Painel deve listar
"Direções vistas: 90°×N · 270°×M" e o azul ter os dois sinais. Se só aparecer 90° e o cinza continuar só positivo,
o jogo manda um lado só (vJoy/jogo, não a ponte) — aí envie o log do *Capturar FFB do jogo*.

### Evidência das capturas (21/11) e conclusão
- **Inverter já é negar qualquer valor** (`level = magnitude × sinal_da_direção × (−1 se invert)`); `tests/test_ffb_invert.py`
  trava isso para ±10000, ±1200, ±7 e para a escala 255 (255 → −32767; −12 → positivo). A imagem "normal" (azul 0…+100) e a
  "invertida" (azul 0…−100) são exatamente espelhos uma da outra: a inversão funciona.
- O que as capturas mostram é outra coisa: a linha **cinza (bruto do jogo) só existe no lado positivo** nas duas, e a direção
  fica em **polar 89°**. O sinal é preservado de ponta a ponta no código (`vJoy → receiver → translator`), e o header do
  vJoy documenta `Magnitude` como `LONG` de −10000…10000 (com sinal). Logo, o que chega ao tradutor, nessas janelas, é
  magnitude ≥ 0.
- 89° é ≈ 90° = "leste" **no padrão DirectInput** (0° = norte). Com `polar_zero = east` (padrão atual, ângulo a partir de +X) 89°
  seria quase perpendicular ao eixo do volante, ou seja, "indefinido", e o código fixa sinal +1 — e 269° (esquerda no
  DirectInput) também cairia em +1. Um jogo que manda força sobre o eixo X de um volante de 1 eixo usa 90°/270° nessa convenção;
  isso favorece `north`, mas **ainda não está provado** (falta ver 269° no jogo).
- **Teste de 10 s**: Force Feedback › *Zero da direção polar* = `north`. Dirija até o carro puxar para o outro lado:
  o Painel lista "Direções vistas" (ex.: 90°×N · 270°×M) e, com `north`, o azul passa a ter os dois sinais. Se aparecer
  só 90° e o cinza continuar só positivo, o jogo manda um lado só e não há o que corrigir na ponte.
- A autocal gravou `ffb.invert = true` para o seu PID (força positiva moveu o eixo no sentido negativo): é polaridade do
  motor, aplicada só a constante/rampa/offset periódico; molas/amortecedores não invertem (a autocal confirmou que a mola centra).
- Os 11% → 22% do Painel é o `min_effective_magnitude = 0.12` em modo *stretch* (0,12 + 0,88 × 0,11 ≈ 0,22), esperado.

## 2. FFB — pendências conhecidas (do próprio `FFB_REFERENCIAS.md`)
- Envelope (attack/fade) do `FFB_EFF_ENVLP` não é aplicado.
- `Gain=0` é tratado como "não informado" (força cheia); não se sabe se o FH4 manda 0 de propósito.
- `DeadBand` de condição: o header do vJoy é ambíguo (0…1000 vs 0…10000); o dump resolve.
- A autocal mediu assimetria ≈2× entre sentidos; compensação por sentido não implementada
  (relevante: pode ser parte do "só um lado" percebido, mas é outro fenômeno — força, não sinal).
- `SQUARE` vira seno (SDL2 não tem quadrada).

## 3. Robustez
- Feito: gravação de `config.json` pela GUI agora é atômica (temporário + `os.replace`); a ponte recarrega o arquivo a quente.
- Feito: `snapshot()` somava só o último efeito constante; agora soma todos (o motor soma) e limita a ±1.
- Testes: 3 módulos (`translator`, `autocal`, `duration`) exigem `pysdl2` já no import. Sem ele aparecem como erro.
  → Recomendo `requirements-dev.txt` (ou instruir `pip install -r requirements.txt` antes de testar).
- Nunca rodou em Windows real neste ambiente: registro (autostart), mutex de instância única, bandeja (`pystray`),
  vJoy DLL e HidHide só foram validados por simulação. Ver checklist na seção 6.
- Reconexão do volante e laço da ponte têm testes (`test_reconnect`, `test_bridge_loop`).

## 4. GUI / UX
- Feito (0.9): tema único, layout responsivo, painel ao vivo. (0.9.1): bandeja e autostart. (0.9.2): linha "jogo (bruto)".
- Pendente, **não implementado de propósito**: consciência de DPI no Windows. Hoje o Tk fica embaçado em 125–150 %
  de escala; ligar `SetProcessDpiAwareness` sem testar no Windows desalinharia os instrumentos (tamanhos em pixel).
  Precisa de teste no seu monitor antes.
- Páginas antigas (calibração, mapeamento…) herdaram o tema, mas seguem com layout em colunas fixas.

## 5. Empacotamento / organização
- `tk-0.1.0-py3-none-any.whl` na raiz: é o pacote PyPI "tk" (2019, não é o tkinter) e nada o referencia — provável
  sobra de `pip download`. Sugiro remover (não removi).
- Não há script de build do `.exe`. O código já trata `sys.frozen` (process_ctl e autostart), faltam o `.spec`/`.bat`
  do PyInstaller e um teste real do exe com `--tray`.
- `PLANO.md` é histórico (já avisa); a referência atual é `ARCHITECTURE.md`.

## 6. Checklist de validação no Windows (antes de confiar)
1. `python main.py --ffb-test` → sente puxões nos dois lados.
2. Capturar FFB do jogo (seção 1) e olhar o resumo de lados.
3. Sistema → *Iniciar com o Windows* → reiniciar → abre só na bandeja; *Iniciar a ponte automaticamente* sobe a ponte.
4. Abrir o programa de novo com ele na bandeja → aviso de instância única.
