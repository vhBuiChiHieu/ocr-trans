from __future__ import annotations

import logging
import unittest
from types import SimpleNamespace

import numpy as np
from core.ocr_engine import (
    OCR_MODE_AUTO,
    OCR_MODE_INVERTED,
    OCR_MODE_NORMAL,
    OCR_MODES,
    OCRCandidate,
    OCREngine,
    OCRLine,
    OCRResult,
)
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


def make_legacy_item(text: str, confidence: float, box):
    return [box, (text, confidence)]


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

    def test_normalize_result_joins_multiple_lines_until_sentence_end(self) -> None:
        raw_result = wrap_json_page(["Line 1", "Line 2."], [0.91, 0.92])

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "Line 1\nLine 2.")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.lines), 2)

    def test_normalize_result_keeps_line_break_after_sentence_end(self) -> None:
        raw_result = wrap_json_page(["Exclusive Interview with the", "Voidworm Rider.", "Really?", "You want me to decide?"], [0.99, 0.99, 0.99, 0.99])

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "Exclusive Interview with the\nVoidworm Rider.\nReally?\nYou want me to decide?")
        self.assertEqual(result.status, "ok")

    def test_normalize_result_keeps_line_break_after_sentence_end_with_closing_quote(self) -> None:
        raw_result = wrap_json_page(["He asked,", '"Really?"', "Then left."], [0.99, 0.99, 0.99])

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, 'He asked,\n"Really?"\nThen left.')

    def test_normalize_result_groups_same_row_left_to_right(self) -> None:
        raw_result = [[
            make_legacy_item("world", 0.92, [[60, 10], [100, 10], [100, 28], [60, 28]]),
            make_legacy_item("Hello", 0.94, [[10, 12], [50, 12], [50, 30], [10, 30]]),
            make_legacy_item("again", 0.91, [[12, 48], [58, 48], [58, 66], [12, 66]]),
        ]]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "world\nHello\nagain")
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.lines), 3)

    def test_normalize_result_splits_rows_when_vertical_gap_is_large(self) -> None:
        raw_result = [[
            make_legacy_item("Line", 0.95, [[10, 10], [40, 10], [40, 30], [10, 30]]),
            make_legacy_item("One", 0.95, [[50, 12], [88, 12], [88, 32], [50, 32]]),
            make_legacy_item("Line", 0.95, [[12, 70], [42, 70], [42, 90], [12, 90]]),
            make_legacy_item("Two", 0.95, [[52, 70], [86, 70], [86, 90], [52, 90]]),
        ]]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "Line\nOne\nLine\nTwo")

    def test_join_segments_breaks_on_trailing_linebreak_then_uppercase(self) -> None:
        text = self.engine._join_segments_into_sentences(["alpha\n", "Bravo", "tail"])

        self.assertEqual(text, "alpha\nBravo tail")

    def test_join_segments_keeps_join_when_trailing_linebreak_before_comma_then_uppercase(self) -> None:
        text = self.engine._join_segments_into_sentences(["alpha,\n", "Bravo", "tail"])

        self.assertEqual(text, "alpha, Bravo tail")

    def test_normalize_result_keeps_join_when_next_row_starts_lowercase(self) -> None:
        raw_result = [[
            make_legacy_item("line", 0.95, [[10, 10], [40, 10], [40, 30], [10, 30]]),
            make_legacy_item("one", 0.95, [[50, 12], [88, 12], [88, 32], [50, 32]]),
            make_legacy_item("line", 0.95, [[12, 70], [42, 70], [42, 90], [12, 90]]),
            make_legacy_item("two", 0.95, [[52, 70], [86, 70], [86, 90], [52, 90]]),
        ]]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "line\none\nline\ntwo")

    def test_normalize_result_merges_boxes_with_vertical_overlap(self) -> None:
        raw_result = [[
            make_legacy_item("After", 0.95, [[10, 10], [50, 10], [50, 32], [10, 32]]),
            make_legacy_item("the", 0.95, [[58, 18], [84, 18], [84, 40], [58, 40]]),
            make_legacy_item("wielder", 0.95, [[92, 14], [156, 14], [156, 36], [92, 36]]),
            make_legacy_item("Glacio", 0.95, [[12, 60], [72, 60], [72, 82], [12, 82]]),
        ]]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "After\nthe\nwielder\nGlacio")

    def test_normalize_result_ignores_malformed_box_and_keeps_text(self) -> None:
        raw_result = [[
            make_legacy_item("Visible subtitle", 0.91, ["bad-box"]),
        ]]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "Visible subtitle")
        self.assertEqual(result.status, "ok")
        self.assertIsNone(result.lines[0].box)

    def test_normalize_result_prefers_box_order_when_available(self) -> None:
        raw_result = [{
            "rec_texts": ["world", "Hello", "again"],
            "rec_scores": [0.92, 0.94, 0.91],
            "rec_boxes": [
                [[60, 10], [100, 10], [100, 28], [60, 28]],
                [[10, 12], [50, 12], [50, 30], [10, 30]],
                [[12, 48], [58, 48], [58, 66], [12, 66]],
            ],
        }]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "world\nHello\nagain")

    def test_normalize_result_supports_numpy_rec_boxes(self) -> None:
        raw_result = [{
            "rec_texts": ["world", "Hello"],
            "rec_scores": [0.92, 0.94],
            "rec_boxes": np.array(
                [
                    [[60, 10], [100, 10], [100, 28], [60, 28]],
                    [[10, 12], [50, 12], [50, 30], [10, 30]],
                ]
            ),
        }]

        result = self.engine._normalize_result(raw_result)

        self.assertEqual(result.display_text, "world\nHello")

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

    def test_recognize_exposes_expected_modes(self) -> None:
        self.assertEqual(OCR_MODES, (OCR_MODE_NORMAL, OCR_MODE_INVERTED, OCR_MODE_AUTO))

    def test_recognize_inverted_mode_uses_inverted_image(self) -> None:
        fake_engine = FakeEngine(result=wrap_json_page(["Detected"], [0.91]))
        self.engine._ocr = fake_engine
        self.engine._runtime = "cpu"
        image = np.array([[[10, 20, 30]]], dtype=np.uint8)

        result = self.engine.recognize(image=image, mode=OCR_MODE_INVERTED)

        self.assertEqual(result.status, "ok")
        inverted_image, _kwargs = fake_engine.predict_calls[0]
        self.assertTrue(np.array_equal(inverted_image, np.array([[[245, 235, 225]]], dtype=np.uint8)))

    def test_select_best_candidate_prefers_more_lines(self) -> None:
        best = self.engine._select_best_candidate(
            [
                OCRCandidate(
                    mode=OCR_MODE_NORMAL,
                    result=OCRResult(
                        lines=[OCRLine(text="one", confidence=0.80)],
                        display_text="one",
                        average_confidence=0.80,
                        status="ok",
                    ),
                ),
                OCRCandidate(
                    mode=OCR_MODE_INVERTED,
                    result=OCRResult(
                        lines=[OCRLine(text="one", confidence=0.71), OCRLine(text="two", confidence=0.72)],
                        display_text="one\ntwo",
                        average_confidence=0.715,
                        status="ok",
                    ),
                ),
            ]
        )

        self.assertEqual(best.mode, OCR_MODE_INVERTED)

    def test_select_best_candidate_uses_average_confidence_as_tiebreak(self) -> None:
        best = self.engine._select_best_candidate(
            [
                OCRCandidate(
                    mode=OCR_MODE_NORMAL,
                    result=OCRResult(
                        lines=[OCRLine(text="one", confidence=0.80)],
                        display_text="one",
                        average_confidence=0.80,
                        status="ok",
                    ),
                ),
                OCRCandidate(
                    mode=OCR_MODE_INVERTED,
                    result=OCRResult(
                        lines=[OCRLine(text="one", confidence=0.90)],
                        display_text="one",
                        average_confidence=0.90,
                        status="ok",
                    ),
                ),
            ]
        )

        self.assertEqual(best.mode, OCR_MODE_INVERTED)

    def test_select_best_candidate_prefers_normal_on_full_tie(self) -> None:
        best = self.engine._select_best_candidate(
            [
                OCRCandidate(
                    mode=OCR_MODE_INVERTED,
                    result=OCRResult(
                        lines=[OCRLine(text="one", confidence=0.80)],
                        display_text="one",
                        average_confidence=0.80,
                        status="ok",
                    ),
                ),
                OCRCandidate(
                    mode=OCR_MODE_NORMAL,
                    result=OCRResult(
                        lines=[OCRLine(text="one", confidence=0.80)],
                        display_text="one",
                        average_confidence=0.80,
                        status="ok",
                    ),
                ),
            ]
        )

        self.assertEqual(best.mode, OCR_MODE_NORMAL)

    def test_recognize_auto_returns_non_error_branch_when_other_branch_fails(self) -> None:
        calls: list[np.ndarray] = []
        expected_inverted = np.array([[[245, 235, 225]]], dtype=np.uint8)

        def fake_predict(image):
            calls.append(np.array(image, copy=True))
            if np.array_equal(image, expected_inverted):
                return wrap_json_page(["Recovered"], [0.91])
            raise RuntimeError("normal fail")

        self.engine._ocr = SimpleNamespace(predict=lambda image, **kwargs: fake_predict(image))
        self.engine._runtime = "cpu"
        image = np.array([[[10, 20, 30]]], dtype=np.uint8)

        result = self.engine.recognize(image=image, mode=OCR_MODE_AUTO)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.display_text, "Recovered")
        self.assertEqual(len(calls), 2)

    def test_recognize_rejects_unknown_mode(self) -> None:
        self.engine._ocr = FakeEngine(result=wrap_json_page(["Detected"], [0.91]))
        self.engine._runtime = "cpu"

        with self.assertRaises(ValueError):
            self.engine.recognize(image=[[0]], mode="weird")

    def test_create_engine_disables_onednn_for_cpu_runtime(self) -> None:

        created_kwargs: dict[str, object] = {}

        def fake_paddle_ocr(**kwargs):
            created_kwargs.update(kwargs)
            return object()

        with patch("paddleocr.PaddleOCR", side_effect=fake_paddle_ocr):
            self.engine._create_engine(use_gpu=False)

        self.assertEqual(created_kwargs["device"], "cpu")
        self.assertEqual(created_kwargs["text_detection_model_name"], "PP-OCRv5_mobile_det")
        self.assertEqual(created_kwargs["text_recognition_model_name"], "en_PP-OCRv5_mobile_rec")
        self.assertFalse(created_kwargs["enable_mkldnn"])
        self.assertEqual(created_kwargs["cpu_threads"], 8)



if __name__ == "__main__":
    unittest.main()
