from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from main import (
    APP_ICON_PATH,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
    FONT_SIZE_OPTIONS,
    OUTPUT_MODE_OPTIONS,
    _load_tray_icon,
    create_tray_icon,
    load_font_family_options,
)


class FakeController:
    def __init__(self) -> None:
        self.font_sizes: list[int] = []
        self.output_modes: list[str] = []
        self.font_families: list[str] = []

    def set_result_font_size(self, font_size: int) -> None:
        self.font_sizes.append(font_size)

    def set_result_font_family(self, font_family: str) -> None:
        self.font_families.append(font_family)

    def set_output_mode(self, mode: str) -> None:
        self.output_modes.append(mode)


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

    def test_load_font_family_options_returns_default_when_font_dir_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_dir = Path(temp_dir) / "missing"

            options = load_font_family_options(missing_dir)

        self.assertEqual(options, {"Default": DEFAULT_FONT_FAMILY})

    def test_create_tray_icon_sets_exit_action_and_menu(self) -> None:
        controller = FakeController()
        tray = create_tray_icon(self.app, controller)

        self.assertIsInstance(tray, QSystemTrayIcon)
        self.assertFalse(tray.icon().isNull())
        menu = tray.contextMenu()
        self.assertIsInstance(menu, QMenu)

        actions = menu.actions()
        self.assertEqual(len(actions), 5)
        self.assertEqual(actions[0].text(), "Font size")
        self.assertEqual(actions[1].text(), "Font family")
        self.assertEqual(actions[2].text(), "Output mode")
        self.assertTrue(actions[3].isSeparator())
        self.assertIsInstance(actions[4], QAction)
        self.assertEqual(actions[4].text(), "Exit")

        font_menu = actions[0].menu()
        self.assertIsNotNone(font_menu)
        font_actions = font_menu.actions()
        self.assertEqual([action.text() for action in font_actions], list(FONT_SIZE_OPTIONS.keys()))
        checked_action = next(action for action in font_actions if action.isChecked())
        self.assertEqual(checked_action.text(), "Medium")
        self.assertEqual(FONT_SIZE_OPTIONS[checked_action.text()], DEFAULT_FONT_SIZE)

        font_actions[-1].trigger()
        self.assertEqual(controller.font_sizes, [FONT_SIZE_OPTIONS["Large"]])

        font_family_menu = actions[1].menu()
        self.assertIsNotNone(font_family_menu)
        font_family_actions = font_family_menu.actions()
        self.assertEqual([action.text() for action in font_family_actions], ["Default"])
        self.assertTrue(font_family_actions[0].isChecked())
        font_family_actions[0].trigger()
        self.assertEqual(controller.font_families, [DEFAULT_FONT_FAMILY])

        output_menu = actions[2].menu()
        self.assertIsNotNone(output_menu)
        output_actions = output_menu.actions()
        self.assertEqual([action.text() for action in output_actions], list(OUTPUT_MODE_OPTIONS.keys()))
        checked_output_action = next(action for action in output_actions if action.isChecked())
        self.assertEqual(checked_output_action.text(), "Translate")

        output_actions[-1].trigger()
        self.assertEqual(controller.output_modes, [OUTPUT_MODE_OPTIONS["Both"]])

        tray.hide()


if __name__ == "__main__":
    unittest.main()
