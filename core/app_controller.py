from __future__ import annotations

import logging
from dataclasses import dataclass

from core.hotkey import HotkeyManager
from core.screenshot import MonitorCapture, ScreenshotService
from core.coordinate_mapper import CoordinateMapper
from core.preprocessor import ImagePreprocessor
from core.ocr_engine import OCREngine
from ui.selection_overlay import SelectionOverlay, SelectionResult
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
        self._active_capture: MonitorCapture | None = None

    def start(self) -> None:
        self._logger.info("Controller start")
        self._deps.hotkey.start()

    def stop(self) -> None:
        self._logger.info("Controller stop")
        self._deps.selection_overlay.hide_overlay()
        self._deps.hotkey.stop()
        self._active_capture = None
        self.transition_to(STATE_IDLE)

    def handle_hotkey(self) -> None:
        self._logger.info("Global hotkey pressed in state=%s", self.state)

        if self.state == STATE_SELECTING:
            self._logger.info("Restarting active selection")
            self._cancel_selection()
        elif self.state != STATE_IDLE:
            self._logger.info("Ignoring hotkey in state=%s", self.state)
            return

        try:
            capture = self._deps.screenshot.capture_cursor_monitor()
        except Exception:
            self._logger.exception("Screenshot capture failed")
            return

        self._deps.screenshot.log_capture_target(self._logger, capture.monitor)
        self._active_capture = capture
        self.transition_to(STATE_SELECTING)

        self._deps.selection_overlay.show_capture(
            capture=capture,
            on_confirm=self._confirm_selection,
            on_cancel=self._cancel_selection,
            on_focus_ready=self._handle_selection_focus_ready,
        )

    def _handle_selection_focus_ready(self, has_focus: bool) -> None:
        if self.state != STATE_SELECTING:
            return

        if has_focus:
            self._logger.info("Selection overlay shown")
            return

        self._logger.error("Selection overlay failed to acquire focus")
        self._cancel_selection()

    def _confirm_selection(self, result: SelectionResult) -> None:
        self._logger.info(
            "Selection confirmed x=%s y=%s w=%s h=%s",
            result.rect.x(),
            result.rect.y(),
            result.rect.width(),
            result.rect.height(),
        )

        if self._active_capture is None:
            self._logger.error("Selection confirmed without active capture")
            self._deps.selection_overlay.hide_overlay()
            self.transition_to(STATE_IDLE)
            return

        crop_rect = self._deps.coordinate_mapper.map_selection_rect(result.rect, self._active_capture)
        if crop_rect is None:
            self._logger.info("Selection invalid after coordinate mapping")
            self._deps.selection_overlay.hide_overlay()
            self._active_capture = None
            self.transition_to(STATE_IDLE)
            return

        self._logger.info(
            "Mapped crop left=%s top=%s right=%s bottom=%s width=%s height=%s",
            crop_rect.left,
            crop_rect.top,
            crop_rect.right,
            crop_rect.bottom,
            crop_rect.width,
            crop_rect.height,
        )
        self._deps.selection_overlay.hide_overlay()
        self._active_capture = None
        self.transition_to(STATE_IDLE)

    def _cancel_selection(self) -> None:
        self._logger.info("Selection cancelled")
        self._deps.selection_overlay.hide_overlay()
        self._active_capture = None
        self.transition_to(STATE_IDLE)

    def transition_to(self, new_state: str) -> None:
        if new_state not in _ALLOWED_STATES:
            raise ValueError(f"Invalid state: {new_state}")

        if self.state == new_state:
            return

        self._logger.debug("State transition: %s -> %s", self.state, new_state)
        self.state = new_state
