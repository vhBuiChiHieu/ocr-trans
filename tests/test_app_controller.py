from __future__ import annotations

import logging
import tempfile
import textwrap
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PyQt6.QtCore import QRect

from core.app_controller import (
    OUTPUT_MODE_BOTH,
    OUTPUT_MODE_OCR_ONLY,
    AppController,
    AppControllerDependencies,
    STATE_IDLE,
    STATE_PROCESSING,
    STATE_SELECTING,
    STATE_SHOWING_RESULT,
)
from core.app_controller import ScriptTranslator, TranslationError
from core.coordinate_mapper import PixelRect
from core.ocr_engine import OCRLine, OCRResult
from core.ocr_pipeline import OCRPipeline
from core.preprocessor import PRESET_BASELINE
from core.screenshot import MonitorBounds, MonitorCapture
from core.settings_store import AppSettings
from ui.selection_overlay import SelectionResult


class FakeHotkeyManager:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class FakeScreenshotService:
    def __init__(self, capture: MonitorCapture) -> None:
        self.capture = capture
        self.log_calls = 0

    def capture_cursor_monitor(self) -> MonitorCapture:
        return self.capture

    def log_capture_target(self, _logger, _monitor) -> None:
        self.log_calls += 1


class FakeCoordinateMapper:
    def __init__(self, crop_rect: PixelRect | None, force_none: bool = False) -> None:
        self.crop_rect = crop_rect
        self.force_none = force_none

    def map_selection_rect(self, _selection_rect: QRect, _capture: MonitorCapture) -> PixelRect | None:
        if self.force_none:
            return None
        return self.crop_rect

    @staticmethod
    def crop_bounds(crop_rect: PixelRect) -> tuple[int, int, int, int]:
        return crop_rect.left, crop_rect.top, crop_rect.right, crop_rect.bottom


class FakePreprocessor:
    def __init__(self, output: np.ndarray) -> None:
        self.output = output

    def preprocess(self, _image):
        return self.output.copy()


class FakeOCREngine:
    def __init__(self, result: OCRResult) -> None:
        self.result = result
        self.preload_calls = 0

    def preload(self) -> None:
        self.preload_calls += 1

    def recognize(self, image) -> OCRResult:
        return self.result


class FakeOCRPipeline:
    def __init__(self, result: OCRResult) -> None:
        self.result = result
        self.images: list[np.ndarray] = []

    def run(self, image) -> OCRResult:
        self.images.append(image.copy())
        return self.result


class FakeSelectionOverlay:
    def __init__(self) -> None:
        self.show_calls: list[dict[str, object]] = []
        self.hide_calls = 0

    def show_capture(self, capture, on_confirm, on_cancel, on_focus_ready) -> None:
        self.show_calls.append(
            {
                "capture": capture,
                "on_confirm": on_confirm,
                "on_cancel": on_cancel,
                "on_focus_ready": on_focus_ready,
            }
        )

    def hide_overlay(self) -> None:
        self.hide_calls += 1


class FakeHistoryStore:
    def __init__(self) -> None:
        self.entries = []

    def add(self, entry) -> None:
        self.entries.append(entry)


class FakeSettingsStore:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self.saved_settings: list[AppSettings] = []

    def load(self) -> AppSettings:
        return self.settings

    def save(self, settings: AppSettings) -> None:
        self.saved_settings.append(settings)


class FakeResultOverlay:
    def __init__(self) -> None:
        self.show_calls: list[tuple[str, QRect, MonitorCapture, object]] = []
        self.hide_calls = 0
        self.font_size = None
        self.font_family = None

    def show_result(self, text: str, anchor_rect: QRect, capture: MonitorCapture, on_dismiss) -> None:
        self.show_calls.append((text, QRect(anchor_rect), capture, on_dismiss))

    def hide_result(self) -> None:
        self.hide_calls += 1

    def set_font_size(self, font_size: int) -> None:
        self.font_size = font_size

    def set_font_family(self, font_family: str) -> None:
        self.font_family = font_family


class ImmediateThread:
    def __init__(self, target, name=None, daemon=None) -> None:
        self._target = target

    def start(self) -> None:
        self._target()


@dataclass
class ThreadPatch:
    original: object

    def restore(self) -> None:
        import core.app_controller as app_controller_module

        app_controller_module.threading.Thread = self.original


