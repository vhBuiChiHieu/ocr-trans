from __future__ import annotations

import math
from dataclasses import dataclass

from PyQt6.QtCore import QRect

from core.screenshot import MonitorCapture

MIN_CROP_SIZE = 4


@dataclass(frozen=True)
class PixelRect:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class CoordinateMapper:
    # Comment quan trọng: input QRect phải là rect local của overlay tạo từ drag endpoints Qt, nên right/bottom là inclusive và cần đổi sang exclusive trước khi scale.
    def map_selection_rect(self, selection_rect: QRect, capture: MonitorCapture) -> PixelRect | None:
        normalized = QRect(selection_rect).normalized()
        logical_left = normalized.left()
        logical_top = normalized.top()
        logical_right = normalized.right() + 1
        logical_bottom = normalized.bottom() + 1

        pixel_left = math.floor(logical_left * capture.scale_x)
        pixel_top = math.floor(logical_top * capture.scale_y)
        pixel_right = math.ceil(logical_right * capture.scale_x)
        pixel_bottom = math.ceil(logical_bottom * capture.scale_y)

        clamped_left = max(0, min(pixel_left, capture.image.width))
        clamped_top = max(0, min(pixel_top, capture.image.height))
        clamped_right = max(0, min(pixel_right, capture.image.width))
        clamped_bottom = max(0, min(pixel_bottom, capture.image.height))

        crop_rect = PixelRect(
            left=clamped_left,
            top=clamped_top,
            right=clamped_right,
            bottom=clamped_bottom,
        )
        if crop_rect.width < MIN_CROP_SIZE or crop_rect.height < MIN_CROP_SIZE:
            return None

        return crop_rect

    # Comment quan trọng: overlay cho toạ độ local logical, còn crop phải luôn bám ảnh screenshot-local physical pixels.
    @staticmethod
    def crop_bounds(crop_rect: PixelRect) -> tuple[int, int, int, int]:
        return crop_rect.left, crop_rect.top, crop_rect.right, crop_rect.bottom

    @staticmethod
    def is_valid_crop(crop_rect: PixelRect | None) -> bool:
        return crop_rect is not None

    def map_to_screen(self, *_args, **_kwargs):
        raise NotImplementedError("Use map_selection_rect for Phase 1 coordinate mapping.")
