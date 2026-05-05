from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_HISTORY_LIMIT = 20
DEFAULT_HISTORY_PATH = Path("logs") / "ocr_history.json"


@dataclass
class OCRHistoryEntry:
    mode: str
    ocr_text: str
    display_text: str
    translated_text: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class OCRHistoryStore:
    def __init__(self, path: Path = DEFAULT_HISTORY_PATH, limit: int = DEFAULT_HISTORY_LIMIT) -> None:
        self._path = path
        self._limit = limit

    def add(self, entry: OCRHistoryEntry) -> None:
        entries = self._load_entries()
        entries.insert(0, asdict(entry))
        entries = entries[: self._limit]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_entries(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        return [entry for entry in data if isinstance(entry, dict)]
