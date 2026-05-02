from __future__ import annotations

import unittest
from types import SimpleNamespace

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QApplication

from core.screenshot import MonitorBounds, MonitorCapture
from ui.selection_overlay import SelectionOverlay, SelectionResult


class SelectionOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.overlay = SelectionOverlay()
        self.confirmed: list[SelectionResult] = []
        self.cancelled = 0
        self.focus_states: list[bool] = []
        self.capture = MonitorCapture(
            image=SimpleNamespace(width=20, height=20, rgb=b"\x00" * (20 * 20 * 3)),
            monitor=MonitorBounds(left=0, top=0, width=20, height=20),
            scale_x=1.0,
            scale_y=1.0,
        )
        self.overlay.show_capture(
            capture=self.capture,
            on_confirm=self.confirmed.append,
            on_cancel=self._handle_cancel,
            on_focus_ready=self.focus_states.append,
        )

    def tearDown(self) -> None:
        self.overlay.hide_overlay()

    def _handle_cancel(self) -> None:
        self.cancelled += 1

    @staticmethod
    def _mouse_event(event_type, point: tuple[int, int]) -> QMouseEvent:
        pos = QPointF(*point)
        return QMouseEvent(
            event_type,
            pos,
            pos,
            pos,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def test_drag_release_confirms_selection_immediately(self) -> None:
        self.overlay.mousePressEvent(self._mouse_event(QMouseEvent.Type.MouseButtonPress, (2, 3)))
        self.overlay.mouseMoveEvent(self._mouse_event(QMouseEvent.Type.MouseMove, (8, 9)))
        self.overlay.mouseReleaseEvent(self._mouse_event(QMouseEvent.Type.MouseButtonRelease, (8, 9)))

        self.assertEqual(len(self.confirmed), 1)
        self.assertEqual(self.confirmed[0].rect, self.confirmed[0].rect.normalized())
        self.assertEqual(self.confirmed[0].rect.topLeft(), QPoint(2, 3))
        self.assertEqual(self.confirmed[0].rect.bottomRight(), QPoint(8, 9))
        self.assertEqual(self.overlay.selection_rect, self.overlay.selection_rect.normalized())
        self.assertTrue(self.overlay.selection_rect.isNull())

    def test_click_two_corners_confirms_selection(self) -> None:
        self.overlay.mousePressEvent(self._mouse_event(QMouseEvent.Type.MouseButtonPress, (4, 5)))
        self.assertTrue(self.overlay.selection_rect.isNull())
        self.overlay.mouseReleaseEvent(self._mouse_event(QMouseEvent.Type.MouseButtonRelease, (4, 5)))

        self.assertEqual(len(self.confirmed), 0)
        self.assertTrue(self.overlay.selection_rect.isNull())

        self.overlay.mouseMoveEvent(self._mouse_event(QMouseEvent.Type.MouseMove, (10, 12)))
        self.assertEqual(self.overlay.selection_rect.topLeft(), QPoint(4, 5))
        self.assertEqual(self.overlay.selection_rect.bottomRight(), QPoint(10, 12))

        self.overlay.mousePressEvent(self._mouse_event(QMouseEvent.Type.MouseButtonPress, (10, 12)))
        self.overlay.mouseReleaseEvent(self._mouse_event(QMouseEvent.Type.MouseButtonRelease, (10, 12)))

        self.assertEqual(len(self.confirmed), 1)
        self.assertEqual(self.confirmed[0].rect.topLeft(), QPoint(4, 5))
        self.assertEqual(self.confirmed[0].rect.bottomRight(), QPoint(10, 12))

    def test_single_click_does_not_leave_drag_state_stuck(self) -> None:
        self.overlay.mousePressEvent(self._mouse_event(QMouseEvent.Type.MouseButtonPress, (6, 7)))
        self.overlay.mouseReleaseEvent(self._mouse_event(QMouseEvent.Type.MouseButtonRelease, (6, 7)))
        self.overlay.mouseMoveEvent(self._mouse_event(QMouseEvent.Type.MouseMove, (9, 11)))

        self.assertEqual(len(self.confirmed), 0)
        self.assertEqual(self.overlay.selection_rect.topLeft(), QPoint(6, 7))
        self.assertEqual(self.overlay.selection_rect.bottomRight(), QPoint(9, 11))


if __name__ == "__main__":
    unittest.main()
