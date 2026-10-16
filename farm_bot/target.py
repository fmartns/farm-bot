"""Deteccao/consenso da zona-alvo colorida e estimativa de velocidade do arco."""

import collections
import math
from typing import Optional

import numpy as np

from .config import (
    DEFAULT_MAX_PROGRESS_SPEED,
    DEFAULT_MIN_PROGRESS_SPEED,
    DEFAULT_TARGET_THRESHOLD,
    START_ANGLE_DEG,
)
from .geometry import circular_distance, circular_runs


def detect_target_arc(target_profile: np.ndarray, threshold: float = DEFAULT_TARGET_THRESHOLD) -> Optional[dict]:
    # O limiar e adaptativo, mas nunca cai abaixo do valor configurado. Isso
    # evita que um fundo muito colorido gere um alvo falso.
    median = float(np.median(target_profile))
    p90 = float(np.percentile(target_profile, 90))
    dynamic_threshold = max(float(threshold), median + 0.30 * max(0.0, p90 - median))

    runs = circular_runs(target_profile >= dynamic_threshold)
    candidates = []

    for start, end in runs:
        width = end - start + 1
        if width < 10 or width > 96:
            continue

        unwrapped = np.arange(start, end + 1, dtype=np.float64)
        indices = (unwrapped.astype(np.int32) % 360)
        weights = target_profile[indices].astype(np.float64) + 1e-4
        center_unwrapped = float(np.average(unwrapped, weights=weights))
        center = center_unwrapped % 360.0

        # O progresso nasce no topo. A zona de acerto real nunca deve ser
        # confundida com esse trecho inicial.
        dist_from_start = circular_distance(center, START_ANGLE_DEG)
        if dist_from_start < 38.0:
            continue

        mean_score = float(target_profile[indices].mean())
        peak_score = float(target_profile[indices].max())
        if mean_score < dynamic_threshold * 1.01:
            continue

        score = (0.75 * mean_score + 0.25 * peak_score) * math.sqrt(width)
        candidates.append({
            "center": center,
            "width": float(width),
            "start": float(start % 360),
            "end": float(end % 360),
            "score": score,
            "mean": mean_score,
            "threshold": dynamic_threshold,
        })

    if not candidates:
        return None
    return max(candidates, key=lambda item: item["score"])

def stable_target(history: collections.deque, min_width: float = 12.0, min_votes: int = 6) -> Optional[dict]:
    """Estima os limites reais da zona por voto angular entre varios frames.

    Cada frame fornece um intervalo candidato. Em vez de confiar no centro e na
    largura de um unico frame, contamos quantas vezes cada grau do circulo fez
    parte do alvo. O trecho presente em pelo menos ~55% das observacoes vira a
    zona estavel. Isso elimina tanto os segmentos espurios estreitos quanto os
    frames em que o fundo amplia artificialmente a zona.
    """
    usable = list(history)[-48:]
    if len(usable) < min_votes:
        return None

    counts = np.zeros(360, dtype=np.float32)
    quality = np.zeros(360, dtype=np.float32)
    for item in usable:
        width = int(round(float(item.get("width", 0.0))))
        if width < 8 or width > 96:
            continue
        start = int(round(float(item.get("start", 0.0)))) % 360
        idx = (start + np.arange(width, dtype=np.int32)) % 360
        counts[idx] += 1.0
        quality[idx] += max(0.05, float(item.get("score", 0.05)))

    valid_observations = max(1, len(usable))
    vote_threshold = max(float(min_votes) * 0.60, valid_observations * 0.55)
    runs = circular_runs(counts >= vote_threshold)
    candidates = []
    for start, end in runs:
        width = end - start + 1
        if width < min_width or width > 90:
            continue
        unwrapped = np.arange(start, end + 1, dtype=np.float64)
        idx = unwrapped.astype(np.int32) % 360
        # Centro geometrico do intervalo votado. Para o ponto de entrada, os
        # limites sao mais importantes que o pico de cor.
        center = float((start + end) / 2.0) % 360.0
        support_min = float(counts[idx].min())
        support_mean = float(counts[idx].mean())
        qmean = float(quality[idx].mean())
        score = support_mean + 0.05 * qmean
        candidates.append({
            "center": center,
            "width": float(width),
            "start": float(start % 360),
            "end": float(end % 360),
            "score": score,
            "support": support_mean,
            "support_min": support_min,
            "observations": valid_observations,
            "threshold": float(np.median([float(i.get("threshold", DEFAULT_TARGET_THRESHOLD)) for i in usable])),
        })

    if not candidates:
        return None
    return max(candidates, key=lambda item: item["score"])


def estimate_speed(samples: collections.deque, now: float) -> Optional[float]:
    """Regressao robusta simples dos ultimos ~0.75 s do endpoint angular."""
    usable = [(t, p) for t, p in samples if now - t <= 0.45]
    if len(usable) < 5:
        return None

    times = np.asarray([item[0] for item in usable], dtype=np.float64)
    positions = np.asarray([item[1] for item in usable], dtype=np.float64)
    times = times - times[0]
    if times[-1] < 0.14 or positions[-1] - positions[0] < 8.0:
        return None

    slope = float(np.polyfit(times, positions, 1)[0])
    if not (DEFAULT_MIN_PROGRESS_SPEED <= slope <= DEFAULT_MAX_PROGRESS_SPEED):
        return None
    return slope

