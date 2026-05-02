# Phase 1 Design: OCR Overlay MVP

## Goal

Build Phase 1 as an OCR-first Windows desktop tool that runs this end-to-end flow:

1. Global hotkey
2. Capture active monitor screenshot
3. Let user select rectangular region
4. Crop selected region
5. Run local OCR
6. Show original detected text in result overlay

Phase 1 does not include translation, tray, history, settings UI, quadrilateral selection, or packaging polish.

## Product shape

Phase 1 runs as a background app with no main window in normal use.

User interaction is centered around one global hotkey: `Ctrl + Shift + Z`.

When the hotkey is pressed, the app starts capture flow immediately. The app should feel like a lightweight system utility, not a foreground desktop app.

## Scope boundaries

### Included

- Global hotkey trigger
- Screenshot capture using `mss`
- Fullscreen transparent selection overlay using PyQt6
- Rectangle-only selection
- Crop and coordinate mapping for selected region
- Local OCR using PaddleOCR
- GPU-preferred runtime with CPU fallback
- Result overlay showing detected source text
- Basic logging
- Manual end-to-end verification on real screenshots

### Excluded

- Translation flow
- System tray
- History or persistence UI
- Settings dialog
- Clipboard automation
- Timeout-based auto-hide behavior
- Quadrilateral selection
- Full support for fullscreen exclusive games
- Broad multi-monitor compatibility beyond active monitor / cursor monitor path
- Advanced preprocessing presets

## Recommended architecture

Phase 1 uses a controller-first architecture.

A single `AppController` owns state transitions and orchestrates the whole flow. UI modules stay narrow and event-driven. OCR and coordinate mapping stay isolated from Qt-heavy code where possible.

## Module layout

```text
main.py
core/
  app_controller.py
  hotkey.py
  screenshot.py
  coordinate_mapper.py
  preprocessor.py
  ocr_engine.py
ui/
  selection_overlay.py
  result_overlay.py
utils/
  logger.py
```

### Module responsibilities

| Module | Responsibility |
|---|---|
| `main.py` | Create `QApplication`, initialize controller, wire startup lifecycle |
| `core/app_controller.py` | Own app state, receive events, coordinate capture/OCR/result flow |
| `core/hotkey.py` | Register and forward global hotkey events without blocking Qt UI |
| `core/screenshot.py` | Capture screenshot for target monitor and return image plus monitor metadata |
| `core/coordinate_mapper.py` | Convert selection rectangle from Qt coordinate space to screenshot pixel space |
| `core/preprocessor.py` | Keep preprocessing minimal in Phase 1; pass-through or light grayscale path only |
| `core/ocr_engine.py` | Preload PaddleOCR, execute OCR, normalize output, handle GPU/CPU runtime path |
| `ui/selection_overlay.py` | Render screenshot-backed overlay and collect rectangle selection or cancel action |
| `ui/result_overlay.py` | Render OCR result text near selected region and close on explicit user action |
| `utils/logger.py` | Emit basic logs useful for debugging capture/OCR/runtime failures |

## State model

The app uses a strict minimal state machine:

```text
idle -> selecting -> processing -> showing_result -> idle
```

Only `AppController` may transition between these states.

### State rules

| State | Meaning | Allowed next states |
|---|---|---|
| `idle` | No active UI or OCR work running | `selecting` |
| `selecting` | Selection overlay visible, waiting for user input | `processing`, `idle`, `selecting` |
| `processing` | Region chosen, OCR work in progress | `showing_result`, `idle` |
| `showing_result` | Result overlay visible | `idle`, `selecting` |

### Event handling rules

- Hotkey in `idle`: start new capture flow.
- Hotkey in `selecting`: cancel current selection and restart capture flow immediately.
- Hotkey in `processing`: ignore new hotkey.
- Hotkey in `showing_result`: close current result overlay and start fresh capture flow.
- `Esc` in `selecting`: cancel and return to `idle`.
- `Esc` in `showing_result`: close overlay and return to `idle`.

## End-to-end flow

```text
Hotkey pressed
  -> AppController validates state
  -> screenshot.py captures target monitor
  -> selection_overlay.py shows screenshot-backed fullscreen overlay
  -> user drags rectangle and confirms
  -> coordinate_mapper.py maps Qt rect to pixel rect
  -> AppController crops selected image
  -> preprocessor.py prepares OCR input
  -> ocr_engine.py runs OCR in worker thread
  -> AppController receives normalized OCR result
  -> result_overlay.py renders text near selected area
  -> user dismisses with Esc or starts next capture
  -> AppController cleans up and returns to idle
```

## Threading model

UI work stays on Qt main thread.

OCR runs off the main thread.

This is the minimum concurrency model recommended for Phase 1:

- Hotkey integration must not block Qt event loop.
- Selection overlay and result overlay remain on main thread.
- OCR execution runs in worker thread and returns result back to main thread by signal/callback.
- Screenshot capture and crop may stay synchronous initially unless measurement shows visible UI lag.

