from __future__ import annotations

import numpy as np


class ImagePreprocessor:
    def preprocess(self, image) -> np.ndarray:
        if hasattr(image, "rgb") and hasattr(image, "width") and hasattr(image, "height"):
            rgb = np.frombuffer(image.rgb, dtype=np.uint8)
            return rgb.reshape((image.height, image.width, 3)).copy()

        if isinstance(image, np.ndarray):
            return self._normalize_array(image)

        if hasattr(image, "convert"):
            return self._normalize_array(np.array(image.convert("RGB"), dtype=np.uint8))

        return self._normalize_array(np.array(image, dtype=np.uint8))

    @staticmethod
    def _normalize_array(image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            image = np.stack([image] * 3, axis=-1)
        elif image.ndim == 3 and image.shape[2] == 4:
            image = image[:, :, :3]

        return np.ascontiguousarray(image, dtype=np.uint8)
