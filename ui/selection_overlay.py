from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import QPoint, QRect, Qt, QTimer
from PyQt6.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget

from core.screenshot import MonitorBounds, MonitorCapture


@dataclass(frozen=True)
class SelectionResult:
    rect: QRect


class SelectionOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._capture: MonitorCapture | None = None
        self._background = QPixmap()
        self._drag_start: QPoint | None = None
        self._drag_current: QPoint | None = None
        self._click_anchor: QPoint | None = None
        self._selection_rect = QRect()
        self._on_confirm: Callable[[SelectionResult], None] | None = None
        self._on_cancel: Callable[[], None] | None = None

        self.setMouseTracking(True)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()

    def show_capture(
        self,
        capture: MonitorCapture,
        on_confirm: Callable[[SelectionResult], None],
        on_cancel: Callable[[], None],
        on_focus_ready: Callable[[bool], None],
    ) -> None:
        self._capture = capture
        self._background = self._pixmap_from_capture(capture)
        self._drag_start = None
        self._drag_current = None
        self._click_anchor = None
        self._selection_rect = QRect()
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel

        logical_bounds = self._logical_bounds(capture.monitor, capture.scale_x, capture.scale_y)
        self.setGeometry(logical_bounds)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        QTimer.singleShot(0, lambda: on_focus_ready(self.hasFocus()))

    def hide_overlay(self) -> None:
        self.hide()
        self._drag_start = None
        self._drag_current = None
        self._click_anchor = None
        self._selection_rect = QRect()
        self._on_confirm = None
        self._on_cancel = None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            if self._on_cancel is not None:
                self._on_cancel()
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not self._selection_rect.isNull():
            if self._on_confirm is not None:
                self._on_confirm(SelectionResult(rect=QRect(self._selection_rect)))
            return

        super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        point = event.position().toPoint()
        self._drag_start = point
        self._drag_current = point
        if self._click_anchor is None:
            self._selection_rect = QRect()
        else:
            self._selection_rect = QRect(self._click_anchor, point).normalized()
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        point = event.position().toPoint()

        if self._drag_start is not None:
            self._drag_current = point
            self._selection_rect = QRect(self._drag_start, self._drag_current).normalized()
            self.update()
            return

        if self._click_anchor is not None:
            self._selection_rect = QRect(self._click_anchor, point).normalized()
            self.update()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._drag_start is None:
            super().mouseReleaseEvent(event)
            return

        release_point = event.position().toPoint()
        selection_rect = QRect(self._drag_start, release_point).normalized()
        moved = (release_point - self._drag_start).manhattanLength() > 3
        self._drag_start = None
        self._drag_current = None

        if moved:
            self._selection_rect = selection_rect
            self.update()
            self._confirm_current_selection()
            return

        if self._click_anchor is None:
            self._click_anchor = release_point
            self._selection_rect = QRect()
            self.update()
            return

        self._selection_rect = QRect(self._click_anchor, release_point).normalized()
        self._click_anchor = None
        self.update()
        self._confirm_current_selection()

    def _confirm_current_selection(self) -> None:
        if self._on_confirm is None or self._selection_rect.isNull():
            return

        self._on_confirm(SelectionResult(rect=QRect(self._selection_rect)))
        self._click_anchor = None
        self._drag_start = None
        self._drag_current = None
        self._selection_rect = QRect()
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self._background)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))

        if self._selection_rect.isNull():
            return

        painter.drawPixmap(self._selection_rect, self._background, self._selection_rect)
        painter.setPen(QPen(QColor(0, 180, 255), 2))
        painter.drawRect(self._selection_rect)



    def _pixmap_from_capture(self, capture: MonitorCapture) -> QPixmap:
        rgb = bytes(capture.image.rgb)
        image = QImage(
            rgb,
            capture.image.width,
            capture.image.height,
            capture.image.width * 3,
            QImage.Format.Format_RGB888,
        )
        return QPixmap.fromImage(image.copy())

    # Comment quan trọng: overlay dùng toạ độ logical local; crop mapping task sau sẽ đổi sang physical pixel.
    @staticmethod
    def _logical_bounds(monitor: MonitorBounds, scale_x: float, scale_y: float) -> QRect:
        return QRect(
            round(monitor.left / scale_x),
            round(monitor.top / scale_y),
            round(monitor.width / scale_x),
            round(monitor.height / scale_y),
        )

    @property
    def selection_rect(self) -> QRect:
        return QRect(self._selection_rect)

    @property
    def capture(self) -> MonitorCapture | None:
        return self._capture