This design keeps concurrency simple while removing the heaviest likely blocker from the UI thread.

## Target monitor strategy

Phase 1 only guarantees stable behavior for the monitor containing the mouse cursor when the hotkey is pressed.

This keeps monitor targeting explicit and avoids overcommitting to every possible Windows multi-monitor layout before core flow is validated.

`screenshot.py` and `selection_overlay.py` must operate against the same target monitor context for each capture cycle.

## Coordinate mapping design

`coordinate_mapper.py` is a dedicated module because it is one of the highest-risk parts of the MVP.

### Inputs

- Selection rectangle reported by overlay in Qt coordinate space
- Target monitor metadata from screenshot capture
- Any scale information required to translate logical coordinates to physical pixels

### Outputs

- Normalized crop rectangle in screenshot pixel coordinates

### Required behavior

- Normalize reverse drag directions
- Clamp crop rectangle to screenshot bounds
- Map logical Qt coordinates to physical screenshot pixels
- Support monitor origins that may not start at `(0, 0)`
- Be testable without launching full UI

## OCR boundary

`ocr_engine.py` should expose a narrow interface.

### Input

- Prepared crop image

### Output

A normalized OCR result structure containing at least:

- extracted lines
- confidence values or aggregate confidence
- joined display text
- status such as `ok`, `no_text`, or `error`

`AppController` should not depend on PaddleOCR raw output shape.

## OCR runtime behavior

- Preload PaddleOCR during app startup to reduce cold-start delay.
- Prefer GPU runtime when available.
- If GPU path fails at initialization or execution, fall back to CPU path inside OCR module.
- Log which runtime path is active.
- Filter low-confidence results by an initial threshold.
- If no text survives filtering, return `no_text`.

Phase 1 should not introduce multiple OCR presets or aggressive preprocessing branches yet.

## Preprocessing design

`preprocessor.py` stays deliberately minimal in Phase 1.

Recommended baseline:

- pass image through unchanged, or
- apply only a light grayscale path if needed for stability

The purpose of Phase 1 is validating full OCR flow, not optimizing difficult image classes yet. Advanced preprocessing belongs to Phase 2.

## Selection overlay behavior

`selection_overlay.py` should:

- show fullscreen transparent overlay over captured monitor image
- dim background while preserving screenshot visibility
- allow rectangle drag only
- display live coordinates and size while dragging
- support `Enter` to confirm and `Esc` to cancel

The selection overlay should not own OCR logic or coordinate mapping policy.

## Result overlay behavior

`result_overlay.py` should:

- display detected source text near selected region
- reposition if default placement would push overlay out of screen bounds
- use simple readable styling
- remain visible until user presses `Esc` or starts next capture

If OCR returns no text, show short explicit result such as `No text detected` instead of failing silently.

## Error handling policy

Phase 1 uses soft-fail behavior.

### Required outcomes

- OCR failure must not crash app.
- GPU path failure must not crash app.
- Cancelled selection must cleanly return app to `idle`.
- Empty OCR result must still complete flow with explicit user-visible outcome.

Logging should be good enough to distinguish at least:

- hotkey trigger
- screenshot target monitor
- selection confirmed or cancelled
- OCR runtime path used
- OCR success / no text / error

## Verification strategy

Manual verification is primary for Phase 1. Small automated checks support high-risk pure logic.

### Manual checks

Use real screenshots, including the existing sample fixture set already added to repo.

Minimum manual validation:

1. Hotkey opens selection overlay from normal desktop/app context.
2. Rectangle selection works reliably.
3. Confirmed selection produces OCR attempt on real image content.
4. Result overlay shows OCR text or `No text detected`.
5. `Esc` closes overlay.
6. New capture replaces previous result flow correctly.
7. At least one DPI setting above 100% is tested if environment allows.

### Automated checks

Focus only on narrow logic that can be tested without heavy UI orchestration:

- rectangle normalization
- crop bound clamping
- logical-to-physical coordinate scaling
- basic controller state transition rules

## Phase 1 success criteria

Phase 1 is complete when all conditions below are true:

- App runs headless in background without main window for normal flow.
- `Ctrl + Shift + Z` starts capture flow.
- User can select rectangle on target monitor.
- Selected region crops correctly for tested DPI cases.
- OCR runs on real captured image region.
- Result overlay shows extracted text or explicit no-text result.
- App returns cleanly to `idle` on cancel, failure, dismiss, and next-capture flow.
- GPU-preferred path works when available, and CPU fallback path is structurally supported.

## Deferred work

These are intentionally left out of this spec and should not be pulled into implementation plan for Phase 1 unless scope is explicitly changed:

- translation
- tray icon
- clipboard copy
- history
- settings UI
- timeout-based dismissal
- quadrilateral selection
- OCR preset tuning
- packaging and distribution polish
