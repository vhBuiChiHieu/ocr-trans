from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from core.ocr_engine import OCRResult
from tests.smoke_ocr_samples import EVALUATION_RUNS, SmokeRow, evaluate_sample, format_row, summarize_text


class FakePipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def run(self, image, preset: str, mode: str) -> OCRResult:
        self.calls.append((preset, mode))
        return OCRResult(lines=[], display_text=f"{preset} {mode} text output", average_confidence=0.875, status="ok")


class SmokeHarnessTests(unittest.TestCase):
    def test_summarize_text_collapses_whitespace_and_truncates(self) -> None:
        self.assertEqual(summarize_text("hello\n world"), "hello world")
        self.assertEqual(summarize_text("x" * 70, max_len=10), "xxxxxxx...")

    def test_format_row_renders_stable_pipe_table_line(self) -> None:
        row = SmokeRow(
            image="sample.png",
            preset="baseline",
            mode="auto",
            text_summary="hello",
            avg_confidence=0.875,
            note="ok",
        )

        self.assertEqual(format_row(row), "sample.png | baseline | auto | hello | 0.88 | ok")

    def test_evaluate_sample_runs_all_configured_preset_mode_pairs(self) -> None:
        pipeline = FakePipeline()
        with tempfile.TemporaryDirectory() as tmp_dir:
            sample_path = Path(tmp_dir) / "sample.png"
            Image.new("RGB", (2, 2), (255, 255, 255)).save(sample_path)

            rows = evaluate_sample(sample_path, pipeline)

        self.assertEqual(len(rows), len(EVALUATION_RUNS))
        self.assertEqual(
            pipeline.calls,
            [
                ("baseline", "normal"),
                ("baseline", "auto"),
                ("small_text", "normal"),
                ("outlined_high_contrast", "auto"),
            ],
        )
        self.assertEqual(rows[0].image, "sample.png")
        self.assertEqual(rows[0].note, "ok")


if __name__ == "__main__":
    unittest.main()
