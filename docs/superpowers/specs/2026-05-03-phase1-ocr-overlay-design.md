# Phase 1 Design: OCR Overlay MVP

## Goal

Build Phase 1 as an OCR-first Windows desktop tool that runs this end-to-end flow:

1. Global hotkey
2. Capture screenshot of monitor containing cursor at hotkey time
3. Let user select rectangular region
4. Crop selected region
5. Run local OCR
6. Show original detected text in result overlay

Phase 1 does not include translation, tray, history, settings UI, quadrilateral selection, or packaging polish.

## Product shape

Phase 1 runs as a background app with no main window in normal use.

User interaction is centered around one global hotkey: `Ctrl + Shift + Z`.

When the hotkey is pressed, the app starts capture flow immediately on the monitor containing the cursor at hotkey time. The app should feel like a lightweight system utility, not a foreground desktop app.

## Hotkey backend

Phase 1 should use a concrete Windows global hotkey backend rather than a cross-platform abstraction.

Recommended approach: wrap the native Windows `RegisterHotKey` API via `ctypes` or equivalent thin binding.

Required behavior:

- register exactly one global hotkey binding for `Ctrl + Shift + Z`
- detect registration failure cleanly if another app already owns the shortcut
- log registration success or failure at startup
- unregister hotkey on clean shutdown
- dispatch hotkey events into `AppController` without blocking Qt UI thread

This choice reduces ambiguity around Windows focus behavior and keeps Phase 1 aligned with native Windows utility behavior.

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
- Broad multi-monitor compatibility beyond cursor monitor path
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
| `core/hotkey.py` | Register native Windows global hotkey and forward events without blocking Qt UI |
| `core/screenshot.py` | Capture screenshot for target monitor and return image plus monitor metadata |
| `core/coordinate_mapper.py` | Convert selection rectangle from Qt coordinate space to screenshot pixel space |
| `core/preprocessor.py` | Keep preprocessing minimal in Phase 1; pass-through or light grayscale path only |
| `core/ocr_engine.py` | Preload PaddleOCR, execute OCR, normalize output, handle GPU/CPU runtime path |
| `ui/selection_overlay.py` | Render screenshot-backed overlay and collect rectangle selection or cancel action |
| `ui/result_overlay.py` | Render OCR result text near selected region and close on explicit user action |
| `utils/logger.py` | Emit basic logs useful for debugging capture/OCR/runtime failures |

## Phase 1 constants

Keep Phase 1 constants owned in one place instead of scattering them across modules.

Recommended constants for Phase 1:

- hotkey definition: `Ctrl + Shift + Z`
- OCR confidence threshold: `0.70`
- minimum valid crop size: `4 x 4` physical pixels

For Phase 1, OCR confidence threshold should be defined in `core/ocr_engine.py` as the single source of truth and logged at startup. Later configurability is explicitly deferred.

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
- Phase 1 does not queue pending capture requests while in `processing`; extra hotkeys during OCR are dropped.
- Hotkey in `showing_result`: close current result overlay and start fresh capture flow.
- `Esc` in `selecting`: cancel and return to `idle`.
- `Esc` in `showing_result`: close overlay and return to `idle`.

### Selection validity rules

- Normalize drag direction before validation.
- Converted crop must be at least `4 x 4` physical pixels.
- If crop is smaller than minimum valid size, treat action as cancel and return to `idle` without running OCR.
- This case should be logged as invalid selection rather than OCR failure.

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

- hotkey integration must not block Qt event loop
- selection overlay and result overlay remain on main thread
- OCR execution runs in worker thread and returns result back to main thread by signal/callback
- screenshot capture and crop may stay synchronous initially unless measurement shows visible UI lag

This design keeps concurrency simple while removing the heaviest likely blocker from the UI thread.

## Overlay window contract

Both overlay windows need explicit windowing behavior in Phase 1 so implementation does not drift during UI debugging.

### Selection overlay requirements

- frameless full-screen window scoped to target monitor
- topmost while active
- accepts keyboard focus immediately so `Enter` and `Esc` work reliably
- captures pointer interaction for drag selection
- if focus acquisition fails, cancel flow cleanly and log failure instead of leaving partial UI state

### Result overlay requirements

- frameless topmost window
- shown above normal desktop apps and windowed or borderless apps where Qt window flags allow it
- accepts `Esc` handling while visible
- does not block next capture flow from replacing it

This spec does not require solving every fullscreen exclusive edge case in Phase 1.

## Target monitor strategy

Phase 1 only guarantees stable behavior for the monitor containing the mouse cursor when the hotkey is pressed.

This keeps monitor targeting explicit and avoids overcommitting to every possible Windows multi-monitor layout before core flow is validated.

`screenshot.py` and `selection_overlay.py` must operate against the same target monitor context for each capture cycle.

