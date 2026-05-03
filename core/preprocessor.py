from __future__ import annotations

import numpy as np

PRESET_BASELINE = "baseline"
PRESET_SMALL_TEXT = "small_text"
PRESET_OUTLINED_HIGH_CONTRAST = "outlined_high_contrast"
PREPROCESS_PRESETS = (
    PRESET_BASELINE,
    PRESET_SMALL_TEXT,
    PRESET_OUTLINED_HIGH_CONTRAST,
)


class ImagePreprocessor:
    def preprocess(self, image, preset: str = PRESET_BASELINE) -> np.ndarray:
        normalized = self._to_rgb_array(image)

        if preset == PRESET_BASELINE:
            return normalized
        if preset == PRESET_SMALL_TEXT:
            return self._upscale_small_text(normalized)
        if preset == PRESET_OUTLINED_HIGH_CONTRAST:
            return self._outlined_high_contrast(normalized)

        raise ValueError(f"Unsupported preprocess preset: {preset}")

    def _to_rgb_array(self, image) -> np.ndarray:
        if hasattr(image, "rgb") and hasattr(image, "width") and hasattr(image, "height"):
            rgb = np.frombuffer(image.rgb, dtype=np.uint8)
            return rgb.reshape((image.height, image.width, 3)).copy()

        if isinstance(image, np.ndarray):
            return self._normalize_array(image)

        if hasattr(image, "convert"):
            return self._normalize_array(np.array(image.convert("RGB"), dtype=np.uint8))

        return self._normalize_array(np.array(image, dtype=np.uint8))

    def _upscale_small_text(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        scale = 2 if min(height, width) < 64 else 1
        if scale == 1:
            return image.copy()

        upscaled = np.repeat(np.repeat(image, scale, axis=0), scale, axis=1)
        return np.ascontiguousarray(upscaled, dtype=np.uint8)

    def _outlined_high_contrast(self, image: np.ndarray) -> np.ndarray:
        gray = image.mean(axis=2, dtype=np.float32)
        gray = np.clip((gray - 128.0) * 1.35 + 128.0, 0.0, 255.0)
        threshold = np.where(gray >= 160.0, 255, 0).astype(np.uint8)
        return np.repeat(threshold[:, :, None], 3, axis=2)

    @staticmethod
    def _normalize_array(image: np.ndarray) -> np.ndarray:
        if image.ndim == 2:
            image = np.stack([image] * 3, axis=-1)
        elif image.ndim == 3 and image.shape[2] == 4:
            image = image[:, :, :3]

        return np.ascontiguousarray(image, dtype=np.uint8)
