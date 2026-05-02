from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from typing import Callable

from PyQt6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QTimer

WM_HOTKEY = 0x0312
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_Z = 0x5A
HOTKEY_ID = 1


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", wintypes.LONG),
        ("pt_y", wintypes.LONG),
    ]


class _HotkeyEventFilter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id: int, callback: Callable[[], None]) -> None:
        super().__init__()
        self._hotkey_id = hotkey_id
        self._callback = callback

    # Comment quan trọng: Qt chuyển MSG* của Windows vào native event filter.
    def nativeEventFilter(self, event_type: bytes, message: int) -> tuple[bool, int]:
        if event_type != b"windows_generic_MSG":
            return False, 0

        msg = MSG.from_address(int(message))
        if msg.message != WM_HOTKEY or int(msg.wParam) != self._hotkey_id:
            return False, 0

        QTimer.singleShot(0, self._callback)
        return True, 0


class HotkeyManager:
    def __init__(self, logger: logging.Logger, on_hotkey: Callable[[], None]) -> None:
        self._logger = logger
        self._on_hotkey = on_hotkey
        self._event_filter: _HotkeyEventFilter | None = None
        self._registered = False
        self._user32 = ctypes.windll.user32

    def start(self) -> None:
        if self._registered:
            return

        if not hasattr(ctypes, "windll"):
            self._logger.error("Global hotkey backend requires Windows")
            return

        app = QCoreApplication.instance()
        if app is None:
            raise RuntimeError("QCoreApplication must exist before starting hotkey manager")

        if not self._user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_Z):
            error_code = ctypes.get_last_error()
            self._logger.error(
                "Failed to register global hotkey Ctrl+Shift+Z (error=%s)",
                error_code,
            )
            return

        self._event_filter = _HotkeyEventFilter(HOTKEY_ID, self._on_hotkey)
        app.installNativeEventFilter(self._event_filter)
        self._registered = True
        self._logger.info("Registered global hotkey Ctrl+Shift+Z")

    def stop(self) -> None:
        app = QCoreApplication.instance()
        if app is not None and self._event_filter is not None:
            app.removeNativeEventFilter(self._event_filter)
            self._event_filter = None

        if not self._registered:
            return

        if self._user32.UnregisterHotKey(None, HOTKEY_ID):
            self._logger.info("Unregistered global hotkey Ctrl+Shift+Z")
        else:
            error_code = ctypes.get_last_error()
            self._logger.warning(
                "Failed to unregister global hotkey Ctrl+Shift+Z (error=%s)",
                error_code,
            )

        self._registered = False

    @property
    def is_registered(self) -> bool:
        return self._registered
