import cv2
import numpy as np

from farm_bot.geometry import progress_extent
from farm_bot.ring import angular_profiles


def _bgr(h, s, v):
    pixel = np.uint8([[[h, s, v]]])
    return cv2.cvtColor(pixel, cv2.COLOR_HSV2BGR)[0, 0]


def _paint_annulus(image, cx, cy, start, end, bgr):
    yy, xx = np.indices(image.shape[:2])
    angle = (np.degrees(np.arctan2(yy - cy, xx - cx)) + 360.0) % 360.0
    radius = np.hypot(xx - cx, yy - cy)
    annulus = (radius >= 60.0) & (radius <= 69.0)
    if end >= start:
        span = annulus & (angle >= start) & (angle <= end)
    else:
        span = annulus & ((angle >= start) | (angle <= end))
    image[span] = bgr


def test_tinted_arc_counts_as_progress_and_saturated_zone_does_not():
    # Arco levemente tingido e mais escuro que o cinza puro (S=0 V=204).
    # Era invisivel com S<=6 e V>=192, entao a direcao nao travava.
    image = np.zeros((240, 240, 3), dtype=np.uint8)
    _paint_annulus(image, 120, 120, 270, 310, _bgr(15, 20, 185))
    _paint_annulus(image, 120, 120, 100, 140, _bgr(140, 60, 214))

    target, progress = angular_profiles(image, 120, 120, 1.0)

    extent = progress_extent(progress, direction=+1, threshold=0.5, max_distance=80.0)
    assert extent >= 30.0
    assert float(progress[120:130].mean()) < 0.2
    assert float(target[110:130].mean()) > 0.5
