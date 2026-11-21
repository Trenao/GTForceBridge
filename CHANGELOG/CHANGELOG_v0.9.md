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
