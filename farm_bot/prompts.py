"""Deteccao visual do prompt "E" e do aviso de bloqueio/cooldown."""

import cv2
import numpy as np


def detect_e_prompt(roi: np.ndarray) -> bool:
    """Detecta o quadrado luminoso do prompt "E FARM DE MUNICAO".

    O prompt fica na parte inferior do mesmo ROI do minigame. A deteccao usa
    geometria + saturacao/brilho, sem OCR, para continuar leve em 120 Hz.
    """
    if roi is None or roi.size == 0:
        return False

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    y0 = int(round(h * 0.68))
    x1 = int(round(w * 0.72))
    sub = hsv[y0:h, 0:x1]
    if sub.size == 0:
        return False

    sat = sub[:, :, 1]
    val = sub[:, :, 2]
    # O botao E e um bloco verde/lima bem saturado e claro.
    mask = ((sat >= 95) & (val >= 145)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    for i in range(1, count):
        x, y, cw, ch, area = stats[i]
        if area < 260:
            continue
        if not (16 <= cw <= 55 and 16 <= ch <= 55):
            continue
        aspect = cw / max(1.0, float(ch))
        fill = area / max(1.0, float(cw * ch))
        if 0.55 <= aspect <= 1.55 and fill >= 0.45:
            return True
    return False


def detect_cooldown_notification(bgr: np.ndarray) -> bool:
    """Detecta o grande aviso vermelho do bloqueio do minigame."""
    if bgr is None or bgr.size == 0:
        return False

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    red = (
        (sat >= 80)
        & (val >= 75)
        & ((hue <= 14) | (hue >= 150))
    ).astype(np.uint8) * 255
    red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(red)
    for i in range(1, count):
        x, y, cw, ch, area = stats[i]
        if area >= 7000 and cw >= 220 and ch >= 55:
            return True
    return False

