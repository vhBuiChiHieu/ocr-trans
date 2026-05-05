from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import QObject, QRect, pyqtSignal

from core.hotkey import HotkeyManager
from core.screenshot import MonitorCapture, ScreenshotService
from core.coordinate_mapper import CoordinateMapper
from core.preprocessor import ImagePreprocessor, PRESET_BASELINE
from core.ocr_engine import OCR_MODE_NORMAL, OCREngine, OCRResult
from core.ocr_history import OCRHistoryEntry, OCRHistoryStore
from core.ocr_pipeline import OCRPipeline, OCRPipelineConfig
from ui.selection_overlay import SelectionOverlay, SelectionResult
from ui.result_overlay import ResultOverlay


STATE_IDLE = "idle"
STATE_SELECTING = "selecting"
STATE_PROCESSING = "processing"
STATE_SHOWING_RESULT = "showing_result"
OUTPUT_MODE_OCR_ONLY = "ocr_only"
OUTPUT_MODE_TRANSLATE = "translate"
OUTPUT_MODE_BOTH = "both"
_OUTPUT_MODES = {
    OUTPUT_MODE_OCR_ONLY,
    OUTPUT_MODE_TRANSLATE,
    OUTPUT_MODE_BOTH,
}


def _resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base_path / relative_path


_TRANSLATE_SCRIPT_PATH = _resource_path("scripts/google_translate.py")
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
    ocr_pipeline: OCRPipeline
    selection_overlay: SelectionOverlay
    result_overlay: ResultOverlay
    ocr_history: OCRHistoryStore


class _ControllerBridge(QObject):
    ocr_finished = pyqtSignal(object, object, object)


class TranslationError(RuntimeError):
    pass


class ScriptTranslator:
    def __init__(self, script_path: Path = _TRANSLATE_SCRIPT_PATH) -> None:
        self._script_path = script_path

    def translate(self, text: str, sl: str = "en", tl: str = "vi") -> str:
        escaped_text = text.replace("\n", "\\n")
        command = [
            sys.executable,
            str(self._script_path),
            escaped_text,
            "--sl",
            sl,
            "--tl",
            tl,
        ]
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
        except FileNotFoundError as exc:
            raise TranslationError("translator runtime not found") from exc
        except subprocess.CalledProcessError as exc:
            raise TranslationError(exc.stderr.strip() or exc.stdout.strip() or "translator failed") from exc

        return completed.stdout.strip()


