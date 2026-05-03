from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.ocr_engine import OCR_MODE_NORMAL, OCREngine, OCRResult
from core.preprocessor import PRESET_BASELINE, ImagePreprocessor


@dataclass(frozen=True)
class OCRPipelineConfig:
    preset: str = PRESET_BASELINE
    mode: str = OCR_MODE_NORMAL


class OCRPipeline:
    def __init__(
        self,
        preprocessor: ImagePreprocessor,
        ocr_engine: OCREngine,
        config: OCRPipelineConfig | None = None,
    ) -> None:
        self._preprocessor = preprocessor
        self._ocr_engine = ocr_engine
        self._config = config or OCRPipelineConfig()

    def run(self, image: Any, preset: str | None = None, mode: str | None = None) -> OCRResult:
        active_preset = preset or self._config.preset
        active_mode = mode or self._config.mode
        prepared = self._preprocessor.preprocess(image, preset=active_preset)
        return self._ocr_engine.recognize(prepared, mode=active_mode)
