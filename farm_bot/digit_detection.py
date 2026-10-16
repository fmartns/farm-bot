"""Extracao e consenso (votacao) do digito central do minigame."""

import collections
import math
from typing import Optional

import cv2
import numpy as np

from .ring import DIGIT_ANCHOR_DX, DIGIT_ANCHOR_DY
from .templates import classify_digit


def largest_component(mask: np.ndarray, min_area: int) -> tuple:
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
    best_index = None
    best_area = 0

    for i in range(1, count):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area >= min_area and area > best_area:
            best_index = i
            best_area = area

    if best_index is None:
        return None, 0

    component = (labels == best_index).astype(np.uint8) * 255
    return component, best_area


def extract_digit(roi: np.ndarray, cx: int, cy: int, scale: float) -> Optional[dict]:
    """Extrai o digito central sem confundir o arco branco com o numero.

    A versao anterior escolhia o maior componente branco da regiao. Dependendo
    da posicao do arco de progresso, um pedaco do arco podia ser maior que o
    digito e acabava sendo classificado como 0/4/etc. Aqui avaliamos todos os
    componentes plausiveis e escolhemos o que realmente se parece com um digito
    e fica perto do centro do circulo.
    """
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    # Regiao um pouco maior, mas com filtros geometricos fortes abaixo.
    x0 = max(0, int(round(cx - 46 * scale)))
    x1 = min(roi.shape[1], int(round(cx + 46 * scale)))
    y0 = max(0, int(round(cy - 43 * scale)))
    y1 = min(roi.shape[0], int(round(cy + 43 * scale)))

    sub = hsv[y0:y1, x0:x1]

    # Branco/cinza claro do numero. Saturacao <= 50 evita que fundos ciano/azulados
    # moderadamente saturados sejam unidos ao glifo; valor alto preserva antialiasing.
    mask = ((sub[:, :, 1] <= 50) & (sub[:, :, 2] >= 175)).astype(np.uint8) * 255

    # Remove pontinhos soltos sem deformar o glifo.
    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)

    target_x = (x1 - x0) / 2.0
    target_y = (y1 - y0) / 2.0

    min_h = max(24, int(round(30 * scale)))
    max_h = int(round(72 * scale))
    min_w = max(7, int(round(8 * scale)))
    max_w = int(round(58 * scale))
    min_area = max(55, int(round(90 * scale * scale)))
    max_area = int(round(2300 * scale * scale))

    ranked = []

    for i in range(1, count):
        x, y, w, h, area = map(int, stats[i])

        if not (min_h <= h <= max_h):
            continue
        if not (min_w <= w <= max_w):
            continue
        if not (min_area <= area <= max_area):
            continue

        center_x = x + w / 2.0
        center_y = y + h / 2.0
        dx = abs(center_x - target_x)
        dy = abs(center_y - target_y)

        # O numero fica no miolo. Esse filtro elimina sobretudo o arco branco
        # superior/lateral, que causava as leituras falsas de baixa confianca.
        if dx > 25 * scale or dy > 27 * scale:
            continue

        component = (labels == i).astype(np.uint8) * 255
        glyph = component[y:y + h, x:x + w]
        classified = classify_digit(glyph)
        if classified is None:
            continue

        digit, confidence, margin, normalized = classified

        # Priorizamos semelhanca com um numero real e usamos posicao apenas como
        # desempate. Um arco costuma ter conf ~0.55-0.65; numeros reais do video
        # ficam em ~0.85-0.98.
        pos_penalty = 0.0020 * (dx / max(scale, 1e-6)) + 0.0012 * (dy / max(scale, 1e-6))
        rank_score = confidence + 0.35 * margin - pos_penalty

        ranked.append((
            rank_score,
            confidence,
            margin,
            digit,
            (x0 + x, y0 + y, w, h),
            normalized,
        ))

    if not ranked:
        return None

    ranked.sort(reverse=True, key=lambda item: item[0])
    _, confidence, margin, digit, bbox, normalized = ranked[0]

    return {
        "digit": int(digit),
        "confidence": float(confidence),
        "margin": float(margin),
        "bbox": bbox,
        "normalized": normalized,
    }


def digit_anchor(digit_info: dict, scale: float) -> tuple:
    """Centro do anel estimado a partir do bbox do digito."""
    x, y, w, h = digit_info["bbox"]
    dx = DIGIT_ANCHOR_DX.get(int(digit_info["digit"]), 0.0)
    return x + w / 2.0 - dx * scale, y + h / 2.0 + DIGIT_ANCHOR_DY * scale


def stable_digit_lock(observations: collections.deque, min_votes: int) -> Optional[tuple]:
    if len(observations) < min_votes:
        return None

    recent = list(observations)[-max(min_votes + 4, 11):]
    counts = collections.Counter(item[0] for item in recent)
    digit, votes = counts.most_common(1)[0]
    required = max(min_votes, math.ceil(len(recent) * 0.68))
    if votes < required:
        return None

    matching = [item for item in recent if item[0] == digit]
    median_conf = float(np.median([item[1] for item in matching]))
    median_margin = float(np.median([item[2] for item in matching]))
    if median_conf < 0.80 or median_margin < 0.045:
        return None

    return int(digit), median_conf, median_margin, votes, len(recent)

