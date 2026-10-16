"""Aviso sempre visivel (overlay) no canto da tela, mostrando se o bot esta
ligado ou pausado.

Implementado com a API nativa do Windows (ctypes) em vez de Tkinter: um
interpretador Tcl/Tk rodando numa thread diferente da principal se mostrou
instavel nesta configuracao (derrubava o processo com uma excecao fatal do
Windows). Uma janela Win32 comum, com seu proprio loop de mensagens numa
thread dedicada, e a forma suportada de ter uma janela "sempre no topo" sem
acoplar com a thread que esta rodando o resto do programa.

Todas as funcoes da API do Windows usadas aqui tem `argtypes`/`restype`
declarados explicitamente: sem isso, o ctypes assume `c_int` para qualquer
tipo nao declarado, o que corrompe valores de ponteiro/handle em Python de
64 bits (eles nao cabem em 32 bits) e tende a travar o processo.
"""

import ctypes
import threading
from ctypes import wintypes
from typing import Optional

COLOR_ON = 0x00541D  # COLORREF (0x00BBGGRR): verde escuro
COLOR_PAUSED = 0x1A2CC0  # COLORREF: vermelho

_WS_POPUP = 0x80000000
_WS_VISIBLE = 0x10000000
_WS_EX_LAYERED = 0x00080000
_WS_EX_TOPMOST = 0x00000008
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_NOACTIVATE = 0x08000000
_LWA_ALPHA = 0x2
_SW_SHOWNOACTIVATE = 4
_WM_DESTROY = 0x0002
_WM_PAINT = 0x000F
_WM_CLOSE = 0x0010
_WM_APP = 0x8000
_WM_UPDATE = _WM_APP + 1
_SM_CXSCREEN = 0
_SM_CYSCREEN = 1
_DT_CENTER = 0x0001
_DT_VCENTER = 0x0004
_DT_SINGLELINE = 0x0020
_TRANSPARENT = 1
_FW_BOLD = 700

_WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)


class _WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", _WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class _PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", wintypes.HDC),
        ("fErase", wintypes.BOOL),
        ("rcPaint", wintypes.RECT),
        ("fRestore", wintypes.BOOL),
        ("fIncUpdate", wintypes.BOOL),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASS)]
_user32.RegisterClassW.restype = ctypes.c_ushort

_user32.CreateWindowExW.argtypes = [
    wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID,
]
_user32.CreateWindowExW.restype = wintypes.HWND

_user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD]
_user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.ShowWindow.restype = wintypes.BOOL

_user32.UpdateWindow.argtypes = [wintypes.HWND]
_user32.UpdateWindow.restype = wintypes.BOOL

_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint]
_user32.GetMessageW.restype = ctypes.c_int

_user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
_user32.TranslateMessage.restype = wintypes.BOOL

_user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
_user32.DispatchMessageW.restype = ctypes.c_long

_user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
_user32.PostMessageW.restype = wintypes.BOOL

_user32.PostQuitMessage.argtypes = [ctypes.c_int]
_user32.PostQuitMessage.restype = None

_user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
_user32.DefWindowProcW.restype = ctypes.c_long

_user32.BeginPaint.argtypes = [wintypes.HWND, ctypes.POINTER(_PAINTSTRUCT)]
_user32.BeginPaint.restype = wintypes.HDC

_user32.EndPaint.argtypes = [wintypes.HWND, ctypes.POINTER(_PAINTSTRUCT)]
_user32.EndPaint.restype = wintypes.BOOL

_user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetClientRect.restype = wintypes.BOOL

_user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.HBRUSH]
_user32.FillRect.restype = ctypes.c_int

_user32.DrawTextW.argtypes = [wintypes.HDC, wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.RECT), wintypes.UINT]
_user32.DrawTextW.restype = ctypes.c_int

_user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT), wintypes.BOOL]
_user32.InvalidateRect.restype = wintypes.BOOL

_user32.GetSystemMetrics.argtypes = [ctypes.c_int]
_user32.GetSystemMetrics.restype = ctypes.c_int

_gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
_gdi32.CreateSolidBrush.restype = wintypes.HBRUSH

_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteObject.restype = wintypes.BOOL

_gdi32.CreateFontW.argtypes = [ctypes.c_int] * 5 + [wintypes.DWORD] * 8 + [wintypes.LPCWSTR]
_gdi32.CreateFontW.restype = wintypes.HFONT

_gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi32.SelectObject.restype = wintypes.HGDIOBJ

_gdi32.SetBkMode.argtypes = [wintypes.HDC, ctypes.c_int]
_gdi32.SetBkMode.restype = ctypes.c_int

_gdi32.SetTextColor.argtypes = [wintypes.HDC, wintypes.COLORREF]
_gdi32.SetTextColor.restype = wintypes.COLORREF

_kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE


