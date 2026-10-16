"""Gravacao em disco de cada rodada (frames + estado), para analise offline."""

import collections
import os
import time

import cv2
import numpy as np


class RoundRecorder:
    """Diagnostico: salva cada rodada (frames da ROI + estado por frame).

    Grava apenas enquanto ha um minigame em andamento, mais um pre-buffer
    curto. PNGs sao escritos em threads para nao atrasar o loop de captura.
    """

    def __init__(self, base_dir: str):
        import json
        import queue
        import threading

        self._json = json
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.queue = queue.Queue()
        self.pre = collections.deque(maxlen=40)
        self.round_dir = None
        self.log_lines = []
        self.round_index = 0
        self.frame_index = 0
        self.workers = [threading.Thread(target=self._work, daemon=True) for _ in range(2)]
        for worker in self.workers:
            worker.start()

    def _work(self):
        while True:
            item = self.queue.get()
            if item is None:
                return
            kind, path, payload = item
            if kind == "png":
                cv2.imwrite(path, payload, [cv2.IMWRITE_PNG_COMPRESSION, 1])
            else:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(payload)

    @staticmethod
    def _snapshot(state, info, now, event):
        def num(value):
            return None if value is None else round(float(value), 2)

        target = state.get("target")
        locked = state.get("locked_digit")
        digit = info.get("digit_info") if info else None
        return {
            "t": round(now, 4),
            "event": event,
            "center": None if state.get("center") is None else [num(v) for v in state["center"]],
            "ring_scale": num(state.get("ring_scale")),
            "digit_valid": bool(info.get("digit_valid")) if info else False,
            "digit_raw": None if digit is None else [digit["digit"], num(digit["confidence"]), num(digit["margin"])],
            "locked": None if locked is None else locked[0],
            "target": None if target is None else [num(target["center"]), num(target["width"])],
            "frozen": bool(state.get("target_frozen")),
            "direction": state.get("direction"),
            "progress": num(state.get("last_progress")),
            "raw": num(state.get("raw_progress")),
            "entry": num(state.get("target_entry")),
            "desired": num(state.get("desired_progress")),
            "exit": num(state.get("target_exit")),
            "speed": num(state.get("speed")),
            "armed": bool(state.get("armed_for_hit")),
            "streak": state.get("hit_streak", 0),
            "pressed": bool(state.get("pressed")),
        }

    def frame(self, now: float, roi: np.ndarray, state: dict, info: dict, event: str = None) -> None:
        snapshot = self._snapshot(state, info, now, event)
        active = state.get("center") is not None or snapshot["digit_valid"]
        if self.round_dir is None:
            if not active:
                self.pre.append((roi, snapshot))
                return
            self.round_index += 1
            self.round_dir = os.path.join(self.base_dir, f"round_{self.round_index:03d}_{time.strftime('%H%M%S')}")
            os.makedirs(self.round_dir, exist_ok=True)
            self.log_lines = []
            self.frame_index = 0
            for pre_roi, pre_snapshot in self.pre:
                self._add(pre_roi, pre_snapshot)
            self.pre.clear()
        self._add(roi, snapshot)

    def _add(self, roi, snapshot):
        snapshot["i"] = self.frame_index
        self.queue.put(("png", os.path.join(self.round_dir, f"{self.frame_index:05d}.png"), roi))
        self.log_lines.append(self._json.dumps(snapshot))
        self.frame_index += 1

    def end_round(self, result: str) -> None:
        if self.round_dir is None:
            return
        self.queue.put(("text", os.path.join(self.round_dir, "log.jsonl"), "\n".join(self.log_lines) + "\n"))
        self.queue.put(("text", os.path.join(self.round_dir, "result.txt"), result + "\n"))
        self.round_dir = None

    def close(self) -> None:
        self.end_round("interrompida")
        for _ in self.workers:
            self.queue.put(None)
        for worker in self.workers:
            worker.join()

