from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_HISTORY_LIMIT = 20
DEFAULT_HISTORY_DIR = Path("logs")
DEFAULT_HISTORY_FILE_TEMPLATE = "ocr_history_{date}.json"


@dataclass
class OCRHistoryEntry:
    mode: str
    ocr_text: str
    display_text: str
    translated_text: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class OCRHistoryStore:
    def __init__(self, path: Path | None = None, limit: int = DEFAULT_HISTORY_LIMIT) -> None:
        self._path = path
        self._limit = limit

    def _today_path(self) -> Path:
        if self._path is not None:
            return self._path
        date_key = datetime.now().strftime("%Y-%m-%d")
        return DEFAULT_HISTORY_DIR / DEFAULT_HISTORY_FILE_TEMPLATE.format(date=date_key)

    def add(self, entry: OCRHistoryEntry) -> None:
        path = self._today_path()
        entries = self._load_entries(path)
        entries.insert(0, asdict(entry))
        entries = entries[: self._limit]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_entries(self) -> list[OCRHistoryEntry]:
        entries = self._load_entries(self._today_path())[: self._limit]
        normalized: list[OCRHistoryEntry] = []
        for entry in entries:
            normalized.append(
                OCRHistoryEntry(
                    mode=str(entry.get("mode", "translate")),
                    ocr_text=str(entry.get("ocr_text", "")),
                    display_text=str(entry.get("display_text", "")),
                    translated_text=str(entry.get("translated_text", "")),
                    created_at=str(entry.get("created_at", "")) or datetime.now().isoformat(timespec="seconds"),
                )
            )
        return normalized

    def _load_entries(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        if not isinstance(data, list):
            return []

        return [entry for entry in data if isinstance(entry, dict)]
