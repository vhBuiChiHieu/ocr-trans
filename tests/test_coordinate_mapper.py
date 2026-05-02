from __future__ import annotations

import unittest
from types import SimpleNamespace

from PyQt6.QtCore import QRect

from core.coordinate_mapper import CoordinateMapper
from core.screenshot import MonitorBounds, MonitorCapture


def make_capture(
    width: int,
    height: int,
    scale_x: float,
    scale_y: float,
    monitor_left: int = 0,
    monitor_top: int = 0,
) -> MonitorCapture:
    image = SimpleNamespace(width=width, height=height)
    return MonitorCapture(
        image=image,
        monitor=MonitorBounds(left=monitor_left, top=monitor_top, width=width, height=height),
        scale_x=scale_x,
        scale_y=scale_y,
    )


class CoordinateMapperTests(unittest.TestCase):
    def test_spec_example_scale_one(self) -> None:
        mapper = CoordinateMapper()
        capture = make_capture(width=240, height=120, scale_x=1.0, scale_y=1.0)

        pixel_rect = mapper.map_selection_rect(QRect(10, 20, 100, 40), capture)

        self.assertIsNotNone(pixel_rect)
        assert pixel_rect is not None
        self.assertEqual((pixel_rect.left, pixel_rect.top, pixel_rect.right, pixel_rect.bottom), (10, 20, 110, 60))
        self.assertEqual((pixel_rect.width, pixel_rect.height), (100, 40))

    def test_spec_example_scale_one_point_five(self) -> None:
        mapper = CoordinateMapper()
        capture = make_capture(width=240, height=120, scale_x=1.5, scale_y=1.5)

        pixel_rect = mapper.map_selection_rect(QRect(10, 20, 100, 40), capture)

        self.assertIsNotNone(pixel_rect)
        assert pixel_rect is not None
        self.assertEqual((pixel_rect.left, pixel_rect.top, pixel_rect.right, pixel_rect.bottom), (15, 30, 165, 90))
        self.assertEqual((pixel_rect.width, pixel_rect.height), (150, 60))

    def test_spec_example_reverse_drag_with_clamping(self) -> None:
        mapper = CoordinateMapper()
        capture = make_capture(width=240, height=120, scale_x=1.0, scale_y=1.0)

        pixel_rect = mapper.map_selection_rect(QRect(200, 100, -180, -70), capture)

        self.assertIsNotNone(pixel_rect)
        assert pixel_rect is not None
        self.assertEqual((pixel_rect.left, pixel_rect.top, pixel_rect.right, pixel_rect.bottom), (20, 30, 200, 100))
        self.assertEqual((pixel_rect.width, pixel_rect.height), (180, 70))

    def test_non_zero_monitor_origin_keeps_screenshot_local_output(self) -> None:
        mapper = CoordinateMapper()
        capture = make_capture(
            width=240,
            height=120,
            scale_x=1.0,
            scale_y=1.0,
            monitor_left=-1920,
            monitor_top=120,
        )

        pixel_rect = mapper.map_selection_rect(QRect(10, 20, 100, 40), capture)

        self.assertIsNotNone(pixel_rect)
        assert pixel_rect is not None
        self.assertEqual((pixel_rect.left, pixel_rect.top, pixel_rect.right, pixel_rect.bottom), (10, 20, 110, 60))

    def test_map_selection_rect_rejects_too_small_crop(self) -> None:
        mapper = CoordinateMapper()
        capture = make_capture(width=240, height=120, scale_x=1.0, scale_y=1.0)

        pixel_rect = mapper.map_selection_rect(QRect(10, 20, 3, 3), capture)

        self.assertIsNone(pixel_rect)

    def test_map_selection_rect_clamps_to_capture_bounds(self) -> None:
        mapper = CoordinateMapper()
        capture = make_capture(width=240, height=120, scale_x=1.0, scale_y=1.0)

        pixel_rect = mapper.map_selection_rect(QRect(220, 90, 50, 50), capture)

        self.assertIsNotNone(pixel_rect)
        assert pixel_rect is not None
        self.assertEqual((pixel_rect.left, pixel_rect.top, pixel_rect.right, pixel_rect.bottom), (220, 90, 240, 120))
        self.assertEqual((pixel_rect.width, pixel_rect.height), (20, 30))


if __name__ == "__main__":
    unittest.main()
