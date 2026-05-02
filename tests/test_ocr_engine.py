from __future__ import annotations

import logging
import unittest
from types import SimpleNamespace

from core.ocr_engine import OCREngine, OCRResult


class FakeEngine:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    def ocr(self, _image):
        if self._error is not None:
            raise self._error
        return self._result


def make_page_result(texts, scores):
    return SimpleNamespace(json={"rec_texts": texts, "rec_scores": scores})


def wrap_json_page(texts, scores):
    return [make_page_result(texts, scores)]


def wrap_legacy_page(*items):
    return [[[[0, 0], [1, 0], [1, 1], [0, 1]], item] for item in items]


class OCREngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("test_ocr_engine")
        self.engine = OCREngine(logger=self.logger)

    def test_normalize_result_filters_low_confidence(self) -> None:
        raw_result = wrap_json_page(["Hello", "noise"], [0.95, 0.25])

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.display_text, "Hello")
        self.assertEqual(len(result.lines), 1)
        self.assertAlmostEqual(result.average_confidence, 0.95)

    def test_normalize_result_returns_no_text_when_all_filtered(self) -> None:
        raw_result = wrap_json_page(["", "noise"], [0.95, 0.30])

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result, OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text"))

    def test_normalize_result_supports_legacy_shape(self) -> None:
        raw_result = [wrap_legacy_page(("Legacy", 0.88), ("noise", 0.15))]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.display_text, "Legacy")
        self.assertEqual(len(result.lines), 1)

    def test_normalize_result_joins_multiple_lines(self) -> None:
        raw_result = wrap_json_page(["Line 1", "Line 2"], [0.91, 0.92])

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "Line 1\nLine 2")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.lines), 2)

    def test_recognize_falls_back_from_gpu_to_cpu(self) -> None:
        gpu_engine = FakeEngine(error=RuntimeError("gpu fail"))
        cpu_engine = FakeEngine(result=wrap_json_page(["Recovered"], [0.91]))
        created: list[bool] = []

        def fake_create_engine(use_gpu: bool):
            created.append(use_gpu)
            return gpu_engine if use_gpu else cpu_engine

        self.engine._create_engine = fake_create_engine  # type: ignore[method-assign]

        result = self.engine.recognize(image=[[0]])

        self.assertEqual(created, [True, False])
        self.assertEqual(self.engine.runtime, "cpu")
        self.assertEqual(result.display_text, "Recovered")
        self.assertEqual(result.status, "ok")

    def test_recognize_returns_error_when_cpu_fallback_fails(self) -> None:
        gpu_engine = FakeEngine(error=RuntimeError("gpu fail"))
        cpu_engine = FakeEngine(error=RuntimeError("cpu fail"))
        created: list[bool] = []

        def fake_create_engine(use_gpu: bool):
            created.append(use_gpu)
            return gpu_engine if use_gpu else cpu_engine

        self.engine._create_engine = fake_create_engine  # type: ignore[method-assign]

        result = self.engine.recognize(image=[[0]])

        self.assertEqual(created, [True, False])
        self.assertEqual(result.status, "error")
        self.assertEqual(result.lines, [])


if __name__ == "__main__":
    unittest.main()
