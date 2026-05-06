from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.settings_store import AppSettings, SettingsStore


class SettingsStoreTests(unittest.TestCase):
    def test_load_returns_defaults_when_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store = SettingsStore(Path(temp_dir) / "settings.json")

            settings = store.load()

        self.assertEqual(settings, AppSettings())

    def test_save_and_load_round_trips_settings_as_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            store = SettingsStore(path)

            store.save(
                AppSettings(
                    font_size=15,
                    font_family="JetBrains Mono",
                    output_mode="both",
                    translator_script="local_translate_gemma_4b.py",
                    history_panel_width=420,
                    history_panel_visible=False,
                    history_panel_collapsed=False,
                )
            )
            settings = store.load()
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(settings.font_size, 15)
        self.assertEqual(settings.font_family, "JetBrains Mono")
        self.assertEqual(settings.output_mode, "both")
        self.assertEqual(settings.translator_script, "local_translate_gemma_4b.py")
        self.assertEqual(settings.history_panel_width, 420)
        self.assertEqual(settings.history_panel_visible, False)
        self.assertEqual(settings.history_panel_collapsed, False)
        self.assertEqual(data["font_family"], "JetBrains Mono")
        self.assertEqual(data["history_panel_width"], 420)
        self.assertEqual(data["history_panel_visible"], False)
        self.assertEqual(data["history_panel_collapsed"], False)

    def test_load_ignores_invalid_history_panel_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "font_size": 14,
                        "history_panel_width": "wide",
                        "history_panel_visible": "yes",
                        "history_panel_collapsed": "no",
                    }
                ),
                encoding="utf-8",
            )
            store = SettingsStore(path)

            settings = store.load()

        self.assertEqual(settings.history_panel_width, AppSettings().history_panel_width)
        self.assertEqual(settings.history_panel_visible, AppSettings().history_panel_visible)
        self.assertEqual(settings.history_panel_collapsed, AppSettings().history_panel_collapsed)

    def test_load_recovers_from_malformed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("not-json", encoding="utf-8")
            store = SettingsStore(path)

            settings = store.load()

        self.assertEqual(settings, AppSettings())


if __name__ == "__main__":
    unittest.main()
