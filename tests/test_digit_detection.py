import numpy as np

from farm_bot.digit_detection import largest_component
from farm_bot.templates import TEMPLATES, classify_digit


def test_largest_component_picks_biggest_blob_above_min_area():
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[1:3, 1:3] = 255  # blob pequeno (4 px)
    mask[10:18, 10:18] = 255  # blob grande (64 px)

    component, area = largest_component(mask, min_area=10)

    assert area == 64
    assert component is not None
    assert component[12, 12] == 255
    assert component[2, 2] == 0


def test_largest_component_returns_none_when_nothing_meets_min_area():
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[0:2, 0:2] = 255
    component, area = largest_component(mask, min_area=100)
    assert component is None
    assert area == 0


def test_classify_digit_recognizes_its_own_template_with_high_confidence():
    # Um template usado como entrada deve ser classificado como ele mesmo:
    # e o caso trivial de IoU = 1.0 contra si proprio.
    for digit, templates in TEMPLATES.items():
        result = classify_digit(templates[0])
        assert result is not None
        classified_digit, confidence, margin, _normalized = result
        assert classified_digit == digit
        assert confidence > 0.9