def patch_thread():
    import core.app_controller as app_controller_module

    original = app_controller_module.threading.Thread
    app_controller_module.threading.Thread = ImmediateThread
    return ThreadPatch(original=original)


class FakeTranslator:
    def __init__(self, translated_text: str = "", error: Exception | None = None) -> None:
        self.translated_text = translated_text
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def translate(self, text: str, sl: str = "en", tl: str = "vi") -> str:
        self.calls.append((text, sl, tl))
        if self.error is not None:
            raise self.error
        return self.translated_text


class ScriptTranslatorTests(unittest.TestCase):
    def test_translate_reads_unicode_stdout_from_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / "translator_stub.py"
            script_path.write_text(
                textwrap.dedent(
                    """
                    import sys

                    print("đây là bản dịch")
                    """
                ).strip(),
                encoding="utf-8",
            )

            translator = ScriptTranslator(script_path=script_path)

            self.assertEqual(translator.translate("hello"), "đây là bản dịch")


class AppControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.logger = logging.getLogger("test_app_controller")
        self.capture = MonitorCapture(
            image=SimpleNamespace(width=20, height=20),
            monitor=MonitorBounds(left=0, top=0, width=20, height=20),
            scale_x=1.0,
            scale_y=1.0,
        )

    def make_controller(
        self,
        ocr_result: OCRResult,
        crop_rect: PixelRect | None = None,
        invalid_crop: bool = False,
        translator: FakeTranslator | None = None,
    ):
        preprocessed = np.arange(20 * 20 * 3, dtype=np.uint8).reshape((20, 20, 3))
        hotkey = FakeHotkeyManager()
        screenshot = FakeScreenshotService(self.capture)
        mapper = FakeCoordinateMapper(
            PixelRect(left=2, top=3, right=8, bottom=9) if crop_rect is None else crop_rect,
            force_none=invalid_crop,
        )
        preprocessor = FakePreprocessor(preprocessed)
        ocr_engine = FakeOCREngine(ocr_result)
        ocr_pipeline = FakeOCRPipeline(ocr_result)
        selection_overlay = FakeSelectionOverlay()
        result_overlay = FakeResultOverlay()
        history = FakeHistoryStore()
        settings_store = FakeSettingsStore()
        deps = AppControllerDependencies(
            hotkey=hotkey,
            screenshot=screenshot,
            coordinate_mapper=mapper,
            preprocessor=preprocessor,
            ocr_engine=ocr_engine,
            ocr_pipeline=ocr_pipeline,
            selection_overlay=selection_overlay,
            result_overlay=result_overlay,
            ocr_history=history,
            settings_store=settings_store,
        )
        controller = AppController(logger=self.logger, deps=deps)
        controller._translator = translator or FakeTranslator()
        return controller, ocr_pipeline, ocr_engine, selection_overlay, result_overlay, history, settings_store

    def test_start_warms_ocr_in_background(self) -> None:
        controller, _ocr_pipeline, ocr_engine, _selection_overlay, _result_overlay, _history, _settings_store = self.make_controller(
            OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")
        )
        thread_patch = patch_thread()
        try:
            controller.start()
        finally:
            thread_patch.restore()

        self.assertTrue(controller._deps.hotkey.started)
        self.assertEqual(ocr_engine.preload_calls, 1)

    def test_handle_hotkey_starts_selection_flow(self) -> None:
        controller, _ocr_pipeline, _ocr_engine, selection_overlay, _result_overlay, _history, _settings_store = self.make_controller(
            OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")
        )

        controller.handle_hotkey()

        self.assertEqual(controller.state, STATE_SELECTING)
        self.assertEqual(len(selection_overlay.show_calls), 1)

    def test_confirm_selection_translates_ocr_text_before_showing_result_overlay(self) -> None:
        translator = FakeTranslator(translated_text="Van ban da dich")
        controller, ocr_pipeline, _ocr_engine, selection_overlay, result_overlay, history, _settings_store = self.make_controller(
            OCRResult(
                lines=[OCRLine(text="Detected text", confidence=0.95)],
                display_text="Detected text",
                average_confidence=0.95,
                status="ok",
            ),
            translator=translator,
        )
        thread_patch = patch_thread()
        try:
            controller.handle_hotkey()
            on_confirm = selection_overlay.show_calls[0]["on_confirm"]
            on_confirm(SelectionResult(rect=QRect(2, 3, 6, 6)))
        finally:
            thread_patch.restore()

        self.assertEqual(selection_overlay.hide_calls, 1)
        self.assertEqual(controller.state, STATE_SHOWING_RESULT)
        self.assertEqual(len(ocr_pipeline.images), 1)
        self.assertEqual(ocr_pipeline.images[0].shape, (6, 6, 3))
        self.assertEqual(translator.calls, [("Detected text", "en", "vi")])
        self.assertEqual(len(result_overlay.show_calls), 1)
        text, rect, capture, _on_dismiss = result_overlay.show_calls[0]
        self.assertEqual(text, "Van ban da dich")
        self.assertEqual(rect, QRect(2, 3, 6, 6))
        self.assertIs(capture, self.capture)
        self.assertEqual(len(history.entries), 1)
        self.assertEqual(history.entries[0].ocr_text, "Detected text")
        self.assertEqual(history.entries[0].translated_text, "Van ban da dich")
        self.assertEqual(history.entries[0].display_text, "Van ban da dich")

    def test_confirm_selection_ocr_only_skips_translation(self) -> None:
        translator = FakeTranslator(translated_text="Van ban da dich")
        controller, _ocr_pipeline, _ocr_engine, selection_overlay, result_overlay, history, _settings_store = self.make_controller(
            OCRResult(
                lines=[OCRLine(text="Detected text", confidence=0.95)],
                display_text="Detected text",
                average_confidence=0.95,
                status="ok",
            ),
            translator=translator,
        )
        controller.set_output_mode(OUTPUT_MODE_OCR_ONLY)
        thread_patch = patch_thread()
        try:
            controller.handle_hotkey()
            on_confirm = selection_overlay.show_calls[0]["on_confirm"]
            on_confirm(SelectionResult(rect=QRect(2, 3, 6, 6)))
        finally:
            thread_patch.restore()

        self.assertEqual(translator.calls, [])
        text, _rect, _capture, _on_dismiss = result_overlay.show_calls[0]
        self.assertEqual(text, "Detected text")
        self.assertEqual(history.entries[0].mode, OUTPUT_MODE_OCR_ONLY)

    def test_confirm_selection_both_mode_shows_ocr_and_translation(self) -> None:
        translator = FakeTranslator(translated_text="Van ban da dich")
        controller, _ocr_pipeline, _ocr_engine, selection_overlay, result_overlay, history, _settings_store = self.make_controller(
            OCRResult(
                lines=[OCRLine(text="Detected text", confidence=0.95)],
                display_text="Detected text",
                average_confidence=0.95,
                status="ok",
            ),
            translator=translator,
        )
        controller.set_output_mode(OUTPUT_MODE_BOTH)
        thread_patch = patch_thread()
        try:
            controller.handle_hotkey()
            on_confirm = selection_overlay.show_calls[0]["on_confirm"]
            on_confirm(SelectionResult(rect=QRect(2, 3, 6, 6)))
        finally:
            thread_patch.restore()

        text, _rect, _capture, _on_dismiss = result_overlay.show_calls[0]
        self.assertEqual(text, "OCR:\nDetected text\n\nTranslation:\nVan ban da dich")
        self.assertEqual(history.entries[0].mode, OUTPUT_MODE_BOTH)
        self.assertEqual(history.entries[0].translated_text, "Van ban da dich")

    def test_confirm_selection_falls_back_to_ocr_text_when_translation_returns_empty(self) -> None:
        translator = FakeTranslator(translated_text="   ")
        controller, _ocr_pipeline, _ocr_engine, selection_overlay, result_overlay, history, _settings_store = self.make_controller(
            OCRResult(
                lines=[OCRLine(text="Detected text", confidence=0.95)],
                display_text="Detected text",
                average_confidence=0.95,
                status="ok",
            ),
            translator=translator,
        )
        thread_patch = patch_thread()
        try:
            controller.handle_hotkey()
            on_confirm = selection_overlay.show_calls[0]["on_confirm"]
            on_confirm(SelectionResult(rect=QRect(2, 3, 6, 6)))
        finally:
            thread_patch.restore()

        self.assertEqual(len(result_overlay.show_calls), 1)
        text, _rect, _capture, _on_dismiss = result_overlay.show_calls[0]
        self.assertEqual(text, "Detected text")

    def test_confirm_selection_falls_back_to_ocr_text_when_translation_fails(self) -> None:
        translator = FakeTranslator(error=TranslationError("boom"))
        controller, _ocr_pipeline, _ocr_engine, selection_overlay, result_overlay, history, _settings_store = self.make_controller(
            OCRResult(
                lines=[OCRLine(text="Line 1\nLine 2", confidence=0.95)],
                display_text="Line 1\nLine 2",
                average_confidence=0.95,
                status="ok",
            ),
            translator=translator,
        )
        thread_patch = patch_thread()
        try:
            controller.handle_hotkey()
            on_confirm = selection_overlay.show_calls[0]["on_confirm"]
            on_confirm(SelectionResult(rect=QRect(2, 3, 6, 6)))
        finally:
            thread_patch.restore()

        self.assertEqual(translator.calls, [("Line 1\nLine 2", "en", "vi")])
        self.assertEqual(len(result_overlay.show_calls), 1)
        text, _rect, _capture, _on_dismiss = result_overlay.show_calls[0]
        self.assertEqual(text, "Line 1\nLine 2")

    def test_confirm_selection_returns_idle_for_invalid_crop(self) -> None:
        controller, ocr_pipeline, _ocr_engine, selection_overlay, result_overlay, history, _settings_store = self.make_controller(
            OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text"),
            invalid_crop=True,
        )

        controller.handle_hotkey()
        on_confirm = selection_overlay.show_calls[0]["on_confirm"]
        on_confirm(SelectionResult(rect=QRect(1, 1, 2, 2)))

        self.assertEqual(controller.state, STATE_IDLE)
        self.assertEqual(len(ocr_pipeline.images), 0)
        self.assertEqual(len(result_overlay.show_calls), 0)
        self.assertEqual(history.entries, [])

    def test_handle_hotkey_ignores_input_while_processing(self) -> None:
        controller, _ocr_pipeline, _ocr_engine, selection_overlay, _result_overlay, _history, _settings_store = self.make_controller(
            OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")
        )
        controller.transition_to(STATE_PROCESSING)

        controller.handle_hotkey()

        self.assertEqual(len(selection_overlay.show_calls), 0)
        self.assertEqual(controller.state, STATE_PROCESSING)

    def test_dismiss_result_returns_idle(self) -> None:
        controller, _ocr_pipeline, _ocr_engine, selection_overlay, result_overlay, history, _settings_store = self.make_controller(
            OCRResult(
                lines=[OCRLine(text="Detected text", confidence=0.95)],
                display_text="Detected text",
                average_confidence=0.95,
                status="ok",
            )
        )
        thread_patch = patch_thread()
        try:
            controller.handle_hotkey()
            on_confirm = selection_overlay.show_calls[0]["on_confirm"]
            on_confirm(SelectionResult(rect=QRect(2, 3, 6, 6)))
        finally:
            thread_patch.restore()

        _text, _rect, _capture, on_dismiss = result_overlay.show_calls[0]
        on_dismiss()

        self.assertEqual(controller.state, STATE_IDLE)
        self.assertEqual(result_overlay.hide_calls, 1)

    def test_set_result_font_size_updates_overlay(self) -> None:
        controller, _ocr_pipeline, _ocr_engine, _selection_overlay, result_overlay, _history, settings_store = self.make_controller(
            OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")
        )

        controller.set_result_font_size(13)

        self.assertEqual(result_overlay.font_size, 13)
        self.assertEqual(settings_store.saved_settings[-1].font_size, 13)

    def test_set_result_font_family_updates_overlay(self) -> None:
        controller, _ocr_pipeline, _ocr_engine, _selection_overlay, result_overlay, _history, settings_store = self.make_controller(
            OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")
        )

        controller.set_result_font_family("Arial")

        self.assertEqual(result_overlay.font_family, "Arial")
        self.assertEqual(settings_store.saved_settings[-1].font_family, "Arial")

    def test_set_output_mode_saves_settings(self) -> None:
        controller, _ocr_pipeline, _ocr_engine, _selection_overlay, _result_overlay, _history, settings_store = self.make_controller(
            OCRResult(lines=[], display_text="", average_confidence=0.0, status="no_text")
        )

        controller.set_output_mode(OUTPUT_MODE_BOTH)

        self.assertEqual(settings_store.saved_settings[-1].output_mode, OUTPUT_MODE_BOTH)


if __name__ == "__main__":
    unittest.main()
