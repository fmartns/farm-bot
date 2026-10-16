import pytest

tk = pytest.importorskip("tkinter")

from farm_bot.gui import build_args_from_selection  # noqa: E402  (import depende do skip acima)


def test_live_mode_builds_monitor_args_with_defaults():
    args = build_args_from_selection({"mode": "live", "monitor": "2"})
    assert args.video is None
    assert args.monitor == 2
    assert args.dry_run is False
    assert args.show is False


def test_live_mode_rejects_non_numeric_monitor():
    with pytest.raises(ValueError):
        build_args_from_selection({"mode": "live", "monitor": "abc"})


def test_video_mode_requires_a_file():
    with pytest.raises(ValueError):
        build_args_from_selection({"mode": "video", "video": ""})


def test_video_mode_builds_video_args():
    args = build_args_from_selection({"mode": "video", "video": "clip.mp4", "show": True})
    assert args.video == "clip.mp4"
    assert args.show is True


def test_checkboxes_and_offsets_are_forwarded():
    args = build_args_from_selection(
        {
            "mode": "live",
            "monitor": "1",
            "dry_run": True,
            "show": True,
            "save_captures": True,
            "no_auto_retry": True,
            "record_rounds": "rodadas_teste",
            "x_offset": "5",
            "y_offset": "-3",
        }
    )
    assert args.dry_run is True
    assert args.show is True
    assert args.save_captures is True
    assert args.no_auto_retry is True
    assert args.record_rounds == "rodadas_teste"
    assert args.x_offset == 5
    assert args.y_offset == -3


def test_invalid_offsets_raise_value_error():
    with pytest.raises(ValueError):
        build_args_from_selection({"mode": "live", "monitor": "1", "x_offset": "abc"})
