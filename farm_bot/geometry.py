"""Helpers de geometria circular/angular reutilizados pelo tracking do arco."""

import math

import numpy as np

from .config import START_ANGLE_DEG


def circular_delta(a: float, b: float) -> float:
    """Menor diferenca assinada a-b em graus, no intervalo [-180, 180)."""
    return (a - b + 180.0) % 360.0 - 180.0


def circular_distance(a: float, b: float) -> float:
    return abs(circular_delta(a, b))


def circular_mean_deg(values):
    if not values:
        return None
    radians = np.deg2rad(np.asarray(values, dtype=np.float64))
    s = float(np.sin(radians).mean())
    c = float(np.cos(radians).mean())
    if abs(s) < 1e-9 and abs(c) < 1e-9:
        return float(values[-1]) % 360.0
    return math.degrees(math.atan2(s, c)) % 360.0


def circular_smooth(profile: np.ndarray, kernel_size: int = 9) -> np.ndarray:
    kernel_size = max(3, int(kernel_size) | 1)
    pad = kernel_size // 2
    ext = np.concatenate([profile[-pad:], profile, profile[:pad]])
    kernel = np.ones(kernel_size, dtype=np.float32) / float(kernel_size)
    smoothed = np.convolve(ext, kernel, mode="same")[pad:-pad]
    return smoothed.astype(np.float32)


def circular_runs(mask: np.ndarray):
    """Retorna runs True como (inicio, fim_unwrapped)."""
    mask = np.asarray(mask, dtype=bool)
    indices = np.flatnonzero(mask)
    if indices.size == 0:
        return []

    runs = []
    start = prev = int(indices[0])
    for raw in indices[1:]:
        value = int(raw)
        if value == prev + 1:
            prev = value
        else:
            runs.append((start, prev))
            start = prev = value
    runs.append((start, prev))

    if len(runs) > 1 and runs[0][0] == 0 and runs[-1][1] == 359:
        merged = (runs[-1][0], runs[0][1] + 360)
        runs = [merged] + runs[1:-1]
    return runs


def directional_distance(start: float, angle: float, direction: int) -> float:
    if direction >= 0:
        return (angle - start) % 360.0
    return (start - angle) % 360.0


def progress_extent(
    progress_profile: np.ndarray,
    direction: int,
    threshold: float,
    max_distance: float = 220.0,
    gap_allow: int = 3,
):
    """Comprimento do arco claro contiguo a partir do topo, numa direcao."""
    max_steps = int(max(1, math.ceil(max_distance)))
    started = False
    gap = 0
    last_bright = 0

    for distance in range(max_steps + 1):
        angle = int(round((START_ANGLE_DEG + direction * distance) % 360.0)) % 360
        value = float(progress_profile[angle])

        if value >= threshold:
            started = True
            last_bright = distance
            gap = 0
        elif started:
            gap += 1
            if gap > gap_allow:
                break
        elif distance > 18:
            break

    return float(last_bright)

