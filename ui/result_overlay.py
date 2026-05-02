from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QPoint, QRect, Qt
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import QLabel, QWidget

from core.screenshot import MonitorCapture


class ResultOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._label = QLabel(self)
        self._dismiss_callback: Callable[[], None] | None = None
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._label.setStyleSheet("color: white; background: transparent;")
        self._label.setFont(QFont("Segoe UI", 11))

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(
            "background-color: rgba(15, 15, 15, 220);"
            "border: 1px solid rgba(0, 180, 255, 180);"
            "border-radius: 10px;"
        )
        self.hide()

    def show_result(self, text: str, anchor_rect: QRect, capture: MonitorCapture, on_dismiss: Callable[[], None]) -> None:
        self._dismiss_callback = on_dismiss
        self._label.setText(text)
        self._label.adjustSize()

        content_width = min(max(self._label.sizeHint().width(), 220), 520)
        self._label.setFixedWidth(content_width)
        self._label.adjustSize()

        overlay_width = self._label.width() + 24
        overlay_height = self._label.height() + 24
        self.resize(overlay_width, overlay_height)
        self._label.move(12, 12)

        monitor_left = round(capture.monitor.left / capture.scale_x)
        monitor_top = round(capture.monitor.top / capture.scale_y)
        monitor_width = round(capture.monitor.width / capture.scale_x)
        monitor_height = round(capture.monitor.height / capture.scale_y)

        x = monitor_left + anchor_rect.right() + 12
        y = monitor_top + anchor_rect.top()
        max_x = monitor_left + max(0, monitor_width - overlay_width)
        max_y = monitor_top + max(0, monitor_height - overlay_height)
        self.move(QPoint(min(x, max_x), min(y, max_y)))

        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def hide_result(self) -> None:
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
