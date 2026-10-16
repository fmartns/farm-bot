"""Acesso a janela em foco e leitura de teclas (Windows)."""

import ctypes

GAME_WINDOW_CLASS = "grcWindow"  # janela do GTA V / FiveM


def game_has_focus() -> bool:
    """v10: as teclas vao para a janela ativa. Se o terminal estiver em foco,
    o digito e o E eram digitados nele e a rodada falhava."""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return False
    buffer = ctypes.create_unicode_buffer(64)
    ctypes.windll.user32.GetClassNameW(hwnd, buffer, 64)
    return buffer.value == GAME_WINDOW_CLASS


def key_edge(vk_code: int, previous: bool):
    current = bool(ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000)
    return current and not previous, current

