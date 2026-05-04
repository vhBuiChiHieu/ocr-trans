from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from main import APP_ICON_PATH, DEFAULT_FONT_SIZE, FONT_SIZE_OPTIONS, _load_tray_icon, create_tray_icon


class FakeController:
    def __init__(self) -> None:
        self.font_sizes: list[int] = []

    def set_result_font_size(self, font_size: int) -> None:
        self.font_sizes.append(font_size)


class MainTrayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_load_tray_icon_prefers_existing_app_icon_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            icon_path = Path(temp_dir) / "app_icon.png"
            icon_path.write_bytes(APP_ICON_PATH.read_bytes())

            with patch("main.APP_ICON_PATH", icon_path):
                icon = _load_tray_icon()

            self.assertIsInstance(icon, QIcon)
            self.assertFalse(icon.isNull())

    def test_create_tray_icon_sets_exit_action_and_menu(self) -> None:
        controller = FakeController()
        tray = create_tray_icon(self.app, controller)

        self.assertIsInstance(tray, QSystemTrayIcon)
        self.assertFalse(tray.icon().isNull())
        menu = tray.contextMenu()
        self.assertIsInstance(menu, QMenu)

        actions = menu.actions()
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0].text(), "Font size")
        self.assertTrue(actions[1].isSeparator())
        self.assertIsInstance(actions[2], QAction)
        self.assertEqual(actions[2].text(), "Exit")

        font_menu = actions[0].menu()
        self.assertIsNotNone(font_menu)
        font_actions = font_menu.actions()
        self.assertEqual([action.text() for action in font_actions], list(FONT_SIZE_OPTIONS.keys()))
        checked_action = next(action for action in font_actions if action.isChecked())
        self.assertEqual(checked_action.text(), "Medium")
        self.assertEqual(FONT_SIZE_OPTIONS[checked_action.text()], DEFAULT_FONT_SIZE)

        font_actions[-1].trigger()
        self.assertEqual(controller.font_sizes, [FONT_SIZE_OPTIONS["Large"]])

        tray.hide()


if __name__ == "__main__":
    unittest.main()
