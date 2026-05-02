from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

OCR_CONFIDENCE_THRESHOLD = 0.70


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float


@dataclass(frozen=True)
class OCRResult:
    lines: list[OCRLine]
    display_text: str
    average_confidence: float
    status: str


class OCREngine:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("ocr_overlay")
        self._ocr = None
        self._runtime = "uninitialized"

    def preload(self) -> None:
        if self._ocr is not None:
            return

        self._logger.info("OCR confidence threshold=%.2f", OCR_CONFIDENCE_THRESHOLD)
        try:
            self._ocr = self._create_engine(use_gpu=True)
            self._runtime = "gpu"
            self._logger.info("OCR runtime initialized with GPU")
            return
        except Exception:
            self._logger.exception("GPU OCR initialization failed")

        self._ocr = self._create_engine(use_gpu=False)
        self._runtime = "cpu"
        self._logger.info("OCR runtime initialized with CPU fallback")

    def recognize(self, image: Any) -> OCRResult:
        self.preload()

        try:
            raw_result = self._ocr.ocr(image)
        except Exception:
            if self._runtime != "gpu":
                self._logger.exception("OCR execution failed")
                return OCRResult(lines=[], display_text="", average_confidence=0.0, status="error")

            self._logger.exception("GPU OCR execution failed")
            self._ocr = self._create_engine(use_gpu=False)
            self._runtime = "cpu"
            self._logger.info("OCR runtime switched to CPU fallback")

            try:
                raw_result = self._ocr.ocr(image)
            except Exception:
                self._logger.exception("CPU OCR execution failed")
                return OCRResult(lines=[], display_text="", average_confidence=0.0, status="error")

        result = self._normalize_result(raw_result)
        self._logger.info("OCR result status=%s runtime=%s lines=%s", result.status, self._runtime, len(result.lines))
        return result

    @property
    def runtime(self) -> str:
        return self._runtime

    def _create_engine(self, use_gpu: bool):
        from paddleocr import PaddleOCR

        device = "gpu:0" if use_gpu else "cpu"
        return PaddleOCR(
            lang="en",
            device=device,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def _normalize_result(self, raw_result: Any) -> OCRResult:
        lines: list[OCRLine] = []

        for page_result in raw_result or []:
            page_json = getattr(page_result, "json", None)
            if isinstance(page_json, dict):
                texts = page_json.get("rec_texts", []) or []
                scores = page_json.get("rec_scores", []) or []
                for text, confidence in zip(texts, scores):
                    normalized_text = str(text).strip()
                    normalized_confidence = float(confidence)
                    if not normalized_text or normalized_confidence < OCR_CONFIDENCE_THRESHOLD:
                        continue

                    lines.append(OCRLine(text=normalized_text, confidence=normalized_confidence))
                continue

            legacy_items = page_result or []
            if legacy_items and isinstance(legacy_items, list) and len(legacy_items[0]) >= 2:
                for item in legacy_items:
                    if not item or len(item) < 2:
                        continue

                    text, confidence = item[1]
                    normalized_text = str(text).strip()
                    normalized_confidence = float(confidence)
                    if not normalized_text or normalized_confidence < OCR_CONFIDENCE_THRESHOLD:
                        continue

                    lines.append(OCRLine(text=normalized_text, confidence=normalized_confidence))
                continue

            for block in page_result or []:
                for item in block or []:
                    if not item or len(item) < 2:
                        continue

                    text, confidence = item[1]
                    normalized_text = str(text).strip()
                    normalized_confidence = float(confidence)
                    if not normalized_text or normalized_confidence < OCR_CONFIDENCE_THRESHOLD:
                        continue

                    lines.append(OCRLine(text=normalized_text, confidence=normalized_confidence))

        if not lines:
            return OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")

        display_text = "\n".join(line.text for line in lines)
        average_confidence = sum(line.confidence for line in lines) / len(lines)
        return OCRResult(
            lines=lines,
            display_text=display_text,
            average_confidence=average_confidence,
            status="ok",
        )
