from __future__ import annotations

import numpy as np


class ImagePreprocessor:
    def preprocess(self, image) -> np.ndarray:
        if hasattr(image, "rgb") and hasattr(image, "width") and hasattr(image, "height"):
            rgb = np.frombuffer(image.rgb, dtype=np.uint8)
            return rgb.reshape((image.height, image.width, 3)).copy()

        if isinstance(image, np.ndarray):
            return image.copy()

        return np.array(image)
