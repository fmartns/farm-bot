# FARM BOT

Automação visual (OpenCV + captura de tela) de um minigame de coleta
baseado em círculo/arco, para **uso pessoal**. O bot não lê memória do
processo do jogo nem faz qualquer tipo de injeção: ele apenas captura a
região da tela onde o minigame aparece, reconhece o número e a zona-alvo
por visão computacional, e envia a tecla correspondente via `pydirectinput`.

> Avalie as regras do servidor/jogo antes de usar. Este projeto é fornecido
> como está, sem garantias, e o uso é de responsabilidade de quem o executa.

## Arquitetura

O pacote `farm_bot/` é dividido por responsabilidade:

| Módulo | Responsabilidade |
|---|---|
| `config.py` | Constantes de calibração e valores padrão (sem lógica). |
| `geometry.py` | Matemática angular genérica (diferença circular, médias, perfis, runs). |
| `ring.py` | Localiza o círculo do minigame na tela e extrai os perfis angulares (alvo/progresso). |
| `digit_detection.py` | Extrai e classifica o dígito central do círculo. |
| `templates.py` | Templates de dígitos (embutidos em base64) e o classificador por IoU. |
| `target.py` | Detecção/consenso da zona-alvo colorida e estimativa de velocidade do arco. |
| `state.py` | Máquina de estados de uma rodada: liga as peças acima para decidir *quando* apertar. |
| `prompts.py` | Detecção visual do prompt "E" e do aviso de bloqueio/cooldown do jogo. |
| `input_control.py` | Foco de janela e leitura de teclas no Windows. |
| `recorder.py` | Grava frames + estado de cada rodada em disco, para diagnóstico offline. |
| `debug_view.py` | Desenho da janela de depuração (`--show`). |
| `overlay.py` | Aviso sempre visível no canto da tela ("BOT LIGADO"/"BOT DESLIGADO"). |
| `runner.py` | Loop principal: modo ao vivo (`run_live`) e modo replay de vídeo (`run_video`). |
| `gui.py` | Janela (Tkinter) de seleção de opções, usada quando o programa é aberto sem argumentos. |
| `cli.py` | Parser de linha de comando e ponto de entrada (`python -m farm_bot.cli`). |

`farm_bot.py`, na raiz, é um atalho fino para `farm_bot.cli:main` (equivalente
a `python -m farm_bot.cli`).

Código de versões anteriores (pré-modularização) fica em [`legacy/`](legacy/),
mantido só como referência histórica — não é importado pelo pacote.

## Instalação

Requer Python 3.9+ no Windows (o modo ao vivo usa APIs do Windows; o modo
`--video` funciona em qualquer plataforma).

```powershell
pip install -e .
```

Para desenvolvimento (testes, lint, empacotamento em `.exe`):

```powershell
pip install -e ".[dev]"
```

## Uso

### Janela de seleção (modo mais simples)

Rodar sem nenhum argumento abre uma janela (Tkinter, já incluído no Python —
sem dependência extra; nenhum console é aberto junto). Por padrão ela mostra
só o essencial — número do monitor e um checkbox "Modo teste" — já pronta
para apertar **Iniciar** e jogar de verdade (sem dry-run, sem janela de
depuração). Um botão **Avançado** revela o resto: testar com vídeo gravado,
janela de depuração, gravação de diagnóstico, ajustes de posição, etc. A
saída do bot aparece na própria janela.

```powershell
python -m farm_bot.cli
```

(ou simplesmente dando duplo-clique em `FARM BOT.exe`, se você empacotou o
projeto — veja [`BUILD.md`](BUILD.md)). `F12` pausa/retoma e `F10` encerra
funcionam direto no teclado mesmo com a janela aberta; ela também tem um
botão "Parar (envia F10)" para quem preferir. Por padrão aparece também um
aviso no canto superior direito da tela ("BOT LIGADO"/"BOT DESLIGADO"),
indicando se o bot está ativo — desligue em "Mostrar aviso na tela" (dentro
de Avançado) se não quiser.

### Linha de comando (modo avançado)

Testar em um vídeo gravado, sem enviar teclas:

```powershell
python -m farm_bot.cli --video caminho\para\o\video.mp4 --show
```

Rodar ao vivo contra a tela (ajuste `--monitor` para o índice correto):

```powershell
python -m farm_bot.cli --monitor 1 --show
```

Sem janela de depuração:

```powershell
python -m farm_bot.cli --monitor 1
```

Teclas durante o modo ao vivo (apenas `F10`/`F12`: as demais teclas de função
costumam já ter uso dentro do próprio jogo):

- `F12` pausa/retoma
- `F10` encerra

Por padrão, um aviso fica sobreposto no canto superior direito da tela
("BOT LIGADO" em verde / "BOT DESLIGADO" em vermelho) indicando o estado
atual. Use `--no-overlay` para desativar.

Diagnóstico (salva o recorte de cada rodada e o estado interno quadro a
quadro em uma pasta):

```powershell
python -m farm_bot.cli --monitor 1 --show --record-rounds rodadas --save-captures
```

A lista completa de opções (`--hit-distance`, `--target-lock-votes`,
`--cooldown-seconds`, etc.) está em `python -m farm_bot.cli --help`; cada uma
tem uma constante correspondente em `config.py` quando é um valor calibrado
em vez de um comportamento.

## Testes e lint

```powershell
pytest
ruff check .
```

Os testes cobrem a lógica pura e isolável (`geometry`, `target`,
`digit_detection`, `templates`, `recorder`, e o parser da CLI). `state.py` e
`runner.py` concentram a lógica de máquina de estados e o loop de captura ao
vivo — ambos dependem fortemente de frames reais do jogo e de hardware
(tela, teclado), então não têm testes unitários diretos; eles são validados
na prática com `--video` contra gravações reais e com `--dry-run --show` ao
vivo.

## Solução de problemas

- **"Monitor N inválido"**: rode sem gravar nada primeiro; a mensagem lista
  os monitores detectados e seus índices.
- **"jogo sem foco; tecla NÃO enviada"**: clique na janela do jogo antes de
  rodar sem `--dry-run` — por segurança, o bot nunca envia teclas para uma
  janela diferente da do jogo.
- **"alvo não foi travado" / "direção do arco não foi travada"**: a zona ou
  a direção não acumularam votos suficientes antes da rodada acabar; ajuste
  `--target-lock-votes` / `--min-target-width`, ou grave com
  `--record-rounds` para inspecionar quadro a quadro.
- **Número errado é lido**: rode com `--save-captures` e compare os PNGs
  salvos em `debug_captures/` com os templates em `templates.py`.
- **Empacotar em `.exe`**: veja [`BUILD.md`](BUILD.md).

## Empacotamento

Instruções completas de build com PyInstaller (gerando um `.exe` para rodar
em outro Windows sem instalar Python) estão em [`BUILD.md`](BUILD.md).

## Licença

[MIT](LICENSE).
