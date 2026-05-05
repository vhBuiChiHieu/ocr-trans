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

            store.save(AppSettings(font_size=15, font_family="JetBrains Mono", output_mode="both"))
            settings = store.load()
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(settings.font_size, 15)
        self.assertEqual(settings.font_family, "JetBrains Mono")
        self.assertEqual(settings.output_mode, "both")
        self.assertEqual(data["font_family"], "JetBrains Mono")

    def test_load_recovers_from_malformed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("not-json", encoding="utf-8")
            store = SettingsStore(path)

            settings = store.load()

        self.assertEqual(settings, AppSettings())


if __name__ == "__main__":
    unittest.main()
