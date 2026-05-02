from __future__ import annotations

import logging
from dataclasses import dataclass

from core.hotkey import HotkeyManager
from core.screenshot import ScreenshotService
from core.coordinate_mapper import CoordinateMapper
from core.preprocessor import ImagePreprocessor
from core.ocr_engine import OCREngine
from ui.selection_overlay import SelectionOverlay
from ui.result_overlay import ResultOverlay


STATE_IDLE = "idle"
STATE_SELECTING = "selecting"
STATE_PROCESSING = "processing"
STATE_SHOWING_RESULT = "showing_result"
_ALLOWED_STATES = {
    STATE_IDLE,
    STATE_SELECTING,
    STATE_PROCESSING,
    STATE_SHOWING_RESULT,
}


@dataclass
class AppControllerDependencies:
    hotkey: HotkeyManager
    screenshot: ScreenshotService
    coordinate_mapper: CoordinateMapper
    preprocessor: ImagePreprocessor
    ocr_engine: OCREngine
    selection_overlay: SelectionOverlay
    result_overlay: ResultOverlay


class AppController:
    def __init__(self, logger: logging.Logger, deps: AppControllerDependencies | None = None) -> None:
        self._logger = logger
        self._deps = deps or AppControllerDependencies(
            hotkey=HotkeyManager(logger=logger, on_hotkey=self.handle_hotkey),
            screenshot=ScreenshotService(),
            coordinate_mapper=CoordinateMapper(),
            preprocessor=ImagePreprocessor(),
            ocr_engine=OCREngine(),
            selection_overlay=SelectionOverlay(),
            result_overlay=ResultOverlay(),
        )
        self.state = STATE_IDLE

    def start(self) -> None:
        self._logger.info("Controller start")
        self._deps.hotkey.start()

    def stop(self) -> None:
        self._logger.info("Controller stop")
        self._deps.hotkey.stop()

    def handle_hotkey(self) -> None:
        self._logger.info("Global hotkey pressed in state=%s", self.state)

        try:
            capture = self._deps.screenshot.capture_cursor_monitor()
        except Exception:
            self._logger.exception("Screenshot capture failed")
            return

        self._deps.screenshot.log_capture_target(self._logger, capture.monitor)

    def transition_to(self, new_state: str) -> None:
        if new_state not in _ALLOWED_STATES:
            raise ValueError(f"Invalid state: {new_state}")

        if self.state == new_state:
            return

        self._logger.debug("State transition: %s -> %s", self.state, new_state)
        self.state = new_state
