"""Parser de linha de comando e ponto de entrada do programa."""

import argparse
import sys

from .config import (
    DEFAULT_ARM_DISTANCE,
    DEFAULT_CAP_DEGREES,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_E_RETRY_WAIT,
    DEFAULT_HIT_DISTANCE,
    DEFAULT_HIT_STREAK,
    DEFAULT_INPUT_LATENCY,
    DEFAULT_MAX_HIT_OVERSHOOT,
    DEFAULT_MAX_PROGRESS_SPEED,
    DEFAULT_PROGRESS_THRESHOLD,
    DEFAULT_TARGET_FRACTION,
    DEFAULT_TARGET_THRESHOLD,
)
from .runner import run_live, run_video


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automacao visual v9 do minigame de coleta.")

    parser.add_argument(
        "--video",
        help="Testa em um video gravado e NAO envia teclas.",
    )
    parser.add_argument(
        "--monitor",
        type=int,
        default=1,
        help="Monitor usado pelo jogo no modo ao vivo. Padrao: 1.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detecta normalmente, mas nao envia tecla.",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Abre uma janela pequena mostrando a deteccao.",
    )
    parser.add_argument(
        "--poll-hz",
        type=float,
        default=120.0,
        help="Frequencia de captura no modo ao vivo. Padrao: 120.",
    )
    parser.add_argument(
        "--hit-distance",
        type=float,
        default=DEFAULT_HIT_DISTANCE,
        help=f"Distancia para apertar, na escala 1078p. Padrao: {DEFAULT_HIT_DISTANCE}.",
    )
    parser.add_argument(
        "--arm-distance",
        type=float,
        default=DEFAULT_ARM_DISTANCE,
        help=f"Distancia minima que deve ser observada antes de armar. Padrao: {DEFAULT_ARM_DISTANCE}.",
    )
    parser.add_argument(
        "--hit-streak",
        type=int,
        default=DEFAULT_HIT_STREAK,
        help=f"Leituras consecutivas dentro do alvo antes de apertar. Padrao: {DEFAULT_HIT_STREAK}.",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.80,
        help="Confianca minima do reconhecimento do digito. Padrao: 0.80.",
    )
    parser.add_argument(
        "--min-margin",
        type=float,
        default=0.060,
        help="Diferenca minima entre o melhor e o segundo digito. Padrao: 0.060.",
    )
    parser.add_argument(
        "--save-captures",
        action="store_true",
        help="Salva o recorte de cada rodada em debug_captures para diagnosticar numero errado.",
    )
    parser.add_argument(
        "--min-target-width",
        type=float,
        default=12.0,
        help="Largura angular minima da zona-alvo final. Padrao: 12 graus.",
    )
    parser.add_argument(
        "--target-lock-votes",
        type=int,
        default=6,
        help="Quantidade minima de observacoes para formar o voto angular da zona. Padrao: 6.",
    )
    parser.add_argument(
        "--target-freeze-gap",
        type=float,
        default=32.0,
        help="Congela a geometria do alvo quando a ponta fica a esta distancia da entrada. Padrao: 32 graus.",
    )
    parser.add_argument(
        "--entry-tolerance",
        type=float,
        default=1.5,
        help="Tolerancia antes da entrada visual da zona para considerar contato. Padrao: 1.5 grau.",
    )
    parser.add_argument(
        "--merge-precontact",
        type=float,
        default=12.0,
        help="Distancia maxima antes da entrada para aceitar o salto visual de contato. Padrao: 12 graus.",
    )
    parser.add_argument(
        "--target-fraction",
        type=float,
        default=DEFAULT_TARGET_FRACTION,
        help=f"Posicao do disparo na zona logica (0=inicio, 0.5=centro). Padrao: {DEFAULT_TARGET_FRACTION}.",
    )
    parser.add_argument(
        "--cap-degrees",
        type=float,
        default=DEFAULT_CAP_DEGREES,
        help=f"Tamanho angular das pontas arredondadas do arco/zona. Padrao: {DEFAULT_CAP_DEGREES} graus.",
    )
    parser.add_argument(
        "--record-rounds",
        metavar="PASTA",
        help="Diagnostico: salva frames e estado interno de cada rodada nesta pasta.",
    )
    parser.add_argument(
        "--input-latency",
        type=float,
        default=DEFAULT_INPUT_LATENCY,
        help=f"Atraso estimado captura->jogo, compensado com a velocidade do arco. Padrao: {DEFAULT_INPUT_LATENCY}s.",
    )
    parser.add_argument(
        "--exit-margin",
        type=float,
        default=6.0,
        help="Nao dispara se a ponta estiver a menos disso do fim da zona. Padrao: 6 graus.",
    )
    parser.add_argument(
        "--max-hit-overshoot",
        type=float,
        default=DEFAULT_MAX_HIT_OVERSHOOT,
        help=f"Quanto a ponta pode passar do ponto de disparo sem ser rejeitada. Padrao: {DEFAULT_MAX_HIT_OVERSHOOT} graus.",
    )
    parser.add_argument(
        "--progress-threshold",
        type=float,
        default=DEFAULT_PROGRESS_THRESHOLD,
        help=f"Limiar visual do arco de progresso. Padrao: {DEFAULT_PROGRESS_THRESHOLD}.",
    )
    parser.add_argument(
        "--target-threshold",
        type=float,
        default=DEFAULT_TARGET_THRESHOLD,
        help=f"Limiar visual da zona-alvo. Padrao: {DEFAULT_TARGET_THRESHOLD}.",
    )
    parser.add_argument(
        "--max-progress-speed",
        type=float,
        default=DEFAULT_MAX_PROGRESS_SPEED,
        help=f"Velocidade angular maxima aceita. Padrao: {DEFAULT_MAX_PROGRESS_SPEED} deg/s.",
    )
    parser.add_argument(
        "--digit-lock-votes",
        type=int,
        default=11,
        help="Quantidade minima de leituras concordantes para travar o numero. Padrao: 11.",
    )
    parser.add_argument(
        "--reset-after",
        type=float,
        default=0.35,
        help="Tempo sem minigame para liberar a proxima rodada. Padrao: 0.35s.",
    )
    parser.add_argument(
        "--key-hold",
        type=float,
        default=0.025,
        help="Tempo que a tecla fica pressionada. Padrao: 0.025s.",
    )
    parser.add_argument(
        "--no-auto-retry",
        action="store_true",
        help="Desativa o E automatico depois que uma rodada termina/falha.",
    )
    parser.add_argument(
        "--anti-afk-seconds",
        type=float,
        default=8.0,
        help="Intervalo para mexer o mouse e evitar AFK. 0 desativa. Padrao: 8s.",
    )
    parser.add_argument(
        "--idle-recover-seconds",
        type=float,
        default=90.0,
        help="Se nenhum arco/rodada aparecer por esse tempo, aperta E para tentar reiniciar. 0 desativa. Padrao: 90s.",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=float,
        default=DEFAULT_COOLDOWN_SECONDS,
        help=f"Espera local apos detectar o aviso vermelho de bloqueio. Padrao: {DEFAULT_COOLDOWN_SECONDS:.0f}s.",
    )
    parser.add_argument(
        "--e-retry-wait",
        type=float,
        default=DEFAULT_E_RETRY_WAIT,
        help=f"Tempo para esperar a resposta depois de apertar E. Padrao: {DEFAULT_E_RETRY_WAIT:.1f}s.",
    )
    parser.add_argument(
        "--e-prompt-frames",
        type=int,
        default=4,
        help="Frames consecutivos do prompt E antes de apertar. Padrao: 4.",
    )
    parser.add_argument(
        "--failure-prompt-timeout",
        type=float,
        default=1.5,
        help="Sem prompt E apos esse tempo, a rodada e considerada sucesso. Padrao: 1.5s.",
    )
    parser.add_argument(
        "--x-offset",
        type=int,
        default=0,
        help="Ajuste fino horizontal do centro, em pixels.",
    )
    parser.add_argument(
        "--y-offset",
        type=int,
        default=0,
        help="Ajuste fino vertical do centro, em pixels.",
    )
    parser.add_argument(
        "--no-overlay",
        action="store_true",
        help="Desativa o aviso sobreposto na tela (canto superior direito) mostrando se o bot esta ligado/pausado.",
    )

    return parser


def _ensure_stdio() -> None:
    """Em um .exe 'windowed' (sem console), sys.stdout/stderr vem como None,
    e qualquer print() derrubaria o programa com AttributeError. Troca por um
    destino inofensivo; a GUI redireciona stdout de novo para a caixa de
    log antes de rodar o bot (ver farm_bot/gui.py)."""
    import os

    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")


def main() -> None:
    _ensure_stdio()

    if len(sys.argv) == 1:
        # Sem argumentos (ex.: duplo-clique no .exe): abre a janela de
        # selecao de opcoes em vez de exigir flags de linha de comando.
        from .gui import main as gui_main

        gui_main()
        return

    args = build_parser().parse_args()

    if args.video:
        run_video(args)
    else:
        run_live(args)


if __name__ == "__main__":
    main()

