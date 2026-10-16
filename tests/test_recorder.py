import os

import numpy as np

from farm_bot.recorder import RoundRecorder


def test_round_recorder_writes_frames_only_once_round_is_active(tmp_path):
    base_dir = str(tmp_path)
    recorder = RoundRecorder(base_dir)
    roi = np.zeros((4, 4, 3), dtype=np.uint8)

    try:
        # Sem centro/digito valido: fica no pre-buffer, nenhum round_dir criado ainda.
        inactive_state = {"center": None}
        recorder.frame(now=0.0, roi=roi, state=inactive_state, info={"digit_valid": False})
        assert recorder.round_dir is None

        # Com centro detectado, uma rodada comeca e os frames passam a ser gravados.
        active_state = {"center": (1.0, 1.0)}
        recorder.frame(now=0.1, roi=roi, state=active_state, info={"digit_valid": False})
        assert recorder.round_dir is not None

        recorder.end_round("sucesso")
    finally:
        recorder.close()

    round_dirs = [p for p in os.listdir(base_dir) if p.startswith("round_")]
    assert len(round_dirs) == 1

    round_path = os.path.join(base_dir, round_dirs[0])
    assert os.path.isfile(os.path.join(round_path, "log.jsonl"))
    assert os.path.isfile(os.path.join(round_path, "result.txt"))
