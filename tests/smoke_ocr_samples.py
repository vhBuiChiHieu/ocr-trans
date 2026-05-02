from __future__ import annotations

import logging
from pathlib import Path
import sys

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ocr_engine import OCREngine
from core.preprocessor import ImagePreprocessor

def main() -> int:
    logger = logging.getLogger("ocr_smoke")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False

    preprocessor = ImagePreprocessor()
    engine = OCREngine(logger=logger)
    sample_dir = Path("imgs/ocr_test_input")
    sample_paths = sorted(sample_dir.glob("*.png"))
    if not sample_paths:
        raise SystemExit("No OCR sample images found in imgs/ocr_test_input")

    for sample_path in sample_paths:
        image = Image.open(sample_path).convert("RGB")
        prepared = preprocessor.preprocess(image)
        result = engine.recognize(prepared)
        print(f"{sample_path.name}: status={result.status} runtime={engine.runtime} lines={len(result.lines)}")
        if result.display_text:
            print(result.display_text)
            print("---")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
