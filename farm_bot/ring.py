"""Localizacao/ajuste do anel do minigame e perfis angulares (alvo/progresso)."""

import math
from typing import Optional

import cv2
import numpy as np

from .config import COLOR_MIN_SAT, COLOR_MIN_VAL, POLAR_R_MAX, POLAR_R_MIN, WHITE_MAX_SAT, WHITE_MIN_VAL
from .geometry import circular_smooth


def locate_ring_center(roi: np.ndarray, expected_cx: int, expected_cy: int, scale: float) -> Optional[tuple]:
    """Localiza o centro real do circulo.

    O HUD do video se desloca alguns pixels entre rodadas. A v4 assumia o centro
    fixo, o que atrapalhava tanto o numero quanto a geometria do arco.
    """
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 1.2)

    min_r = max(42, int(round(50 * scale)))
    max_r = max(min_r + 5, int(round(88 * scale)))
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.15,
        minDist=max(24, int(round(28 * scale))),
        param1=100,
        param2=27,
        minRadius=min_r,
        maxRadius=max_r,
    )
    if circles is None:
        return None

    best = None
    for x, y, radius in circles[0]:
        dx = float(x) - float(expected_cx)
        dy = float(y) - float(expected_cy)
        center_distance = math.hypot(dx, dy)
        if center_distance > 32 * scale:
            continue
        # O raio pode variar dependendo de qual borda o Hough pegou; centro pesa mais.
        radius_penalty = abs(float(radius) - 72.0 * scale) * 0.12
        score = center_distance + radius_penalty
        if best is None or score < best[0]:
            best = (score, float(x), float(y), float(radius))

    if best is None:
        return None
    return best[1], best[2], best[3]


# v10: bordas do trilho escuro (px na escala 1) e deslocamento do centro do
# digito em relacao ao centro do anel, medidos nas gravacoes do jogo.
RING_EDGE_INNER = 58.0
RING_EDGE_OUTER = 71.5
DIGIT_ANCHOR_DY = 9.2
DIGIT_ANCHOR_DX = {5: 1.8, 6: -2.2, 7: 1.5, 8: -1.4}
_FIT_ANGLES = np.linspace(0.0, 2.0 * np.pi, 96, endpoint=False)
_FIT_COS = np.cos(_FIT_ANGLES).astype(np.float32)
_FIT_SIN = np.sin(_FIT_ANGLES).astype(np.float32)


def fit_ring(roi: np.ndarray, cx0: float, cy0: float, scale: float,
             ring_scale0: float = 1.0, span: float = 6.0, scale_span: float = 0.14) -> tuple:
    """Centro e escala do anel maximizando o gradiente nas DUAS bordas do trilho.

    Nas gravacoes, o tamanho do anel variava entre rodadas (escala ~1.00 ou
    ~1.11) e o Hough da v9 escolhia o circulo mais proximo do centro esperado,
    nao o melhor. Com raio/centro errados a faixa angular amostrava a borda do
    trilho e o fundo: a zona-alvo nunca passava do limiar ("alvo nao foi
    travado") e os angulos ficavam deslocados.
    """
    gray = cv2.GaussianBlur(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)
    mag = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    h, w = mag.shape

    def score(cx, cy, s):
        per_edge = []
        for edge in (RING_EDGE_INNER, RING_EDGE_OUTER):
            r = (edge * scale * s)[:, None]
            xi = np.clip(np.rint(cx[:, None] + r * _FIT_COS).astype(np.int32), 0, w - 1)
            yi = np.clip(np.rint(cy[:, None] + r * _FIT_SIN).astype(np.int32), 0, h - 1)
            per_edge.append(mag[yi, xi].mean(axis=1))
        return np.minimum(per_edge[0], per_edge[1])

    best = (float(cx0), float(cy0), float(ring_scale0))
    best_score = 0.0
    passes = (
        (1.0, span, 0.02, scale_span),
        (0.5, 1.5, 0.005, 0.02),
    )
    for step, sp, s_step, s_sp in passes:
        offsets = np.arange(-sp, sp + 1e-6, step, dtype=np.float32)
        s_offsets = np.arange(-s_sp, s_sp + 1e-6, s_step, dtype=np.float32)
        gx, gy, gs = np.meshgrid(best[0] + offsets, best[1] + offsets, best[2] + s_offsets, indexing="ij")
        gx, gy, gs = gx.ravel(), gy.ravel(), gs.ravel()
        values = score(gx, gy, gs)
        k = int(np.argmax(values))
        best = (float(gx[k]), float(gy[k]), float(gs[k]))
        best_score = float(values[k])
    return best[0], best[1], best[2], best_score


def angular_profiles(roi: np.ndarray, cx: float, cy: float, scale: float) -> tuple:
    """Perfis hue-independent do anel.

    A v5 usava limites absolutos de saturacao/brilho. Isso podia enxergar o
    cenario atraves do HUD como se fosse a zona de acerto. Na v6 amostramos
    apenas o miolo radial do anel e calculamos dois scores continuos:

      target_score   = brilho * saturacao
      progress_score = brilho * (1 - saturacao)

    Assim a cor do alvo pode mudar sem precisar conhecer o hue, enquanto o
    arco branco continua separado do alvo colorido.
    """
    # v10: os scores continuos da v6 nao separavam o arco branco da zona.
    # Medido no jogo (HSV 0-255): branco S=0 V=204; verde S=103 V=228;
    # rosa S=92 V=216; lilas S=48 V=214. Com brilho*(1-sat) a zona dava
    # 0.53-0.68, acima do limiar 0.44 do progresso: a zona era lida como
    # arco branco e o bot disparava cedo. Agora cada pixel e classificado
    # (branco x colorido) e o perfil e a FRACAO de pixels de cada classe.
    # O branco aceita um cinza tingido ou mais escuro (ver WHITE_MAX_SAT);
    # o miolo saturado da zona continua so na classe colorida.
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    yy, xx = np.indices(roi.shape[:2])
    radius = np.hypot(xx - cx, yy - cy)
    angles = (np.degrees(np.arctan2(yy - cy, xx - cx)) + 360.0) % 360.0

    r_min = POLAR_R_MIN * scale
    r_max = POLAR_R_MAX * scale
    annulus = (radius >= r_min) & (radius <= r_max)
    angle_bins = np.floor(angles).astype(np.int16) % 360

    counts = np.bincount(angle_bins[annulus].ravel(), minlength=360).astype(np.float32)
    counts = np.maximum(counts, 1.0)

    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    # Branco tem prioridade: o arco tingido (S ate WHITE_MAX_SAT) nao pode
    # cair na classe colorida, senao a zona "engole" o progresso e a direcao
    # nao trava. O miolo saturado da zona (lilas/rosa/verde) continua colorido.
    white_pixels = (sat <= WHITE_MAX_SAT) & (val >= WHITE_MIN_VAL)
    colored_pixels = (sat >= COLOR_MIN_SAT) & (val >= COLOR_MIN_VAL) & ~white_pixels

    target_profile = (
        np.bincount(
            angle_bins[annulus].ravel(),
            weights=colored_pixels[annulus].ravel().astype(np.float32),
            minlength=360,
        ).astype(np.float32)
        / counts
    )
    progress_profile = (
        np.bincount(
            angle_bins[annulus].ravel(),
            weights=white_pixels[annulus].ravel().astype(np.float32),
            minlength=360,
        ).astype(np.float32)
        / counts
    )

    return circular_smooth(target_profile, 3), circular_smooth(progress_profile, 3)

