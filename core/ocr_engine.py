from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

OCR_CONFIDENCE_THRESHOLD = 0.70
TEXT_DET_LIMIT_SIDE_LEN = 960
TEXT_DET_LIMIT_TYPE = "max"
TEXT_DET_THRESH = 0.3
TEXT_DET_BOX_THRESH = 0.6
TEXT_DET_UNCLIP_RATIO = 2.0
TEXT_REC_SCORE_THRESH = 0.0
OCR_MODE_NORMAL = "normal"
OCR_MODE_INVERTED = "inverted"
OCR_MODE_AUTO = "auto"
OCR_MODES = (OCR_MODE_NORMAL, OCR_MODE_INVERTED, OCR_MODE_AUTO)


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


@dataclass(frozen=True)
class OCRCandidate:
    mode: str
    result: OCRResult


class OCREngine:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("ocr_overlay")
        self._ocr = None
        self._runtime = "uninitialized"

    def preload(self) -> None:
        if self._ocr is not None:
            return

        self._logger.info("OCR confidence threshold=%.2f", OCR_CONFIDENCE_THRESHOLD)
        self._ocr = self._create_engine(use_gpu=False)
        self._runtime = "cpu"
        self._logger.info("OCR runtime initialized with CPU")

    def recognize(self, image: Any, mode: str = OCR_MODE_NORMAL) -> OCRResult:
        self.preload()

        if mode == OCR_MODE_NORMAL:
            result = self._recognize_single(image)
        elif mode == OCR_MODE_INVERTED:
            result = self._recognize_single(self._invert_image(image))
        elif mode == OCR_MODE_AUTO:
            result = self._recognize_auto(image)
        else:
            raise ValueError(f"Unsupported OCR mode: {mode}")

        self._logger.info("OCR result status=%s runtime=%s lines=%s mode=%s", result.status, self._runtime, len(result.lines), mode)
        return result

    def _recognize_auto(self, image: Any) -> OCRResult:
        candidates: list[OCRCandidate] = []
        normal_result = self._recognize_single(image)
        if normal_result.status != "error":
            candidates.append(OCRCandidate(mode=OCR_MODE_NORMAL, result=normal_result))

        inverted_result = self._recognize_single(self._invert_image(image))
        if inverted_result.status != "error":
            candidates.append(OCRCandidate(mode=OCR_MODE_INVERTED, result=inverted_result))

        if not candidates:
            return OCRResult(lines=[], display_text="", average_confidence=0.0, status="error")

        return self._select_best_candidate(candidates).result

    def _recognize_single(self, image: Any) -> OCRResult:
        try:
            raw_result = self._predict(image)
        except Exception:
            self._logger.exception("OCR execution failed")
            return OCRResult(lines=[], display_text="", average_confidence=0.0, status="error")

        return self._normalize_result(raw_result)

    def _predict(self, image: Any) -> Any:
        return self._ocr.predict(
            image,
            text_det_limit_side_len=TEXT_DET_LIMIT_SIDE_LEN,
            text_det_limit_type=TEXT_DET_LIMIT_TYPE,
            text_det_thresh=TEXT_DET_THRESH,
            text_det_box_thresh=TEXT_DET_BOX_THRESH,
            text_det_unclip_ratio=TEXT_DET_UNCLIP_RATIO,
            text_rec_score_thresh=TEXT_REC_SCORE_THRESH,
        )

    @property
    def runtime(self) -> str:
        return self._runtime

    def _create_engine(self, use_gpu: bool):
        from paddleocr import PaddleOCR

        device = "gpu:0" if use_gpu else "cpu"
        kwargs: dict[str, Any] = {
            "lang": "en",
            "device": device,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }
        if not use_gpu:
            kwargs["enable_mkldnn"] = False
            kwargs["cpu_threads"] = 1

        return PaddleOCR(**kwargs)

    def _normalize_result(self, raw_result: Any) -> OCRResult:
        lines: list[OCRLine] = []
        fallback_lines: list[OCRLine] = []

        for page_result in raw_result or []:
            if isinstance(page_result, dict):
                texts = page_result.get("rec_texts", []) or []
                scores = page_result.get("rec_scores", []) or []
                for text, confidence in zip(texts, scores):
                    self._collect_line(lines, fallback_lines, text, confidence)
                continue

            page_json = getattr(page_result, "json", None)
            if isinstance(page_json, dict):
                texts = page_json.get("rec_texts", []) or []
                scores = page_json.get("rec_scores", []) or []
                for text, confidence in zip(texts, scores):
                    self._collect_line(lines, fallback_lines, text, confidence)
                continue

            legacy_items = page_result or []
            if legacy_items and isinstance(legacy_items, list) and len(legacy_items[0]) >= 2:
                for item in legacy_items:
                    if not item or len(item) < 2:
                        continue

                    text, confidence = item[1]
                    self._collect_line(lines, fallback_lines, text, confidence)
                continue

            for block in page_result or []:
                for item in block or []:
                    if not item or len(item) < 2:
                        continue

                    text, confidence = item[1]
                    self._collect_line(lines, fallback_lines, text, confidence)

        if not lines and fallback_lines:
            best_line = max(fallback_lines, key=lambda line: line.confidence)
            lines = [best_line]

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

    @staticmethod
    def _select_best_candidate(candidates: list[OCRCandidate]) -> OCRCandidate:
        return max(
            candidates,
            key=lambda candidate: (
                len(candidate.result.lines),
                candidate.result.average_confidence,
                1 if candidate.mode == OCR_MODE_NORMAL else 0,
            ),
        )

    @staticmethod
    def _invert_image(image: Any) -> np.ndarray:
        array = np.asarray(image, dtype=np.uint8)
        return np.ascontiguousarray(255 - array, dtype=np.uint8)

    @staticmethod
    def _collect_line(lines: list[OCRLine], fallback_lines: list[OCRLine], text: Any, confidence: Any) -> None:
        normalized_text = str(text).strip()
        normalized_confidence = float(confidence)
        if not normalized_text:
            return

        line = OCRLine(text=normalized_text, confidence=normalized_confidence)
        if normalized_confidence >= OCR_CONFIDENCE_THRESHOLD:
            lines.append(line)
            return

        if normalized_confidence >= 0.5 and any(char.isalnum() for char in normalized_text) and len(normalized_text) >= 4:
            fallback_lines.append(line)
