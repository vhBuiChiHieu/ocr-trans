from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.ocr_history import OCRHistoryEntry, OCRHistoryStore


class OCRHistoryStoreTests(unittest.TestCase):
    def _today_history_path(self, root: Path) -> Path:
        from datetime import datetime

        date_key = datetime.now().strftime("%Y-%m-%d")
        return root / "logs" / f"ocr_history_{date_key}.json"

    def test_add_writes_recent_entries_as_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            store = OCRHistoryStore(limit=2)

            with patch("core.ocr_history.DEFAULT_HISTORY_DIR", temp_root / "logs"):
                store.add(OCRHistoryEntry(mode="translate", ocr_text="hello", translated_text="xin chào", display_text="xin chào"))
                store.add(OCRHistoryEntry(mode="ocr_only", ocr_text="second", display_text="second"))
                store.add(OCRHistoryEntry(mode="both", ocr_text="third", translated_text="ba", display_text="third\n\nba"))

                path = self._today_history_path(temp_root)
                entries = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["mode"], "both")
        self.assertEqual(entries[0]["ocr_text"], "third")
        self.assertEqual(entries[1]["mode"], "ocr_only")
        self.assertIn("created_at", entries[0])

    def test_add_recovers_from_malformed_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            path.write_text("not-json", encoding="utf-8")
            store = OCRHistoryStore(path=path)

            store.add(OCRHistoryEntry(mode="translate", ocr_text="hello", display_text="hello"))

            entries = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["display_text"], "hello")

    def test_list_entries_returns_typed_entries_in_newest_first_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            store = OCRHistoryStore(path=path, limit=3)

            store.add(OCRHistoryEntry(mode="translate", ocr_text="one", display_text="one"))
            store.add(OCRHistoryEntry(mode="both", ocr_text="two", translated_text="hai", display_text="two\n\nhai"))

            entries = store.list_entries()

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].mode, "both")
        self.assertEqual(entries[0].ocr_text, "two")
        self.assertEqual(entries[1].mode, "translate")

    def test_list_entries_recovers_from_malformed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            path.write_text("not-json", encoding="utf-8")
            store = OCRHistoryStore(path=path)

            entries = store.list_entries()

        self.assertEqual(entries, [])

    def test_list_entries_normalizes_missing_created_at(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "mode": "translate",
                            "ocr_text": "hello",
                            "display_text": "hello",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            store = OCRHistoryStore(path=path)

            entries = store.list_entries()

        self.assertEqual(len(entries), 1)
        self.assertTrue(entries[0].created_at)
        self.assertEqual(entries[0].display_text, "hello")

    def test_list_entries_applies_store_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            store = OCRHistoryStore(path=path, limit=2)
            store.add(OCRHistoryEntry(mode="translate", ocr_text="one", display_text="one"))
            store.add(OCRHistoryEntry(mode="translate", ocr_text="two", display_text="two"))
            store.add(OCRHistoryEntry(mode="translate", ocr_text="three", display_text="three"))

            entries = store.list_entries()

        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].display_text, "three")
        self.assertEqual(entries[1].display_text, "two")


if __name__ == "__main__":
    unittest.main()
