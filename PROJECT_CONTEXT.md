# PROJECT_CONTEXT

## Repo này là gì

Repo này là app OCR local cho Windows.

Mục tiêu chính:

1. Bấm `Ctrl+Shift+Z`
2. Chụp monitor đang có con trỏ
3. Kéo chọn vùng cần OCR
4. Đổi tọa độ vùng chọn của Qt sang pixel thật của ảnh chụp
5. Chạy OCR bằng PaddleOCR
6. Hiển thị text bằng overlay

Hiện trạng: repo đã làm xong phần hotkey, screenshot, selection overlay, coordinate mapping, và OCR engine. Phần nối end-to-end từ vùng chọn sang crop ảnh, OCR thật, rồi hiện kết quả vẫn chưa hoàn tất.

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
| `core/preprocessor.py:5` | Chuẩn hóa dữ liệu ảnh sang `numpy` |
| `core/ocr_engine.py:23` | Wrapper quanh PaddleOCR, có GPU/CPU fallback |
| `ui/result_overlay.py:1` | Overlay kết quả, hiện vẫn là stub |
| `tests/test_coordinate_mapper.py:28` | Test logic mapping |
| `tests/test_ocr_engine.py:32` | Test OCR normalization và fallback |

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

- `ui/selection_overlay.py:38`
- overlay hiển thị screenshot nền
- kéo chuột để chọn `QRect`
- `Enter` để xác nhận
- `Esc` để hủy

### 5. Map tọa độ vùng chọn

- `core/coordinate_mapper.py:30`
- input là `QRect` local của overlay
- output là `PixelRect` theo pixel thật trong ảnh screenshot

Đây là phần quan trọng vì Qt dùng logical coordinates, còn ảnh screenshot dùng physical pixels.

### 6. OCR engine đã sẵn nhưng chưa nối xong

- `core/ocr_engine.py:46`
- engine sẽ thử GPU trước, fail thì fallback CPU
- kết quả được normalize về `OCRResult`
- lọc text theo threshold `0.70`

Nhưng `AppController` hiện mới dừng ở bước map crop rect. Chưa crop ảnh, chưa gọi preprocess/OCR, chưa hiện kết quả.

---

## State machine hiện tại

State nằm ở `core/app_controller.py:14`:

- `idle`
- `selecting`
- `processing`
- `showing_result`

Thực tế đang dùng chủ yếu:

- `idle`
- `selecting`

`processing` và `showing_result` đã khai báo nhưng chưa có flow đầy đủ.

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
| GPU -> CPU fallback | Xong |
| Crop ảnh thật trong controller | Chưa xong |
| Gọi OCR từ controller | Chưa xong |
| Result overlay | Chưa xong |
| End-to-end OCR overlay | Chưa xong |

---

## Test hiện có

| File | Mục đích |
|---|---|
| `tests/test_coordinate_mapper.py:28` | Test DPI scaling, reverse drag, clamp, monitor origin âm |
| `tests/test_ocr_engine.py:32` | Test normalize output, low confidence filter, GPU/CPU fallback |
| `tests/smoke_ocr_samples.py:15` | Chạy OCR trên ảnh mẫu trong `imgs/ocr_test_input/` |

Nếu muốn hiểu repo nhanh, đọc test của `CoordinateMapper` và `OCREngine` khá hiệu quả vì chúng cho thấy logic cốt lõi và edge cases đang được bảo vệ.

---

## Lưu ý thực tế cho người mới

1. Repo này ưu tiên code thật hơn roadmap. Roadmap còn nhắc `pynput` và `opencv`, nhưng code hiện tại không dùng `pynput` và preprocessor vẫn rất mỏng.
2. App hiện phụ thuộc Windows cho phần hotkey toàn cục.
3. Bài toán khó nhất hiện tại không phải OCR model, mà là nối đúng selection overlay với pixel thật của screenshot.
4. Nếu muốn hoàn tất MVP, điểm bắt đầu hợp lý nhất là `core/app_controller.py:101` và `ui/result_overlay.py:1`.

---

## Tóm tắt 1 câu

Repo này đã có xương sống cho OCR overlay Windows; phần còn thiếu chủ yếu là đoạn nối cuối từ vùng chọn -> crop -> OCR -> hiện kết quả.
