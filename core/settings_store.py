from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS_PATH = Path("config") / "settings.json"


@dataclass(frozen=True)
class AppSettings:
    font_size: int = 14
    font_family: str = "Segoe UI"
    output_mode: str = "translate"


class SettingsStore:
    def __init__(self, path: Path = DEFAULT_SETTINGS_PATH) -> None:
        self._path = path

    def load(self) -> AppSettings:
        if not self._path.exists():
            return AppSettings()

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return AppSettings()

        if not isinstance(data, dict):
            return AppSettings()

        settings = AppSettings()
        return replace(
            settings,
            font_size=self._read_int(data, "font_size", settings.font_size),
            font_family=self._read_str(data, "font_family", settings.font_family),
            output_mode=self._read_str(data, "output_mode", settings.output_mode),
        )

    def save(self, settings: AppSettings) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _read_int(data: dict[str, Any], key: str, default: int) -> int:
        value = data.get(key)
        if isinstance(value, int):
            return value
        return default

    @staticmethod
    def _read_str(data: dict[str, Any], key: str, default: str) -> str:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
        return default