## Coordinate mapping design

`coordinate_mapper.py` is a dedicated module because it is one of the highest-risk parts of the MVP.

### Inputs

- selection rectangle reported by overlay in Qt coordinate space
- target monitor metadata from screenshot capture
- scale information required to translate logical coordinates to physical pixels

### Outputs

- normalized crop rectangle in screenshot pixel coordinates

### Canonical rule

Use overlay-local Qt coordinates as the single input coordinate system. Convert them into screenshot-local physical pixel coordinates before cropping.

Recommended transform for each edge:

- `pixel_left = floor(logical_left * scale_x)`
- `pixel_top = floor(logical_top * scale_y)`
- `pixel_right = ceil(logical_right * scale_x)`
- `pixel_bottom = ceil(logical_bottom * scale_y)`

Then:

1. normalize drag direction in logical space
2. convert to pixel edges
3. clamp pixel edges to screenshot bounds
4. derive crop width and height from clamped edges

Treat left/top as inclusive edges and right/bottom as exclusive edges.

### Required behavior

- normalize reverse drag directions
- clamp crop rectangle to screenshot bounds
- map logical Qt coordinates to physical screenshot pixels
- support monitor origins that may not start at `(0, 0)`
- be testable without launching full UI

### Numeric examples

Example 1: scale 1.0
- logical rect `(10, 20)` to `(110, 60)`
- pixel rect becomes left `10`, top `20`, right `110`, bottom `60`
- crop size `100 x 40`

Example 2: scale 1.5
- logical rect `(10, 20)` to `(110, 60)`
- pixel rect becomes left `15`, top `30`, right `165`, bottom `90`
- crop size `150 x 60`

Example 3: reverse drag with clamping
- logical drag start `(200, 100)`, end `(20, 30)` on screenshot width `240`, height `120`, scale `1.0`
- normalize to logical left `20`, top `30`, right `200`, bottom `100`
- if converted edge exceeds bounds, clamp before deriving final width and height

## OCR boundary

`ocr_engine.py` should expose a narrow interface.

### Input

- prepared crop image

### Output

A normalized OCR result structure containing at least:

- extracted lines
- confidence values or aggregate confidence
- joined display text
- status such as `ok`, `no_text`, or `error`

`AppController` should not depend on PaddleOCR raw output shape.

## OCR runtime behavior

- preload PaddleOCR during app startup to reduce cold-start delay
- prefer GPU runtime when available
- if GPU path fails at initialization or execution, fall back to CPU path inside OCR module
- log which runtime path is active
- filter low-confidence results by the single threshold owned by `core/ocr_engine.py`
- if no text survives filtering, return `no_text`

Phase 1 should not introduce multiple OCR presets or aggressive preprocessing branches yet.

## Preprocessing design

`preprocessor.py` stays deliberately minimal in Phase 1.

Recommended baseline:

- pass image through unchanged, or
- apply only a light grayscale path if needed for stability

Purpose of Phase 1 is validating full OCR flow, not optimizing difficult image classes yet. Advanced preprocessing belongs to Phase 2.

## Selection overlay behavior

`selection_overlay.py` should:

- show fullscreen transparent overlay over captured monitor image
- dim background while preserving screenshot visibility
- allow rectangle drag only
- display live coordinates and size while dragging
- support `Enter` to confirm and `Esc` to cancel

Selection overlay should not own OCR logic or coordinate mapping policy.

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

- OCR failure must not crash app
- GPU path failure must not crash app
- cancelled selection must cleanly return app to `idle`
- empty OCR result must still complete flow with explicit user-visible outcome

Logging should be good enough to distinguish at least:

- hotkey trigger
- screenshot target monitor
- selection confirmed or cancelled
- OCR runtime path used
- OCR success / no text / error

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

- hotkey integration must not block Qt event loop
- selection overlay and result overlay remain on main thread
- OCR execution runs in worker thread and returns result back to main thread by signal/callback
- screenshot capture and crop may stay synchronous initially unless measurement shows visible UI lag

This design keeps concurrency simple while removing the heaviest likely blocker from the UI thread.

## Overlay window contract

Both overlay windows need explicit windowing behavior in Phase 1 so implementation does not drift during UI debugging.

### Selection overlay requirements

- frameless full-screen window scoped to target monitor
- topmost while active
- accepts keyboard focus immediately so `Enter` and `Esc` work reliably
- captures pointer interaction for drag selection
- if focus acquisition fails, cancel flow cleanly and log failure instead of leaving partial UI state

### Result overlay requirements

- frameless topmost window
- shown above normal desktop apps and windowed or borderless apps where Qt window flags allow it
- accepts `Esc` handling while visible
- does not block next capture flow from replacing it

