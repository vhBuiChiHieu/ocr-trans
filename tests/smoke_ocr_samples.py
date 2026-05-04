from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
import sys

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ocr_engine import OCREngine
from core.ocr_pipeline import OCRPipeline
from core.preprocessor import (
    PRESET_BASELINE,
    PRESET_OUTLINED_HIGH_CONTRAST,
    PRESET_SMALL_TEXT,
    ImagePreprocessor,
)

EVALUATION_RUNS = (
    (PRESET_BASELINE, "normal"),
    (PRESET_BASELINE, "auto"),
    (PRESET_SMALL_TEXT, "normal"),
    (PRESET_OUTLINED_HIGH_CONTRAST, "auto"),
)


@dataclass(frozen=True)
class SmokeRow:
    image: str
    preset: str
    mode: str
    text: str
    avg_confidence: float
    note: str


# Giữ full OCR text để dễ đối chiếu thủ công với từng ảnh input.


def format_text_block(text: str) -> str:
    return text if text else "<empty>"


def format_row(row: SmokeRow) -> str:
    return " | ".join(
        [
            row.image,
            row.preset,
            row.mode,
            f"{row.avg_confidence:.2f}",
            row.note,
        ]
    )


def evaluate_sample(sample_path: Path, pipeline: OCRPipeline) -> list[SmokeRow]:
    with Image.open(sample_path) as source_image:
        image = source_image.convert("RGB")
    rows: list[SmokeRow] = []

    for preset, mode in EVALUATION_RUNS:
        result = pipeline.run(image, preset=preset, mode=mode)
        rows.append(
            SmokeRow(
                image=sample_path.name,
                preset=preset,
                mode=mode,
                text=result.display_text,
                avg_confidence=result.average_confidence,
                note=result.status,
            )
        )

    return rows


def main() -> int:
    logger = logging.getLogger("ocr_smoke")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False

    pipeline = OCRPipeline(preprocessor=ImagePreprocessor(), ocr_engine=OCREngine(logger=logger))
    sample_dir = PROJECT_ROOT / "imgs/ocr_test_input"
    sample_paths = sorted(sample_dir.glob("*.png"))
    if not sample_paths:
        raise SystemExit("No OCR sample images found in imgs/ocr_test_input")

    print("image | preset | mode | avg confidence | note")
    print("--- | --- | --- | --- | ---")
    for sample_path in sample_paths:
        for row in evaluate_sample(sample_path, pipeline):
            print(format_row(row))
            print(format_text_block(row.text))
            print("---")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
