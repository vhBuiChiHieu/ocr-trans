# PROJECT_CONTEXT

# Môi trường
- môi trường riêng tại .venv/

## Repo này là gì

Repo này là app OCR local cho Windows.

Mục tiêu chính:

1. Bấm `Ctrl+Shift+Z`
2. Chụp monitor đang có con trỏ
3. Kéo chọn vùng cần OCR
4. Đổi tọa độ vùng chọn của Qt sang pixel thật của ảnh chụp
5. Chạy OCR bằng PaddleOCR
6. Hiển thị text bằng overlay

Hiện trạng: repo đã chạy được flow end-to-end trên Windows: hotkey -> screenshot monitor theo con trỏ -> selection overlay -> coordinate mapping -> crop ảnh -> OCR thật bằng PaddleOCR -> result overlay. Chưa có translation.

---

## Nên đọc file nào trước

| File | Vai trò |
|---|---|
| `main.py:8` | Entry point, tạo `QApplication` và `AppController` |
| `core/app_controller.py:37` | Coordinator chính của app |
| `core/hotkey.py:47` | Đăng ký hotkey toàn cục Windows |
| `core/screenshot.py:32` | Chụp monitor theo vị trí con trỏ |
| `ui/selection_overlay.py:17` | Overlay để kéo chọn vùng |
| `core/coordinate_mapper.py:28` | Map vùng chọn Qt sang pixel thật của ảnh |
| `core/preprocessor.py:14` | Chuẩn hóa ảnh và preset preprocess (`baseline`, `small_text`, `outlined_high_contrast`) |
| `core/ocr_engine.py:41` | Wrapper quanh PaddleOCR, preload CPU, mode `normal`/`inverted`/`auto` |
| `core/ocr_pipeline.py:15` | Nối preprocess preset với OCR mode |
| `ui/result_overlay.py:11` | Overlay kết quả OCR thật, bám theo vùng chọn |
| `tests/test_coordinate_mapper.py:28` | Test logic mapping |
| `tests/test_ocr_engine.py:32` | Test OCR normalization, mode selection, runtime config |
| `tests/test_app_controller.py:146` | Test flow end-to-end trong controller |

---

## Cấu trúc repo ngắn gọn

```text
core/    logic lõi
ui/      overlay UI
utils/   logging
tests/   unit test và smoke test
imgs/    ảnh mẫu OCR
```

---

## Logic chính hiện có

### 1. App khởi động

- `main.py:8` tạo `QApplication`
- tạo `AppController`
- gọi `controller.start()`

### 2. App đăng ký hotkey toàn cục

- `core/hotkey.py:47`
- dùng Windows API qua `RegisterHotKey`
- hotkey hiện tại là `Ctrl+Shift+Z`

### 3. Khi bấm hotkey

`AppController.handle_hotkey()` tại `core/app_controller.py:63` sẽ:

1. bỏ qua nếu app không ở state phù hợp
2. chụp monitor đang chứa con trỏ
3. lưu capture hiện tại
4. mở `SelectionOverlay`

### 4. Người dùng chọn vùng

- `ui/selection_overlay.py:39`
- overlay hiển thị screenshot nền
- hỗ trợ cả kéo-thả và click 2 góc để chọn `QRect`
- kéo-thả sẽ tự xác nhận khi thả chuột
- `Enter` vẫn xác nhận được nếu đã có vùng chọn
- `Esc` để hủy

### 5. Map tọa độ vùng chọn

- `core/coordinate_mapper.py:30`
- input là `QRect` local của overlay
- output là `PixelRect` theo pixel thật trong ảnh screenshot

Đây là phần quan trọng vì Qt dùng logical coordinates, còn ảnh screenshot dùng physical pixels.

### 6. OCR pipeline đã nối xong

