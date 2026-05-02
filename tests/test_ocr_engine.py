from __future__ import annotations

import logging
import unittest
from types import SimpleNamespace

from core.ocr_engine import OCREngine, OCRResult
from unittest.mock import patch


class FakeEngine:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.predict_calls: list[tuple[object, dict[str, object]]] = []

    def predict(self, image, **kwargs):
        self.predict_calls.append((image, kwargs))
        if self._error is not None:
            raise self._error
        return self._result

    def ocr(self, _image):
        raise AssertionError("recognize() should use predict()")


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

    def test_normalize_result_keeps_best_text_when_raw_text_exists_but_scores_are_low(self) -> None:
        raw_result = wrap_json_page(["Visible subtitle", "noise"], [0.55, 0.30])

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.display_text, "Visible subtitle")
        self.assertEqual(len(result.lines), 1)
        self.assertAlmostEqual(result.average_confidence, 0.55)

    def test_normalize_result_supports_legacy_shape(self) -> None:
        raw_result = [wrap_legacy_page(("Legacy", 0.88), ("noise", 0.15))]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.display_text, "Legacy")
        self.assertEqual(len(result.lines), 1)

    def test_normalize_result_supports_predict_dict_shape(self) -> None:
        raw_result = [{"rec_texts": ["Shorekeeper"], "rec_scores": [0.99]}]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.display_text, "Shorekeeper")
        self.assertEqual(len(result.lines), 1)
        self.assertAlmostEqual(result.average_confidence, 0.99)

    def test_normalize_result_joins_multiple_lines(self) -> None:
        raw_result = wrap_json_page(["Line 1", "Line 2"], [0.91, 0.92])

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "Line 1\nLine 2")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.lines), 2)

    def test_preload_initializes_cpu_runtime(self) -> None:
        created: list[bool] = []
        cpu_engine = FakeEngine(result=wrap_json_page(["Recovered"], [0.91]))

        def fake_create_engine(use_gpu: bool):
            created.append(use_gpu)
            return cpu_engine

        self.engine._create_engine = fake_create_engine  # type: ignore[method-assign]

        self.engine.preload()

        self.assertEqual(created, [False])
        self.assertEqual(self.engine.runtime, "cpu")

    def test_recognize_uses_cpu_runtime(self) -> None:
        fake_engine = FakeEngine(result=wrap_json_page(["Recovered"], [0.91]))
        self.engine._ocr = fake_engine
        self.engine._runtime = "cpu"

        result = self.engine.recognize(image=[[0]])

        self.assertEqual(result.display_text, "Recovered")
        self.assertEqual(result.status, "ok")
        self.assertEqual(self.engine.runtime, "cpu")

    def test_recognize_uses_predict_with_explicit_detection_params(self) -> None:
        fake_engine = FakeEngine(result=wrap_json_page(["Detected"], [0.91]))
        self.engine._ocr = fake_engine
        self.engine._runtime = "cpu"

        result = self.engine.recognize(image=[[0]])

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(fake_engine.predict_calls), 1)
        _image, kwargs = fake_engine.predict_calls[0]
        self.assertEqual(kwargs["text_det_limit_side_len"], 960)
        self.assertEqual(kwargs["text_det_limit_type"], "max")
        self.assertEqual(kwargs["text_det_thresh"], 0.3)
        self.assertEqual(kwargs["text_det_box_thresh"], 0.6)
        self.assertEqual(kwargs["text_det_unclip_ratio"], 2.0)
        self.assertEqual(kwargs["text_rec_score_thresh"], 0.0)

    def test_recognize_returns_error_when_cpu_prediction_fails(self) -> None:
        cpu_engine = FakeEngine(error=RuntimeError("cpu fail"))
        created: list[bool] = []

        def fake_create_engine(use_gpu: bool):
            created.append(use_gpu)
            return cpu_engine

        self.engine._create_engine = fake_create_engine  # type: ignore[method-assign]

        result = self.engine.recognize(image=[[0]])

        self.assertEqual(created, [False])
        self.assertEqual(result.status, "error")
        self.assertEqual(result.lines, [])

    def test_create_engine_disables_onednn_for_cpu_runtime(self) -> None:

        created_kwargs: dict[str, object] = {}

        def fake_paddle_ocr(**kwargs):
            created_kwargs.update(kwargs)
            return object()

        with patch("paddleocr.PaddleOCR", side_effect=fake_paddle_ocr):
            self.engine._create_engine(use_gpu=False)

        self.assertEqual(created_kwargs["device"], "cpu")
        self.assertFalse(created_kwargs["enable_mkldnn"])
        self.assertEqual(created_kwargs["cpu_threads"], 1)



if __name__ == "__main__":
    unittest.main()
