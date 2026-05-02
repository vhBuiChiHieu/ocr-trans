from __future__ import annotations

import unittest

import numpy as np
from PIL import Image

from core.preprocessor import ImagePreprocessor


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


if __name__ == "__main__":
    unittest.main()
