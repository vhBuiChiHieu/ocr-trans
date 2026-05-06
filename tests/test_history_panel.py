from __future__ import annotations

import unittest

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from core.ocr_history import OCRHistoryEntry
from ui.history_panel import (
    COLLAPSED_HEIGHT,
    COLLAPSED_TOP_MARGIN,
    COLLAPSED_VERTICAL_ANCHOR_RATIO,
    COLLAPSED_WIDTH,
    DEFAULT_PANEL_WIDTH,
    HistoryPanel,
    MAX_PANEL_WIDTH,
    MIN_PANEL_WIDTH,
)


class HistoryPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_default_mode_is_collapsed(self) -> None:
        panel = HistoryPanel()

        self.assertTrue(panel.is_collapsed())
        self.assertEqual(panel.minimumWidth(), COLLAPSED_WIDTH)

    def test_collapsed_toggle_shows_count_tooltip(self) -> None:
        panel = HistoryPanel()
        panel.set_entries(
            [
                OCRHistoryEntry(mode="both", ocr_text="a", display_text="a"),
                OCRHistoryEntry(mode="both", ocr_text="b", display_text="b"),
            ]
        )

        toggle = panel.findChild(QPushButton, "historyToggle")
        self.assertIsNotNone(toggle)
        self.assertEqual(toggle.text(), "H")
        self.assertIn("(2)", toggle.toolTip())

    def test_toggle_callback_is_called_with_new_state(self) -> None:
        panel = HistoryPanel()
        states = []
        panel.set_toggle_callback(states.append)

        toggle = panel.findChild(QPushButton, "historyToggle")
        self.assertIsNotNone(toggle)
        toggle.click()

        self.assertEqual(states, [False])

    def test_set_entries_renders_empty_state(self) -> None:
        panel = HistoryPanel()
        panel.set_collapsed(False)

        panel.set_entries([])

        labels = panel.findChildren(QLabel, "historyMeta")
        self.assertTrue(any("Chưa có kết quả OCR." in label.text() for label in labels))

    def test_set_entries_renders_newest_first_preview(self) -> None:
        panel = HistoryPanel()
        panel.set_collapsed(False)
        entries = [
            OCRHistoryEntry(mode="both", ocr_text="new", display_text="new item", created_at="2026-05-06T12:00:00"),
            OCRHistoryEntry(mode="translate", ocr_text="old", display_text="old item", created_at="2026-05-06T11:00:00"),
        ]

        panel.set_entries(entries)

        text_labels = panel.findChildren(QLabel, "historyText")
        self.assertEqual(text_labels[0].text(), "new item")
        self.assertEqual(text_labels[1].text(), "old item")

    def test_set_panel_width_applies_bounds(self) -> None:
        panel = HistoryPanel()
        panel.set_collapsed(False)

        panel.set_panel_width(MIN_PANEL_WIDTH - 100)
        self.assertEqual(panel.width(), MIN_PANEL_WIDTH)

        panel.set_panel_width(MAX_PANEL_WIDTH + 100)
        self.assertEqual(panel.width(), MAX_PANEL_WIDTH)

    def test_resize_event_calls_width_callback_only_in_expanded_mode(self) -> None:
        panel = HistoryPanel()
        values = []
        panel.set_width_changed_callback(values.append)

        panel.show()
        self.app.processEvents()
        panel.resize(QSize(COLLAPSED_WIDTH, COLLAPSED_HEIGHT))
        self.app.processEvents()
        self.assertEqual(values, [])

        panel.set_collapsed(False)
        panel.resize(QSize(DEFAULT_PANEL_WIDTH + 10, 600))
        self.app.processEvents()
        self.assertEqual(values[-1], DEFAULT_PANEL_WIDTH + 10)
        panel.hide()

    def test_show_docked_right_sets_geometry_for_collapsed_mode(self) -> None:
        panel = HistoryPanel(width=320)
        panel.set_collapsed(True)

        panel.show_docked_right()

        screen = QApplication.primaryScreen()
        self.assertIsNotNone(screen)
        available = screen.availableGeometry()
        expected_x = available.right() - panel.width() + 1
        expected_y = available.top() + int((available.height() - COLLAPSED_HEIGHT) * COLLAPSED_VERTICAL_ANCHOR_RATIO)
        expected_y = max(available.top() + COLLAPSED_TOP_MARGIN, expected_y)
        self.assertEqual(panel.geometry().x(), expected_x)
        self.assertEqual(panel.geometry().y(), expected_y)
        self.assertEqual(panel.geometry().height(), COLLAPSED_HEIGHT)
        panel.hide()

    def test_show_docked_right_sets_geometry_for_expanded_mode(self) -> None:
        panel = HistoryPanel(width=320)
        panel.set_collapsed(False)

        panel.show_docked_right()

        screen = QApplication.primaryScreen()
        self.assertIsNotNone(screen)
        available = screen.availableGeometry()
        expected_x = available.right() - panel.width() + 1
        self.assertEqual(panel.geometry().x(), expected_x)
        self.assertEqual(panel.geometry().y(), available.top())
        self.assertEqual(panel.geometry().height(), available.height())
        panel.hide()


if __name__ == "__main__":
    unittest.main()
