from __future__ import annotations

import unittest

import numpy as np

from core.ocr_engine import OCRResult
from core.ocr_pipeline import OCRPipeline, OCRPipelineConfig
from core.preprocessor import PRESET_OUTLINED_HIGH_CONTRAST


class FakePreprocessor:
    def __init__(self, output: np.ndarray) -> None:
        self.output = output
        self.calls: list[tuple[object, str]] = []

    def preprocess(self, image, preset: str):
        self.calls.append((image, preset))
        return self.output.copy()


class FakeOCREngine:
    def __init__(self, result: OCRResult) -> None:
        self.result = result
        self.calls: list[tuple[np.ndarray, str]] = []

    def recognize(self, image, mode: str):
        self.calls.append((image.copy(), mode))
        return self.result


class OCRPipelineTests(unittest.TestCase):
    def test_run_applies_configured_preset_and_mode(self) -> None:
        prepared = np.ones((2, 2, 3), dtype=np.uint8)
        result = OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")
        preprocessor = FakePreprocessor(output=prepared)
        engine = FakeOCREngine(result=result)
        pipeline = OCRPipeline(
            preprocessor=preprocessor,
            ocr_engine=engine,
            config=OCRPipelineConfig(preset=PRESET_OUTLINED_HIGH_CONTRAST, mode="auto"),
        )
        source = np.zeros((2, 2, 3), dtype=np.uint8)

        actual = pipeline.run(source)

        self.assertIs(actual, result)
        self.assertEqual(preprocessor.calls, [(source, PRESET_OUTLINED_HIGH_CONTRAST)])
        self.assertEqual(len(engine.calls), 1)
        prepared_image, mode = engine.calls[0]
        self.assertEqual(mode, "auto")
        self.assertTrue(np.array_equal(prepared_image, prepared))

    def test_run_allows_overriding_preset_and_mode(self) -> None:
        prepared = np.full((2, 2, 3), 7, dtype=np.uint8)
        result = OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")
        preprocessor = FakePreprocessor(output=prepared)
        engine = FakeOCREngine(result=result)
        pipeline = OCRPipeline(preprocessor=preprocessor, ocr_engine=engine)
        source = np.zeros((2, 2, 3), dtype=np.uint8)

        pipeline.run(source, preset="small_text", mode="inverted")

        self.assertEqual(preprocessor.calls, [(source, "small_text")])
        _prepared_image, mode = engine.calls[0]
        self.assertEqual(mode, "inverted")


if __name__ == "__main__":
    unittest.main()
