from __future__ import annotations

import logging
from dataclasses import dataclass
from statistics import median
from typing import Any

Point = tuple[float, float]
Box = tuple[Point, ...]

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
    box: Box | None = None
    center_x: float | None = None
    center_y: float | None = None
    height: float | None = None


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

    def _log_result_details(self, result: OCRResult) -> None:
        self._logger.info(
            "OCR detail: status=%s avg_conf=%.3f line_count=%d display_text=%r",
            result.status,
            result.average_confidence,
            len(result.lines),
            result.display_text,
        )
        if not result.lines:
            return

        self._logger.info(
            "OCR detail lines:\n%s",
            "\n".join(self._format_line_detail(index, line) for index, line in enumerate(result.lines, start=1)),
        )

    @staticmethod
    def _format_line_detail(index: int, line: OCRLine) -> str:
        center_x = "-" if line.center_x is None else f"{line.center_x:.1f}"
        center_y = "-" if line.center_y is None else f"{line.center_y:.1f}"
        height = "-" if line.height is None else f"{line.height:.1f}"
        return (
            f"[{index:02d}] conf={line.confidence:.3f} center=({center_x}, {center_y}) "
            f"height={height} box={OCREngine._format_box(line.box)} text={line.text!r}"
        )

    @staticmethod
    def _format_box(box: Box | None) -> str:
        if not box:
            return "-"
        return "[" + ", ".join(f"({x:.1f},{y:.1f})" for x, y in box) + "]"

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
        self._log_result_details(result)
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
            "text_detection_model_name": "PP-OCRv5_mobile_det",
            "text_recognition_model_name": "en_PP-OCRv5_mobile_rec",
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }
        if not use_gpu:
            kwargs["enable_mkldnn"] = False
            kwargs["cpu_threads"] = 8

        return PaddleOCR(**kwargs)

    def _normalize_result(self, raw_result: Any) -> OCRResult:
        lines: list[OCRLine] = []
        fallback_lines: list[OCRLine] = []

        for page_result in raw_result or []:
            page_json = page_result if isinstance(page_result, dict) else getattr(page_result, "json", None)
            if isinstance(page_json, dict):
                texts = page_json.get("rec_texts") or []
                scores = page_json.get("rec_scores") or []
                boxes = page_json.get("rec_boxes")
                if boxes is None:
                    boxes = []
                for index, (text, confidence) in enumerate(zip(texts, scores)):
                    box = boxes[index] if index < len(boxes) else None
                    self._collect_line(lines, fallback_lines, text, confidence, box=box)
                continue

            legacy_items = page_result or []
            if legacy_items and isinstance(legacy_items, list) and len(legacy_items[0]) >= 2:
                for item in legacy_items:
                    if not item or len(item) < 2:
                        continue

                    text, confidence = item[1]
                    box = item[0] if OCREngine._is_box_like(item[0]) else None
                    self._collect_line(lines, fallback_lines, text, confidence, box=box)
                continue

            for block in page_result or []:
                for item in block or []:
                    if not item or len(item) < 2:
                        continue

                    text, confidence = item[1]
                    box = item[0] if OCREngine._is_box_like(item[0]) else None
                    self._collect_line(lines, fallback_lines, text, confidence, box=box)

        if not lines and fallback_lines:
            best_line = max(fallback_lines, key=lambda line: line.confidence)
            lines = [best_line]

        if not lines:
            return OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")

        display_text = self._build_display_text(lines)
        average_confidence = sum(line.confidence for line in lines) / len(lines)
        return OCRResult(
            lines=lines,
            display_text=display_text,
            average_confidence=average_confidence,
            status="ok",
        )

    @staticmethod
    def _build_display_text(lines: list[OCRLine]) -> str:
        geometric_lines = [line for line in lines if line.center_x is not None and line.center_y is not None]
        if not geometric_lines:
            return "\n".join(line.text for line in lines)

        row_heights = [line.height for line in geometric_lines if line.height is not None and line.height > 0]
        row_threshold = max(8.0, median(row_heights) * 0.9) if row_heights else 14.0

        rows: list[list[OCRLine]] = []
        pending_unpositioned: list[OCRLine] = []
        for line in sorted(
            lines,
            key=lambda current: (
                float("inf") if current.center_y is None else current.center_y,
                float("inf") if current.center_x is None else current.center_x,
            ),
        ):
            if line.center_y is None or line.center_x is None:
                pending_unpositioned.append(line)
                continue

            if not rows or not OCREngine._should_merge_into_row(rows[-1], line, row_threshold):
                rows.append([line])
                continue

            rows[-1].append(line)

        rendered_rows = [
            " ".join(item.text for item in sorted(row, key=lambda current: current.center_x or 0.0))
            for row in rows
            if row
        ]
        rendered_rows.extend(line.text for line in pending_unpositioned)
        return "\n".join(rendered_rows)

    @staticmethod
    def _should_merge_into_row(row: list[OCRLine], line: OCRLine, row_threshold: float) -> bool:
        row_tops = [item.center_y - (item.height or 0.0) / 2 for item in row if item.center_y is not None]
        row_bottoms = [item.center_y + (item.height or 0.0) / 2 for item in row if item.center_y is not None]
        if not row_tops or not row_bottoms or line.center_y is None:
            return False

        line_height = line.height or 0.0
        line_top = line.center_y - line_height / 2
        line_bottom = line.center_y + line_height / 2
        row_top = min(row_tops)
        row_bottom = max(row_bottoms)
        overlap = min(row_bottom, line_bottom) - max(row_top, line_top)
        min_height = max(1.0, min(row_bottom - row_top, line_height))
        if overlap >= min_height * 0.2:
            return True

        row_center = (row_top + row_bottom) / 2
        return abs(line.center_y - row_center) <= row_threshold

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
    def _collect_line(
        lines: list[OCRLine],
        fallback_lines: list[OCRLine],
        text: Any,
        confidence: Any,
        box: Any = None,
    ) -> None:
        normalized_text = str(text).strip()
        normalized_confidence = float(confidence)
        if not normalized_text:
            return

        normalized_box = OCREngine._normalize_box(box)
        line = OCRLine(
            text=normalized_text,
            confidence=normalized_confidence,
            box=normalized_box,
            center_x=OCREngine._box_center_x(normalized_box),
            center_y=OCREngine._box_center_y(normalized_box),
            height=OCREngine._box_height(normalized_box),
        )
        if normalized_confidence >= OCR_CONFIDENCE_THRESHOLD:
            lines.append(line)
            return

        if normalized_confidence >= 0.5 and any(char.isalnum() for char in normalized_text) and len(normalized_text) >= 4:
            fallback_lines.append(line)

    @staticmethod
    def _normalize_box(box: Any) -> Box | None:
        if not OCREngine._is_box_like(box):
            return None

        points: list[Point] = []
        for point in box:
            if not OCREngine._is_box_like(point) or len(point) < 2:
                return None
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                return None

        return tuple(points)

    @staticmethod
    def _is_box_like(value: Any) -> bool:
        return hasattr(value, "__len__") and hasattr(value, "__getitem__") and len(value) > 0

    @staticmethod
    def _box_center_x(box: Box | None) -> float | None:
        if not box:
            return None
        return sum(point[0] for point in box) / len(box)

    @staticmethod
    def _box_center_y(box: Box | None) -> float | None:
        if not box:
            return None
        return sum(point[1] for point in box) / len(box)

    @staticmethod
    def _box_height(box: Box | None) -> float | None:
        if not box:
            return None
        ys = [point[1] for point in box]
        return max(ys) - min(ys)
        rendered_rows.extend(line.text for line in pending_unpositioned)
        return "\n".join(rendered_rows)

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
    def _collect_line(
        lines: list[OCRLine],
        fallback_lines: list[OCRLine],
        text: Any,
        confidence: Any,
        box: Any = None,
    ) -> None:
        normalized_text = str(text).strip()
        normalized_confidence = float(confidence)
        if not normalized_text:
            return

        normalized_box = OCREngine._normalize_box(box)
        line = OCRLine(
            text=normalized_text,
            confidence=normalized_confidence,
            box=normalized_box,
            center_x=OCREngine._box_center_x(normalized_box),
            center_y=OCREngine._box_center_y(normalized_box),
            height=OCREngine._box_height(normalized_box),
        )
        if normalized_confidence >= OCR_CONFIDENCE_THRESHOLD:
            lines.append(line)
            return

        if normalized_confidence >= 0.5 and any(char.isalnum() for char in normalized_text) and len(normalized_text) >= 4:
            fallback_lines.append(line)

    @staticmethod
    def _normalize_box(box: Any) -> Box | None:
        if not OCREngine._is_box_like(box):
            return None

        points: list[Point] = []
        for point in box:
            if not OCREngine._is_box_like(point) or len(point) < 2:
                return None
            try:
                points.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError):
                return None

        return tuple(points)

    @staticmethod
    def _is_box_like(value: Any) -> bool:
        return hasattr(value, "__len__") and hasattr(value, "__getitem__") and len(value) > 0

    @staticmethod
    def _box_center_x(box: Box | None) -> float | None:
        if not box:
            return None
        return sum(point[0] for point in box) / len(box)

    @staticmethod
    def _box_center_y(box: Box | None) -> float | None:
        if not box:
            return None
        return sum(point[1] for point in box) / len(box)

    @staticmethod
    def _box_height(box: Box | None) -> float | None:
        if not box:
            return None
        ys = [point[1] for point in box]
        return max(ys) - min(ys)