class StatusOverlay:
    """Janela Win32 minuscula, sem borda, sempre no topo, com um texto curto.

    Roda inteiramente numa thread propria (loop de mensagens incluido) para
    nao interferir com a thread principal do bot nem com a janela de
    selecao de opcoes (farm_bot/gui.py, que usa Tkinter).
    """

    CLASS_NAME = "FarmBotStatusOverlay"
    _class_registered = False
    _class_lock = threading.Lock()
    _wndproc_ref = None  # mantem o callback vivo (ver _register_class_once)
    _windows: dict = {}

    def __init__(self, corner: str = "top-right", text: str = "BOT LIGADO", color: int = COLOR_ON):
        self._corner = corner
        self._text = text
        self._bg = color
        self._hwnd: Optional[int] = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)

    # -- ciclo de vida da janela (tudo abaixo roda na thread do overlay) ----
    def _run(self) -> None:
        try:
            self._register_class_once()
            width, height = 220, 42
            x, y = self._corner_position(width, height)

            hwnd = _user32.CreateWindowExW(
                _WS_EX_LAYERED | _WS_EX_TOPMOST | _WS_EX_TOOLWINDOW | _WS_EX_NOACTIVATE,
                self.CLASS_NAME,
                "FARM BOT",
                _WS_POPUP | _WS_VISIBLE,
                x, y, width, height,
                None, None, _kernel32.GetModuleHandleW(None), None,
            )
            if not hwnd:
                return
            self._hwnd = hwnd
            StatusOverlay._windows[hwnd] = self

            _user32.SetLayeredWindowAttributes(hwnd, 0, 217, _LWA_ALPHA)
            _user32.ShowWindow(hwnd, _SW_SHOWNOACTIVATE)
            _user32.UpdateWindow(hwnd)
        finally:
            self._ready.set()

        if not self._hwnd:
            return

        msg = wintypes.MSG()
        while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    @classmethod
    def _register_class_once(cls) -> None:
        with cls._class_lock:
            if cls._class_registered:
                return
            cls._wndproc_ref = _WNDPROC(cls._wndproc)
            wndclass = _WNDCLASS()
            wndclass.style = 0
            wndclass.lpfnWndProc = cls._wndproc_ref
            wndclass.cbClsExtra = 0
            wndclass.cbWndExtra = 0
            wndclass.hInstance = _kernel32.GetModuleHandleW(None)
            wndclass.hIcon = None
            wndclass.hCursor = None
            wndclass.hbrBackground = None
            wndclass.lpszMenuName = None
            wndclass.lpszClassName = cls.CLASS_NAME
            if not _user32.RegisterClassW(ctypes.byref(wndclass)):
                raise ctypes.WinError(ctypes.get_last_error())
            cls._class_registered = True

    @staticmethod
    def _wndproc(hwnd, message, wparam, lparam):
        overlay = StatusOverlay._windows.get(hwnd)

        if message == _WM_UPDATE and overlay is not None:
            _user32.InvalidateRect(hwnd, None, True)
            return 0

        if message == _WM_PAINT and overlay is not None:
            ps = _PAINTSTRUCT()
            hdc = _user32.BeginPaint(hwnd, ctypes.byref(ps))
            rect = wintypes.RECT()
            _user32.GetClientRect(hwnd, ctypes.byref(rect))

            brush = _gdi32.CreateSolidBrush(overlay._bg)
            _user32.FillRect(hdc, ctypes.byref(rect), brush)
            _gdi32.DeleteObject(brush)

            font = _gdi32.CreateFontW(
                18, 0, 0, 0, _FW_BOLD, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI",
            )
            old_font = _gdi32.SelectObject(hdc, font)
            _gdi32.SetBkMode(hdc, _TRANSPARENT)
            _gdi32.SetTextColor(hdc, 0xFFFFFF)
            _user32.DrawTextW(
                hdc, overlay._text, -1, ctypes.byref(rect),
                _DT_CENTER | _DT_VCENTER | _DT_SINGLELINE,
            )
            _gdi32.SelectObject(hdc, old_font)
            _gdi32.DeleteObject(font)
            _user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0

        if message == _WM_DESTROY:
            StatusOverlay._windows.pop(hwnd, None)
            _user32.PostQuitMessage(0)
            return 0

        return _user32.DefWindowProcW(hwnd, message, wparam, lparam)

    def _corner_position(self, width: int, height: int) -> tuple:
        screen_w = _user32.GetSystemMetrics(_SM_CXSCREEN)
        screen_h = _user32.GetSystemMetrics(_SM_CYSCREEN)
        margin = 12
        positions = {
            "top-left": (margin, margin),
            "top-right": (screen_w - width - margin, margin),
            "bottom-left": (margin, screen_h - height - margin),
            "bottom-right": (screen_w - width - margin, screen_h - height - margin),
        }
        return positions.get(self._corner, positions["top-right"])

    # -- API publica (chamavel de qualquer thread) ---------------------------
    def set_status(self, text: str, color: int) -> None:
        if not self._hwnd:
            return
        self._text = text
        self._bg = color
        _user32.PostMessageW(self._hwnd, _WM_UPDATE, 0, 0)

    def close(self) -> None:
        if self._hwnd:
            _user32.PostMessageW(self._hwnd, _WM_CLOSE, 0, 0)


def create_overlay(corner: str = "top-right") -> Optional[StatusOverlay]:
    """Cria o overlay, devolvendo None se a janela nao puder ser criada
    (ex.: plataforma sem suporte, ou qualquer falha inesperada do Win32)."""
    try:
        overlay = StatusOverlay(corner=corner)
    except Exception:
        return None
    if not overlay._hwnd:
        return None
    return overlay
