from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PyQt6.QtGui import QCursor, QGuiApplication


@dataclass(frozen=True)
class MonitorBounds:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True)
class MonitorCapture:
    image: Any
    monitor: MonitorBounds
    scale_x: float
    scale_y: float


class ScreenshotService:
    def __init__(self) -> None:
        self._mss_module = None

    def capture_cursor_monitor(self) -> MonitorCapture:
        monitor, device_pixel_ratio = self._resolve_cursor_monitor_bounds()

        with self._create_sct() as sct:
            image = sct.grab(
                {
                    "left": monitor.left,
                    "top": monitor.top,
                    "width": monitor.width,
                    "height": monitor.height,
                }
            )

        return MonitorCapture(
            image=image,
            monitor=monitor,
            scale_x=device_pixel_ratio,
            scale_y=device_pixel_ratio,
        )

    def _create_sct(self):
        mss_module = self._load_mss_module()
        return mss_module.mss()

    def _load_mss_module(self):
        if self._mss_module is not None:
            return self._mss_module

        try:
            import mss
        except ImportError as exc:
            raise RuntimeError("mss is required for screenshot capture") from exc

        self._mss_module = mss
        return mss

    # Comment quan trọng: monitor target phải lấy từ cursor trước, rồi overlay/crop dùng cùng context này.
    @staticmethod
    def point_in_monitor(x: int, y: int, monitor: MonitorBounds) -> bool:
        return monitor.left <= x < monitor.right and monitor.top <= y < monitor.bottom

    @staticmethod
    def from_mss_monitor(monitor: dict[str, int]) -> MonitorBounds:
        return MonitorBounds(
            left=monitor["left"],
            top=monitor["top"],
            width=monitor["width"],
            height=monitor["height"],
        )

    def get_cursor_monitor(self) -> MonitorBounds:
        monitor, _device_pixel_ratio = self._resolve_cursor_monitor_bounds()
        return monitor

    def _resolve_cursor_monitor_bounds(self) -> tuple[MonitorBounds, float]:
        cursor_pos = QCursor.pos()
        screen = QGuiApplication.screenAt(cursor_pos)
        if screen is None:
            raise RuntimeError("Could not resolve target monitor from cursor position")

        geometry = screen.geometry()
        device_pixel_ratio = screen.devicePixelRatio()
        monitor = MonitorBounds(
            left=round(geometry.left() * device_pixel_ratio),
            top=round(geometry.top() * device_pixel_ratio),
            width=round(geometry.width() * device_pixel_ratio),
            height=round(geometry.height() * device_pixel_ratio),
        )
        return monitor, device_pixel_ratio

    @staticmethod
    def describe_monitor(monitor: MonitorBounds) -> str:
        return (
            f"left={monitor.left}, top={monitor.top}, width={monitor.width}, height={monitor.height}"
        )

    def log_capture_target(self, logger, monitor: MonitorBounds) -> None:
        logger.info("Screenshot target monitor: %s", self.describe_monitor(monitor))

    def capture_region(self, *_args, **_kwargs):
        raise NotImplementedError("Use capture_cursor_monitor for Phase 1 monitor capture.")
