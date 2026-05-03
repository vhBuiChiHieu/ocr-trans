from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from core.preprocessor import (
    PRESET_BASELINE,
    PRESET_OUTLINED_HIGH_CONTRAST,
    PRESET_SMALL_TEXT,
    PREPROCESS_PRESETS,
    ImagePreprocessor,
)


class ImagePreprocessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preprocessor = ImagePreprocessor()

    def test_preprocess_converts_rgba_pil_image_to_contiguous_rgb_uint8_array(self) -> None:
        image = Image.new("RGBA", (2, 1), (10, 20, 30, 255))

        result = self.preprocessor.preprocess(image)

        self.assertEqual(result.shape, (1, 2, 3))
        self.assertEqual(result.dtype, np.uint8)
        self.assertTrue(result.flags.c_contiguous)
        self.assertEqual(result[0, 0].tolist(), [10, 20, 30])

    def test_preprocess_exposes_expected_presets(self) -> None:
        self.assertEqual(
            PREPROCESS_PRESETS,
            (PRESET_BASELINE, PRESET_SMALL_TEXT, PRESET_OUTLINED_HIGH_CONTRAST),
        )

    def test_small_text_preset_upscales_small_inputs(self) -> None:
        image = np.arange(4 * 4 * 3, dtype=np.uint8).reshape((4, 4, 3))

        result = self.preprocessor.preprocess(image, preset=PRESET_SMALL_TEXT)

        self.assertEqual(result.shape, (8, 8, 3))
        self.assertEqual(result.dtype, np.uint8)
        self.assertTrue(result.flags.c_contiguous)

    def test_outlined_high_contrast_preset_returns_rgb_binary_image(self) -> None:
        image = np.array(
            [
                [[20, 20, 20], [240, 240, 240]],
                [[120, 120, 120], [200, 180, 170]],
            ],
            dtype=np.uint8,
        )

        result = self.preprocessor.preprocess(image, preset=PRESET_OUTLINED_HIGH_CONTRAST)

        self.assertEqual(result.shape, image.shape)
        self.assertEqual(result.dtype, np.uint8)
        self.assertTrue(np.isin(result, [0, 255]).all())
        self.assertTrue(np.array_equal(result[:, :, 0], result[:, :, 1]))
        self.assertTrue(np.array_equal(result[:, :, 1], result[:, :, 2]))

    def test_preprocess_rejects_unknown_preset(self) -> None:
        with self.assertRaises(ValueError):
            self.preprocessor.preprocess(np.zeros((2, 2, 3), dtype=np.uint8), preset="weird")


if __name__ == "__main__":
    unittest.main()
