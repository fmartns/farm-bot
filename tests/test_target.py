import collections

import numpy as np

from farm_bot.target import detect_target_arc, estimate_speed, stable_target


def _profile_with_arc(center: int, width: int, value: float = 1.0) -> np.ndarray:
    profile = np.zeros(360, dtype=np.float32)
    half = width // 2
    for offset in range(-half, half + 1):
        profile[(center + offset) % 360] = value
    return profile


def test_detect_target_arc_finds_single_colored_zone():
    # Longe o suficiente do inicio do progresso (START_ANGLE_DEG=270) para nao
    # ser descartado pelo filtro de distancia minima.
    profile = _profile_with_arc(center=120, width=20)
    candidate = detect_target_arc(profile, threshold=0.5)
    assert candidate is not None
    assert abs(candidate["center"] - 120.0) <= 1.0
    assert 18.0 <= candidate["width"] <= 22.0


def test_detect_target_arc_returns_none_without_candidates():
    profile = np.zeros(360, dtype=np.float32)
    assert detect_target_arc(profile, threshold=0.5) is None


def test_stable_target_requires_minimum_votes():
    history = collections.deque()
    history.append({"center": 120.0, "width": 20.0, "start": 110.0, "score": 1.0})
    assert stable_target(history, min_width=12.0, min_votes=6) is None


def test_stable_target_locks_zone_with_enough_consistent_votes():
    history = collections.deque()
    for _ in range(10):
        history.append({"center": 120.0, "width": 20.0, "start": 110.0, "score": 1.0})

    locked = stable_target(history, min_width=12.0, min_votes=6)
    assert locked is not None
    assert 15.0 <= locked["width"] <= 22.0


def test_estimate_speed_needs_minimum_samples():
    samples = collections.deque([(0.0, 0.0), (0.1, 2.0)])
    assert estimate_speed(samples, now=0.1) is None


def test_estimate_speed_computes_slope_within_bounds():
    samples = collections.deque()
    slope = 40.0  # graus/s, dentro de [DEFAULT_MIN_PROGRESS_SPEED, DEFAULT_MAX_PROGRESS_SPEED]
    for i in range(8):
        t = i * 0.03
        samples.append((t, slope * t))
    estimated = estimate_speed(samples, now=samples[-1][0])
    assert estimated is not None
    assert abs(estimated - slope) < 1.0
