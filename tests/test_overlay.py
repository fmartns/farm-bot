import os
import time

import pytest

from farm_bot.overlay import create_overlay

pytestmark = pytest.mark.skipif(os.name != "nt", reason="overlay usa a API do Windows (ctypes/user32).")


def test_overlay_can_be_created_updated_and_closed():
    overlay = create_overlay()
    if overlay is None:
        pytest.skip("Nao foi possivel criar a janela (ambiente sem suporte).")

    assert overlay._hwnd

    overlay.set_status("BOT DESLIGADO", 0x1A2CC0)
    time.sleep(0.2)

    overlay.close()
    overlay._thread.join(timeout=3.0)
    assert not overlay._thread.is_alive()
