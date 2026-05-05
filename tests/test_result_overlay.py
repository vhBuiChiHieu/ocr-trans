from __future__ import annotations

import unittest
from types import SimpleNamespace

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication

from core.screenshot import MonitorBounds, MonitorCapture
from ui.result_overlay import DEFAULT_FONT_SIZE, ResultOverlay


class ResultOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.overlay = ResultOverlay()
        self.capture = MonitorCapture(
            image=SimpleNamespace(width=300, height=200),
            monitor=MonitorBounds(left=100, top=50, width=300, height=200),
            scale_x=1.0,
            scale_y=1.0,
        )

    def tearDown(self) -> None:
        self.overlay.hide_result()

    def test_overlay_uses_minimal_style(self) -> None:
        style = self.overlay.styleSheet()

        self.assertIn("border: none", style)
        self.assertIn("border-radius: 6px", style)
        self.assertIn("background-color: rgba(18, 18, 18, 208)", style)

    def test_overlay_uses_larger_default_font_size(self) -> None:
        self.assertEqual(self.overlay.font_size, DEFAULT_FONT_SIZE)
        self.assertEqual(self.overlay._label.font().pointSize(), DEFAULT_FONT_SIZE)

    def test_set_font_family_updates_label_font(self) -> None:
        self.overlay.set_font_family("Arial")

        self.assertEqual(self.overlay.font_family, "Arial")
        self.assertEqual(self.overlay._label.font().family(), "Arial")

    def test_show_result_matches_anchor_width_and_places_below(self) -> None:
        anchor_rect = QRect(20, 30, 120, 40)

        self.overlay.show_result("Detected text", anchor_rect, self.capture, on_dismiss=lambda: None)

        self.assertEqual(self.overlay.width(), 144)
        self.assertEqual(self.overlay._label.width(), 120)
        self.assertEqual(self.overlay.x(), 120)
        self.assertEqual(self.overlay.y(), 131)

    def test_show_result_moves_above_when_below_would_overflow(self) -> None:
        anchor_rect = QRect(20, 150, 120, 40)

        self.overlay.show_result("Detected text", anchor_rect, self.capture, on_dismiss=lambda: None)

        self.assertEqual(self.overlay.width(), 144)
        self.assertEqual(self.overlay._label.width(), 120)
        self.assertEqual(self.overlay.x(), 120)
        self.assertEqual(self.overlay.y() + self.overlay.height(), 188)

    def test_escape_dismisses_overlay(self) -> None:
        dismissed = []
        anchor_rect = QRect(20, 30, 120, 40)
        self.overlay.show_result("Detected text", anchor_rect, self.capture, on_dismiss=lambda: dismissed.append(True))

        event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        self.overlay.keyPressEvent(event)

        self.assertEqual(dismissed, [True])


if __name__ == "__main__":
    unittest.main()
