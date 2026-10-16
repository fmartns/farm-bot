from farm_bot.cli import build_parser
from farm_bot.config import (
    DEFAULT_ARM_DISTANCE,
    DEFAULT_CAP_DEGREES,
    DEFAULT_HIT_DISTANCE,
    DEFAULT_TARGET_FRACTION,
)


def test_build_parser_does_not_raise_and_has_expected_defaults():
    """Regressao: build_parser() referenciava constantes de config.py que nao
    estavam importadas (NameError em tempo de execucao, antes de qualquer
    argumento ser parseado)."""
    parser = build_parser()
    args = parser.parse_args([])

    assert args.hit_distance == DEFAULT_HIT_DISTANCE
    assert args.arm_distance == DEFAULT_ARM_DISTANCE
    assert args.cap_degrees == DEFAULT_CAP_DEGREES
    assert args.target_fraction == DEFAULT_TARGET_FRACTION
    assert args.video is None
    assert args.dry_run is False


def test_build_parser_accepts_video_mode_flags():
    parser = build_parser()
    args = parser.parse_args(["--video", "clip.mp4", "--dry-run", "--show"])

    assert args.video == "clip.mp4"
    assert args.dry_run is True
    assert args.show is True