- `core/ocr_engine.py:41`
- runtime hiện preload trực tiếp bằng CPU
- hỗ trợ mode `normal`, `inverted`, `auto`
- mặc định app đang dùng `OCR_MODE_NORMAL` để giữ tốc độ tốt hơn
- CPU runtime đang cấu hình `cpu_threads = 4`
- kết quả được normalize về `OCRResult`
- lọc text theo threshold `0.70`

`AppController` hiện đã map crop rect, crop ảnh thật, chạy preprocess/OCR trên worker thread, rồi hiện kết quả bằng `ResultOverlay`.

---

## State machine hiện tại

State nằm ở `core/app_controller.py:14`:

- `idle`
- `selecting`
- `processing`
- `showing_result`

Thực tế đang dùng đủ cả 4 state:

- `idle`
- `selecting`
- `processing`
- `showing_result`

Flow OCR hiện chuyển state đầy đủ từ chọn vùng -> OCR nền -> hiện kết quả -> dismiss về `idle`.

---

## Thành phần cần hiểu rõ nhất

| Thành phần | Vì sao quan trọng |
|---|---|
| `AppController` | Nơi nối toàn bộ flow |
| `ScreenshotService` | Quyết định monitor nào bị chụp |
| `SelectionOverlay` | Nơi sinh ra vùng chọn của người dùng |
| `CoordinateMapper` | Chỗ dễ sai nhất vì DPI scaling / multi-monitor |
| `OCREngine` | Chỗ xử lý OCR và fallback runtime |

Nếu người mới chỉ có thời gian đọc ít, nên đọc theo thứ tự:

1. `main.py`
2. `core/app_controller.py`
3. `ui/selection_overlay.py`
4. `core/screenshot.py`
5. `core/coordinate_mapper.py`
6. `core/ocr_engine.py`

---

## Điều đã làm xong vs chưa làm xong

| Mục | Trạng thái |
|---|---|
| App Qt khởi động | Xong |
| Logging cơ bản | Xong |
| Hotkey toàn cục Windows | Xong |
| Chụp monitor theo con trỏ | Xong |
| Overlay chọn vùng | Xong |
| Coordinate mapping | Xong |
| OCR engine độc lập | Xong |
| CPU preload/runtime mặc định | Xong |
| Crop ảnh thật trong controller | Xong |
| Gọi OCR từ controller | Xong |
| Result overlay | Xong |
| End-to-end OCR overlay | Xong |
| Translation | Chưa xong |

---

## Test hiện có

| File | Mục đích |
|---|---|
| `tests/test_coordinate_mapper.py:28` | Test DPI scaling, reverse drag, clamp, monitor origin âm |
| `tests/test_ocr_engine.py:32` | Test normalize output, low confidence filter, inversion modes, runtime config |
| `tests/test_ocr_pipeline.py:32` | Test preset/mode wiring trong pipeline |
| `tests/test_app_controller.py:146` | Test crop + OCR + result overlay flow |
| `tests/smoke_ocr_samples.py:31` | Chạy OCR trên ảnh mẫu trong `imgs/ocr_test_input/` |

Nếu muốn hiểu repo nhanh, đọc test của `CoordinateMapper` và `OCREngine` khá hiệu quả vì chúng cho thấy logic cốt lõi và edge cases đang được bảo vệ.

---

## Lưu ý thực tế cho người mới

1. Repo này ưu tiên code thật hơn roadmap. Nếu docs và code lệch nhau, tin code trước.
2. App hiện phụ thuộc Windows cho phần hotkey toàn cục.
3. Bài toán khó vẫn nằm ở coordinate mapping, sample quality, và tuning OCR trên text nhỏ/outline.
4. MVP OCR overlay đã chạy được; bước lớn tiếp theo là đánh giá accuracy thêm và làm translation nếu cần.

---

## Tóm tắt 1 câu

Repo này đã có flow OCR overlay Windows chạy end-to-end; phần chưa có chủ yếu là translation và các vòng tuning accuracy sâu hơn.
