# Empacotamento do FARM BOT em .exe (PyInstaller)

## Bug corrigido antes do build

`farm_bot/cli.py` importava apenas parte das constantes de `farm_bot/config.py`,
mas usava `DEFAULT_HIT_DISTANCE`, `DEFAULT_ARM_DISTANCE`, `DEFAULT_MAX_HIT_OVERSHOOT`,
`DEFAULT_PROGRESS_THRESHOLD` e `DEFAULT_TARGET_THRESHOLD` como valores padrão de
argumentos da CLI. Isso causava `NameError` ao chamar `build_parser()` — ou seja,
o programa já quebrava com `python -m farm_bot.cli --help`, independente de
qualquer empacotamento. Os imports faltantes foram adicionados; nada na lógica
do bot foi alterado.

## Recursos do projeto (sem dependências externas de arquivo)

- Os templates de dígitos ficam embutidos como base64 em `farm_bot/templates.py` —
  não há imagens/arquivos externos para incluir no pacote.
- `recorder.py` e `runner.py` só escrevem em pastas relativas ao diretório de
  trabalho atual (`rodadas/`, `debug_captures/`), criadas em runtime. Nada disso
  precisa ser empacotado dentro do `.exe`.
- Logo, o build não precisa de `--add-data`.

## Pré-requisitos

```powershell
pip install -e ".[dev]"
```

Isso instala o projeto (`pyproject.toml`) junto com `pyinstaller`, `pytest` e
`ruff`. As dependências de runtime (`numpy`, `opencv-python`, `mss`,
`pydirectinput`) são detectadas automaticamente pelo PyInstaller (há hooks
prontos para `cv2` e `numpy`); `mss` e `pydirectinput` foram adicionados
explicitamente em `hiddenimports` no `.spec` porque são importados dentro de
função (import tardio em `runner.py`), não no topo do módulo.

## Build

Um `.spec` já está em `farm_bot.spec` na raiz do projeto, com ponto de entrada
`farm_bot.py` (equivalente a `python -m farm_bot.cli`). Para gerar o executável:

```powershell
cd "C:\Users\fmart\OneDrive\Área de Trabalho\farm_bot_package_v9"
python -m PyInstaller farm_bot.spec --noconfirm
```

Resultado: `dist\FARM BOT\FARM BOT.exe` + pasta `dist\FARM BOT\_internal\` com
as DLLs/dependências. É um build **onedir** (não onefile): para distribuir,
copie a pasta `dist\FARM BOT\` inteira para o outro computador — o `.exe` não
funciona isolado sem o `_internal`.

Por que onedir e não onefile: onefile extrai tudo para uma pasta temporária a
cada execução, o que é mais lento para um programa que já faz captura de tela
em alta frequência (`--poll-hz`). Onedir evita essa extração repetida. Pode ser
trocado para onefile se preferir um único arquivo — basta mudar `EXE(...,
exclude_binaries=True, ...)` + `COLLECT(...)` por um único `EXE(..., a.binaries,
a.datas, ...)` sem `exclude_binaries` e sem bloco `COLLECT`.

## Teste de inicialização

Executado e confirmado nesta máquina:

```powershell
dist\"FARM BOT"\"FARM BOT.exe" --help
```

exibe a ajuda normalmente. Também foi testado `--video` apontando para um PNG
(erro esperado de decodificação, pois não é um vídeo real) para confirmar que
`opencv-python`/`numpy`/FFmpeg embutidos carregam sem erro de DLL ou import
faltando.

Rodando `FARM BOT.exe` **sem nenhum argumento** (ex.: duplo-clique), abre a
janela de seleção de opções (`farm_bot/gui.py`, Tkinter — já embutido no
Python, PyInstaller inclui automaticamente), sem nenhuma janela de console
junto (build "windowed": `console=False` no `.spec`, bootloader `runw.exe`).
Isso foi confirmado tanto visualmente quanto checando que o processo não tem
nenhum `cmd`/`conhost` filho. Como esse modo não tem console anexado,
`sys.stdout`/`sys.stderr` chegam como `None`; `farm_bot/cli.py` troca por um
destino vazio antes de qualquer `print()` para não derrubar o programa
(`--help`/`--video` continuam funcionando quando chamados de um terminal que
já redireciona a saída, como em CI; quando chamados por duplo-clique sem
redirecionamento nenhum, a saída dessas duas flags fica apenas invisível —
use a janela ou `python -m farm_bot.cli` para ver os prints).

O modo ao vivo (`--monitor`) também foi testado de fato rodando (com
`--dry-run`, sem enviar teclas): o aviso sobreposto no canto da tela
("BOT LIGADO"/"BOT DESLIGADO", `farm_bot/overlay.py`) apareceu corretamente
sobre a tela, sem travar nem derrubar o processo. Esse overlay usa a API do
Windows diretamente (ctypes/user32), e não Tkinter — uma primeira versão com
Tkinter rodando numa thread separada derrubava o processo com uma exceção
fatal do Windows nesta máquina.

Não foi testado o modo ao vivo de fato jogando (`--monitor` apertando teclas
reais) nem a janela de depuração do OpenCV (`--show`) com um jogo de verdade,
pois dependem de uma sessão de jogo e de supervisão interativa no computador
de destino.

## Distribuição

1. Copie a pasta `dist\FARM BOT\` inteira (não só o `.exe`) para o computador
   de destino.
2. Nenhuma instalação de Python é necessária no destino.
3. Rode `FARM BOT.exe` (ou `FARM BOT.exe --help`) de dentro dessa pasta — ou
   crie um atalho apontando para `caminho\dist\FARM BOT\FARM BOT.exe`,
   mantendo-o dentro da pasta.

## Não implementado (fora do escopo pedido)

Instalador, auto-update e qualquer mecanismo de ocultação/evasão não foram
implementados — não foram solicitados e estão fora do escopo deste pacote.
