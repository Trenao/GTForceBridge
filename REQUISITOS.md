# Requisitos — GTForce Bridge

Para usar o GTForce Bridge você precisa de **dois drivers instalados no Windows**: **vJoy** e **HidHide**. Eles **não** vêm junto com o programa; cada um tem sua licença e deve ser baixado da fonte original.

| Componente | Para que serve | Obrigatório? |
|---|---|---|
| **vJoy** (fork njz3 2.2.x) | Joystick virtual que o jogo enxerga e por onde chega o force feedback | **Sim** |
| **HidHide** | Esconde o volante físico do jogo, para ele ver só o vJoy | Recomendado |
| ViGEmBus | Só para a saída de controle Xbox 360 virtual | Opcional |

> Instalar driver exige **administrador** e, em geral, **reiniciar o Windows** no final.

---

## 1. vJoy (fork njz3 2.2.x)

- **Download:** https://github.com/njz3/vJoy/releases/tag/v2.2.1.1
- Use este fork. A **vJoy 2.1.8 original não é suportada** pelo programa.

### Instalar pela linha de comando (PowerShell)

Não achei pacote do fork no winget. Abra o **PowerShell** e rode:

```powershell
$r = Invoke-RestMethod 'https://api.github.com/repos/njz3/vJoy/releases/tags/v2.2.1.1' -Headers @{'User-Agent'='gtforce'}
$a = $r.assets | Where-Object { $_.name -like '*.exe' } | Select-Object -First 1
$o = Join-Path $env:TEMP $a.name
Invoke-WebRequest $a.browser_download_url -OutFile $o
Start-Process $o -Verb RunAs -Wait
```

O instalador abre em **modo normal** (de propósito, não silencioso): há relatos de instalação travando ou falhando no Windows 11, e você precisa ver a janela. Se o comando falhar, baixe o `.exe` pelo link acima e instale manualmente.

### Configurar o vJoy (obrigatório, depois de instalar)

Abra o **vJoyConf** e deixe assim:

- **Device 1**
- Eixos: **X**, **RZ** e **Slider0 (SL0)**
- **32 botões**
- **Todos os efeitos de Force Feedback marcados**

Clique em **Apply** e **reinicie o Windows**.

---

## 2. HidHide

- **Download:** https://github.com/nefarius/HidHide/releases

### Instalar pela linha de comando (CMD ou PowerShell)

```cmd
winget install --id Nefarius.HidHide -e --silent --accept-package-agreements --accept-source-agreements
```

Rode em um terminal **como administrador**. Se preferir, o `winget` sem `--silent` mostra a janela do instalador.

### Depois de instalar

1. Reinicie o Windows.
2. Abra o `GTForceBridge.exe` e vá na aba **HidHide**.
3. Clique em **Autorizar esta ponte**.
4. Clique em **Ocultar volante GT Force**.

A autorização vale para o **caminho** do programa. Se você mover a pasta, autorize de novo.

---

## 3. ViGEmBus (opcional)

Só necessário se for usar a saída de **controle Xbox 360 virtual**.

- **Download:** https://github.com/nefarius/ViGEmBus/releases
- No modo código, instale também o pacote Python: `pip install -r requirements-xbox.txt`.

---

## Instalar tudo de uma vez (rodando do código)

Se você usa o projeto pelo código-fonte, o `1-PREPARAR_GTForceBridge.bat` faz isso:

```cmd
1-PREPARAR_GTForceBridge.bat
```

Ele cria o ambiente Python, detecta se **HidHide** e **vJoy** estão instalados e **oferece instalar** (pergunta S/N, com pedido de administrador). Para pular essa parte: `1-PREPARAR_GTForceBridge.bat --sem-drivers`.

---

## Como saber se está instalado

No CMD:

```cmd
dir "%ProgramFiles%\vJoy\x64\vJoyInterface.dll"
dir "%ProgramFiles%\Nefarius Software Solutions\HidHide\x64\HidHideCLI.exe"
```

Se os dois arquivos aparecerem, os drivers estão no lugar. Depois, abra o programa e clique em **Detectar volante**: o GT Force deve aparecer na lista.

---

## Requisitos do sistema

- Windows, 64 bits
- Rodando o `.exe`: nada além dos drivers acima
- Rodando do código: Python 3.10+ **64 bits**, com `tkinter`

---

Criado por **Sthevan P.K. (oTrenao)** · MIT