This spec does not require solving every fullscreen exclusive edge case in Phase 1.

## Target monitor strategy

Phase 1 only guarantees stable behavior for the monitor containing the mouse cursor when the hotkey is pressed.

This keeps monitor targeting explicit and avoids overcommitting to every possible Windows multi-monitor layout before core flow is validated.

`screenshot.py` and `selection_overlay.py` must operate against the same target monitor context for each capture cycle.

## Coordinate mapping design

`coordinate_mapper.py` is a dedicated module because it is one of the highest-risk parts of the MVP.

### Inputs

- selection rectangle reported by overlay in Qt coordinate space
- target monitor metadata from screenshot capture
- scale information required to translate logical coordinates to physical pixels

### Outputs

- normalized crop rectangle in screenshot pixel coordinates

### Canonical rule

Use overlay-local Qt coordinates as the single input coordinate system. Convert them into screenshot-local physical pixel coordinates before cropping.

Recommended transform for each edge:

- `pixel_left = floor(logical_left * scale_x)`
- `pixel_top = floor(logical_top * scale_y)`
- `pixel_right = ceil(logical_right * scale_x)`
- `pixel_bottom = ceil(logical_bottom * scale_y)`

Then:

1. normalize drag direction in logical space
2. convert to pixel edges
3. clamp pixel edges to screenshot bounds
4. derive crop width and height from clamped edges

Treat left/top as inclusive edges and right/bottom as exclusive edges.

### Required behavior

- normalize reverse drag directions
- clamp crop rectangle to screenshot bounds
- map logical Qt coordinates to physical screenshot pixels
- support monitor origins that may not start at `(0, 0)`
- be testable without launching full UI

### Numeric examples

Example 1: scale 1.0
- logical rect `(10, 20)` to `(110, 60)`
- pixel rect becomes left `10`, top `20`, right `110`, bottom `60`
- crop size `100 x 40`

Example 2: scale 1.5
- logical rect `(10, 20)` to `(110, 60)`
- pixel rect becomes left `15`, top `30`, right `165`, bottom `90`
- crop size `150 x 60`

Example 3: reverse drag with clamping
- logical drag start `(200, 100)`, end `(20, 30)` on screenshot width `240`, height `120`, scale `1.0`
- normalize to logical left `20`, top `30`, right `200`, bottom `100`
- if converted edge exceeds bounds, clamp before deriving final width and height

## OCR boundary

`ocr_engine.py` should expose a narrow interface.

### Input

- prepared crop image

### Output

A normalized OCR result structure containing at least:

- extracted lines
- confidence values or aggregate confidence
- joined display text
- status such as `ok`, `no_text`, or `error`

`AppController` should not depend on PaddleOCR raw output shape.

## OCR runtime behavior

- preload PaddleOCR during app startup to reduce cold-start delay
- prefer GPU runtime when available
- if GPU path fails at initialization or execution, fall back to CPU path inside OCR module
- log which runtime path is active
- filter low-confidence results by the single threshold owned by `core/ocr_engine.py`
- if no text survives filtering, return `no_text`

Phase 1 should not introduce multiple OCR presets or aggressive preprocessing branches yet.

## Preprocessing design

`preprocessor.py` stays deliberately minimal in Phase 1.

Recommended baseline:

- pass image through unchanged, or
- apply only a light grayscale path if needed for stability

Purpose of Phase 1 is validating full OCR flow, not optimizing difficult image classes yet. Advanced preprocessing belongs to Phase 2.

## Selection overlay behavior

`selection_overlay.py` should:

- show fullscreen transparent overlay over captured monitor image
- dim background while preserving screenshot visibility
- allow rectangle drag only
- display live coordinates and size while dragging
- support `Enter` to confirm and `Esc` to cancel

Selection overlay should not own OCR logic or coordinate mapping policy.

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

- OCR failure must not crash app
- GPU path failure must not crash app
- cancelled selection must cleanly return app to `idle`
- empty OCR result must still complete flow with explicit user-visible outcome

Logging should be good enough to distinguish at least:

- hotkey trigger
- screenshot target monitor
- selection confirmed or cancelled
- OCR runtime path used
- OCR success / no text / error

## Verification strategy

Manual verification is primary for Phase 1. Small automated checks support high-risk pure logic.

### Manual checks

Use real screenshots, including existing sample fixture set already added to repo.

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

- app runs headless in background without main window for normal flow
- `Ctrl + Shift + Z` starts capture flow
- user can select rectangle on target monitor
- selected region crops correctly for tested DPI cases
- OCR runs on real captured image region
- result overlay shows extracted text or explicit no-text result
- app returns cleanly to `idle` on cancel, failure, dismiss, and next-capture flow
- GPU-preferred path works when available, and CPU fallback path is structurally supported

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
