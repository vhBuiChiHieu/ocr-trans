from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.ocr_history import OCRHistoryEntry, OCRHistoryStore


class OCRHistoryStoreTests(unittest.TestCase):
    def test_add_writes_recent_entries_as_utf8_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "history.json"
            store = OCRHistoryStore(path=path, limit=2)

            store.add(OCRHistoryEntry(mode="translate", ocr_text="hello", translated_text="xin chào", display_text="xin chào"))
            store.add(OCRHistoryEntry(mode="ocr_only", ocr_text="second", display_text="second"))
            store.add(OCRHistoryEntry(mode="both", ocr_text="third", translated_text="ba", display_text="third\n\nba"))

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


if __name__ == "__main__":
    unittest.main()