class AppController:
    def __init__(self, logger: logging.Logger, deps: AppControllerDependencies | None = None) -> None:
        self._logger = logger
        if deps is None:
            preprocessor = ImagePreprocessor()
            ocr_engine = OCREngine(logger=logger)
            deps = AppControllerDependencies(
                hotkey=HotkeyManager(logger=logger, on_hotkey=self.handle_hotkey),
                screenshot=ScreenshotService(),
                coordinate_mapper=CoordinateMapper(),
                preprocessor=preprocessor,
                ocr_engine=ocr_engine,
                ocr_pipeline=OCRPipeline(
                    preprocessor=preprocessor,
                    ocr_engine=ocr_engine,
                    config=OCRPipelineConfig(
                        preset=PRESET_BASELINE,
                        mode=OCR_MODE_NORMAL,
                    ),
                ),
                selection_overlay=SelectionOverlay(),
                result_overlay=ResultOverlay(),
                ocr_history=OCRHistoryStore(),
            )
        self._deps = deps
        self._translator = ScriptTranslator()
        self.state = STATE_IDLE
        self._output_mode = OUTPUT_MODE_TRANSLATE
        self._active_capture: MonitorCapture | None = None
        self._active_selection_rect = QRect()
        self._bridge = _ControllerBridge()
        self._bridge.ocr_finished.connect(self._handle_ocr_finished)

    def start(self) -> None:
        self._logger.info("Controller start")
        self._deps.hotkey.start()

        threading.Thread(target=self._preload_ocr, name="ocr-preload", daemon=True).start()

    def stop(self) -> None:
        self._logger.info("Controller stop")
        self._deps.selection_overlay.hide_overlay()
        self._deps.result_overlay.hide_result()
        self._deps.hotkey.stop()
        self._active_capture = None
        self._active_selection_rect = QRect()
        self.transition_to(STATE_IDLE)

    def set_result_font_size(self, font_size: int) -> None:
        self._logger.info("Setting result overlay font size to %s", font_size)
        self._deps.result_overlay.set_font_size(font_size)

    def set_result_font_family(self, font_family: str) -> None:
        self._logger.info("Setting result overlay font family to %s", font_family)
        self._deps.result_overlay.set_font_family(font_family)

    def set_output_mode(self, mode: str) -> None:
        if mode not in _OUTPUT_MODES:
            raise ValueError(f"Invalid output mode: {mode}")

        self._logger.info("Setting output mode to %s", mode)
        self._output_mode = mode

    def _preload_ocr(self) -> None:
        try:
            self._deps.ocr_engine.preload()
        except Exception:
            self._logger.exception("OCR preload failed")

    def handle_hotkey(self) -> None:
        self._logger.info("Global hotkey pressed in state=%s", self.state)

        if self.state == STATE_PROCESSING:
            self._logger.info("Ignoring hotkey in state=%s", self.state)
            return

        if self.state == STATE_SELECTING:
            self._logger.info("Restarting active selection")
            self._cancel_selection()
        elif self.state == STATE_SHOWING_RESULT:
            self._logger.info("Replacing visible result overlay")
            self._deps.result_overlay.hide_result()
            self.transition_to(STATE_IDLE)

        if self.state != STATE_IDLE:
            self._logger.info("Ignoring hotkey in state=%s", self.state)
            return

        self._start_capture_flow()

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
            self._active_selection_rect = QRect()
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

        full_image = self._deps.preprocessor.preprocess(self._active_capture.image)
        left, top, right, bottom = self._deps.coordinate_mapper.crop_bounds(crop_rect)
        cropped_image = full_image[top:bottom, left:right]

        self._active_selection_rect = QRect(result.rect.normalized())
        active_capture = self._active_capture
        self._deps.selection_overlay.hide_overlay()
        self.transition_to(STATE_PROCESSING)
        self._start_ocr(active_capture, cropped_image, self._active_selection_rect)

    def _cancel_selection(self) -> None:
        self._logger.info("Selection cancelled")
        self._deps.selection_overlay.hide_overlay()
        self._active_capture = None
        self._active_selection_rect = QRect()
        self.transition_to(STATE_IDLE)

    def _start_capture_flow(self) -> None:
        try:
            capture = self._deps.screenshot.capture_cursor_monitor()
        except Exception:
            self._logger.exception("Screenshot capture failed")
            return

        self._deps.screenshot.log_capture_target(self._logger, capture.monitor)
        self._active_capture = capture
        self._active_selection_rect = QRect()
        self.transition_to(STATE_SELECTING)

        self._deps.selection_overlay.show_capture(
            capture=capture,
            on_confirm=self._confirm_selection,
            on_cancel=self._cancel_selection,
            on_focus_ready=self._handle_selection_focus_ready,
        )

    def _start_ocr(self, capture: MonitorCapture, cropped_image, selection_rect: QRect) -> None:
        def run_ocr() -> None:
            result = self._deps.ocr_pipeline.run(cropped_image)
            self._bridge.ocr_finished.emit(capture, QRect(selection_rect), result)

        threading.Thread(target=run_ocr, name="ocr-worker", daemon=True).start()

    def _handle_ocr_finished(self, capture: MonitorCapture, selection_rect: QRect, result: OCRResult) -> None:
        if self.state != STATE_PROCESSING:
            self._logger.info("Ignoring OCR result in state=%s", self.state)
            return

        self._active_capture = None

        if result.status != "ok" or not result.display_text:
            self._logger.info("OCR completed without displayable text status=%s", result.status)
            self._active_selection_rect = QRect()
            self.transition_to(STATE_IDLE)
            return

        self._logger.info("OCR text:\n%s", result.display_text)
        translated_text = self._translate_text(result.display_text)
        display_text = self._build_display_text(result.display_text, translated_text)
        self._deps.ocr_history.add(
            OCRHistoryEntry(
                mode=self._output_mode,
                ocr_text=result.display_text,
                translated_text=translated_text,
                display_text=display_text,
            )
        )

        self._deps.result_overlay.show_result(
            display_text,
            selection_rect,
            capture,
            on_dismiss=self._dismiss_result,
        )
        self.transition_to(STATE_SHOWING_RESULT)

    def _translate_text(self, text: str) -> str:
        if self._output_mode == OUTPUT_MODE_OCR_ONLY:
            return ""

        try:
            translated_text = self._translator.translate(text)
        except TranslationError:
            self._logger.exception("Translation failed")
            return ""

        translated_text = translated_text.strip()
        if translated_text:
            self._logger.info("Translated text:\n%s", translated_text)
        return translated_text

    def _build_display_text(self, ocr_text: str, translated_text: str) -> str:
        if self._output_mode == OUTPUT_MODE_BOTH and translated_text:
            return f"OCR:\n{ocr_text}\n\nTranslation:\n{translated_text}"

        if self._output_mode == OUTPUT_MODE_TRANSLATE and translated_text:
            return translated_text

        return ocr_text

    def _dismiss_result(self) -> None:
        self._logger.info("Result overlay dismissed")
        self._deps.result_overlay.hide_result()
        self._active_selection_rect = QRect()
        self.transition_to(STATE_IDLE)

    def transition_to(self, new_state: str) -> None:
        if new_state not in _ALLOWED_STATES:
            raise ValueError(f"Invalid state: {new_state}")

        if self.state == new_state:
            return

        self._logger.debug("State transition: %s -> %s", self.state, new_state)
        self.state = new_state
