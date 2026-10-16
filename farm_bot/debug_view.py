"""Desenho da janela de depuracao (--show)."""

import cv2
import numpy as np


def draw_debug_v6(roi: np.ndarray, state: dict, info: dict, paused: bool = False) -> np.ndarray:
    debug = roi.copy()
    cx, cy = info.get("center", (debug.shape[1] / 2, debug.shape[0] / 2))
    cv2.drawMarker(debug, (int(round(cx)), int(round(cy))), (0, 255, 255), cv2.MARKER_CROSS, 12, 1)

    digit = info.get("digit_info")
    if digit is not None:
        x, y, w, h = digit["bbox"]
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 255), 1)

    target = state.get("target")
    if target is not None:
        radius = int(round(72))
        start_angle = target["center"] - target["width"] / 2.0
        end_angle = target["center"] + target["width"] / 2.0
        cv2.ellipse(
            debug,
            (int(round(cx)), int(round(cy))),
            (radius, radius),
            0,
            float(start_angle),
            float(end_angle),
            (0, 255, 0),
            2,
        )

    locked = state.get("locked_digit")
    digit_text = "--" if locked is None else str(locked[0])
    direction = state.get("direction")
    dir_text = "?" if direction is None else ("CW" if direction > 0 else "CCW")
    speed = state.get("speed")
    speed_text = "--" if speed is None else f"{speed:.1f}d/s"
    pred = state.get("predicted_progress")
    desired = state.get("desired_progress")
    pred_text = "--" if pred is None else f"{pred:.1f}"
    desired_text = "--" if desired is None else f"{desired:.1f}"

    lines = [
        f"digit={digit_text} dir={dir_text} speed={speed_text}",
        f"progress={pred_text} target={desired_text}",
    ]
    if paused:
        lines.append("PAUSADO")
    elif state.get("pressed"):
        lines.append("JA APERTOU")
    elif speed is None:
        lines.append("CALIBRANDO")
    else:
        lines.append("RASTREANDO")

    for i, line in enumerate(lines):
        cv2.putText(debug, line, (5, 18 + 18 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (255, 255, 255), 1, cv2.LINE_AA)
    return debug

