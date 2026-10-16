import numpy as np

from farm_bot.geometry import (
    circular_delta,
    circular_distance,
    circular_mean_deg,
    circular_runs,
    circular_smooth,
    directional_distance,
    progress_extent,
)


def test_circular_delta_wraps_around_360():
    assert circular_delta(350.0, 10.0) == -20.0
    assert circular_delta(10.0, 350.0) == 20.0


def test_circular_distance_is_always_positive():
    assert circular_distance(350.0, 10.0) == 20.0
    assert circular_distance(10.0, 350.0) == 20.0


def test_circular_mean_deg_empty_returns_none():
    assert circular_mean_deg([]) is None


def test_circular_mean_deg_averages_across_wraparound():
    # 350 e 10 graus estao a 20 graus de distancia um do outro passando por 0.
    # O resultado cai exatamente na borda (0/360): math.atan2 pode retornar
    # qualquer um dos dois por erro de ponto flutuante.
    mean = circular_mean_deg([350.0, 10.0])
    assert mean == 0.0 or mean == 360.0


def test_circular_smooth_preserves_length_and_constant_signal():
    profile = np.full(360, 5.0, dtype=np.float32)
    smoothed = circular_smooth(profile, kernel_size=9)
    assert smoothed.shape == profile.shape
    assert np.allclose(smoothed, 5.0, atol=1e-4)


def test_circular_runs_detects_simple_run():
    mask = np.zeros(360, dtype=bool)
    mask[10:20] = True
    assert circular_runs(mask) == [(10, 19)]


def test_circular_runs_merges_run_that_wraps_past_zero():
    mask = np.zeros(360, dtype=bool)
    mask[355:] = True
    mask[:5] = True
    assert circular_runs(mask) == [(355, 364)]


def test_circular_runs_empty_mask_returns_empty_list():
    assert circular_runs(np.zeros(360, dtype=bool)) == []


def test_directional_distance_clockwise_and_counterclockwise():
    assert directional_distance(270.0, 280.0, +1) == 10.0
    assert directional_distance(270.0, 260.0, -1) == 10.0


def test_progress_extent_measures_contiguous_bright_arc():
    profile = np.zeros(360, dtype=np.float32)
    # A partir de START_ANGLE_DEG (270), 15 graus continuos acima do limiar.
    for offset in range(15):
        profile[(270 + offset) % 360] = 1.0
    extent = progress_extent(profile, direction=+1, threshold=0.5, max_distance=60.0)
    assert extent == 14.0
