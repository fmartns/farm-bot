"""Constantes de calibracao e parametros padrao do farm bot."""

REFERENCE_HEIGHT = 1078.0
CENTER_X_RATIO = 0.5
CENTER_Y_RATIO = 0.8646

# Geometria do circulo, em pixels na altura de referencia.
RING_R_MIN = 57.0
RING_R_MAX = 90.0
ROI_PAD = 95.0

# O toque e considerado valido quando a menor distancia entre
# o arco branco e o alvo fica abaixo desse valor (escalado pela resolucao).
DEFAULT_HIT_DISTANCE = 1.25
DEFAULT_ARM_DISTANCE = 12.0
DEFAULT_HIT_STREAK = 1


START_ANGLE_DEG = 270.0
# v10: faixa radial restrita ao miolo do trilho escuro (~57-72 px em 1080p).
# A v9 ia ate 76 px e amostrava o cenario fora do anel.
POLAR_R_MIN = 60.0
POLAR_R_MAX = 69.0
# v10: posicao do disparo dentro da zona LOGICA (0=inicio, 0.5=centro).
# A ponta branca e a zona tem pontas arredondadas de ~6 graus (meia espessura
# do trilho): visualmente a ponta parece 6 graus a frente e a zona parece
# comecar 6 graus antes. Ao vivo, disparos com a ponta 6-7 graus apos a borda
# colorida falharam e com 8+ graus acertaram.
DEFAULT_TARGET_FRACTION = 0.5
DEFAULT_CAP_DEGREES = 6.0
# Classificacao por pixel (HSV OpenCV, 0-255). O arco branco e cinza neutro
# exato (BGR 204,204,204 -> S=0 V=204). Ha zonas palidas em degrade que
# comecam quase brancas (S~10 V~184) e vao a S~30, entao o corte e baixo.
WHITE_MAX_SAT = 6
WHITE_MIN_VAL = 192
COLOR_MIN_SAT = 8
COLOR_MIN_VAL = 150
# Perfis = fracao de pixels da classe em cada grau (0..1).
DEFAULT_PROGRESS_THRESHOLD = 0.5
DEFAULT_TARGET_THRESHOLD = 0.5
# Atraso estimado entre a captura e o jogo registrar a tecla.
DEFAULT_INPUT_LATENCY = 0.030
DEFAULT_MAX_HIT_OVERSHOOT = 18.0
DEFAULT_MERGE_PRECONTACT = 12.0
DEFAULT_COOLDOWN_SECONDS = 70.0
DEFAULT_E_RETRY_WAIT = 20.0
DEFAULT_MAX_PROGRESS_SPEED = 220.0
DEFAULT_MIN_PROGRESS_SPEED = 18.0


