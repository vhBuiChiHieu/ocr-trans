from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import QLabel, QWidget

from core.screenshot import MonitorCapture


DEFAULT_FONT_SIZE = 14


class ResultOverlay(QWidget):
    def __init__(self, font_size: int = DEFAULT_FONT_SIZE) -> None:
        super().__init__()
        self._label = QLabel(self)
        self._dismiss_callback: Callable[[], None] | None = None
        self._font_size = font_size
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setStyleSheet("color: white; background: transparent;")
        self._apply_font_size()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(
            "background-color: rgba(18, 18, 18, 208);"
            "border: none;"
            "border-radius: 6px;"
        )
        self.hide()

    @property
    def font_size(self) -> int:
        return self._font_size

    def set_font_size(self, font_size: int) -> None:
        self._font_size = font_size
        self._apply_font_size()
        self._label.adjustSize()

    def _apply_font_size(self) -> None:
        self._label.setFont(QFont("Segoe UI", self._font_size))

    def show_result(self, text: str, anchor_rect: QRect, capture: MonitorCapture, on_dismiss: Callable[[], None]) -> None:
        padding = 12
        gap = 12

        self._dismiss_callback = on_dismiss
        self._label.setText(text)

        content_width = max(1, anchor_rect.width())
        self._label.setFixedWidth(content_width)
        self._label.adjustSize()

        overlay_width = content_width + (padding * 2)
        overlay_height = self._label.height() + (padding * 2)
        self.resize(overlay_width, overlay_height)
        self._label.move(padding, padding)

        monitor_left = round(capture.monitor.left / capture.scale_x)
        monitor_top = round(capture.monitor.top / capture.scale_y)
        monitor_width = round(capture.monitor.width / capture.scale_x)
        monitor_height = round(capture.monitor.height / capture.scale_y)
        monitor_right = monitor_left + monitor_width
        monitor_bottom = monitor_top + monitor_height

        x = monitor_left + anchor_rect.left()
        y_below = monitor_top + anchor_rect.bottom() + gap
        y_above = monitor_top + anchor_rect.top() - overlay_height - gap

        x = max(monitor_left, min(x, monitor_right - overlay_width))
        if y_below + overlay_height <= monitor_bottom:
            y = y_below
        else:
            y = max(monitor_top, y_above)

        self.move(QPoint(x, y))

        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        self.grabKeyboard()

    def hide_result(self) -> None:
        self.releaseKeyboard()
        self.hide()
        self._dismiss_callback = None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._dismiss_callback is not None:
                self._dismiss_callback()
            else:
                self.hide_result()
            return

        super().keyPressEvent(event)
