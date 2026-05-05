# orc-trans-app

Ứng dụng OCR + dịch text chạy local trên Windows.

Flow chính:

1. Bấm `Ctrl+Shift+Z`.
2. App chụp monitor đang có con trỏ.
3. Kéo chọn vùng cần OCR.
4. App map tọa độ Qt sang pixel thật của ảnh chụp.
5. Chạy OCR bằng PaddleOCR.
6. Dịch text sang tiếng Việt nếu bật chế độ dịch.
7. Hiển thị kết quả bằng overlay nổi trên màn hình.

## Tính năng chính

- Hotkey toàn cục `Ctrl+Shift+Z` để bắt đầu OCR.
- Chọn vùng bằng overlay kéo-thả hoặc click 2 góc.
- OCR bằng PaddleOCR với model `PP-OCRv5_mobile_det` và `en_PP-OCRv5_mobile_rec`.
- Dịch OCR text bằng script `scripts/google_translate.py`.
- Tray icon để đổi runtime config:
  - Font size: `Small / Medium / Large`.
  - Font family: đọc từ thư mục `./fonts/*.ttf` và `./fonts/*.otf`.
  - Output mode: `OCR only / Translate / Both`.
- Lưu config tại `config/settings.json`.
- Lưu log theo ngày tại `logs/YYYY-MM-DD.log`.
- Lưu OCR history gần đây tại `logs/ocr_history.json`, tối đa 20 entry.
- Có helper build `.exe` bằng PyInstaller.

## Yêu cầu môi trường

- Windows 10/11.
- Python 3.11+ khuyến nghị.
- Internet trong lần đầu tải model PaddleOCR và khi dùng tính năng dịch.
- Dependency Python nằm trong `requirements.txt`.

## Setup sau khi clone

```bash
git clone <repo-url>
cd orc-trans-app
python -m venv .venv
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -r requirements.txt
```

Nếu muốn dùng Paddle GPU, thay `paddlepaddle` trong `requirements.txt` bằng bản Paddle phù hợp CUDA của máy theo hướng dẫn chính thức của PaddlePaddle.

## Chạy app

```bash
.venv/Scripts/python main.py
```

Sau khi chạy:

1. App hiện tray icon.
2. Bấm `Ctrl+Shift+Z`.
3. Kéo chọn vùng có text.
4. Thả chuột để OCR.
5. Xem kết quả trong overlay.
6. Bấm `Esc` để đóng overlay.

## Cấu hình runtime

File cấu hình nằm tại:

```text
config/settings.json
```

Ví dụ:

```json
{
  "font_size": 13,
  "font_family": "JetBrains Mono",
  "output_mode": "translate"
}
```

Giá trị `output_mode` hợp lệ:

| Giá trị | Ý nghĩa |
|---|---|
| `ocr_only` | Chỉ hiện text OCR gốc |
| `translate` | Dịch sang tiếng Việt, lỗi thì fallback về OCR gốc |
| `both` | Hiện cả OCR gốc và bản dịch |

Có thể đổi các cấu hình này trực tiếp từ tray icon. App sẽ lưu lại vào `config/settings.json`.

## Dùng font riêng

Tạo thư mục `fonts/` ở root repo, sau đó copy font `.ttf` hoặc `.otf` vào:

```text
fonts/
  JetBrainsMono-Bold.ttf
```

Khởi động lại app, font sẽ xuất hiện trong menu tray `Font family`.

Lưu ý: `fonts/` đang nằm trong `.gitignore`, nên font cá nhân không bị commit.

## Log và history

Log theo ngày:

```text
logs/YYYY-MM-DD.log
```

OCR history gần đây:

```text
logs/ocr_history.json
```

History là file-only, chưa có UI để xem lại trong app.

## Chạy test

```bash
.venv/Scripts/python -m pytest
```

Chạy smoke OCR với ảnh mẫu trong `imgs/ocr_test_input/`:

```bash
.venv/Scripts/python tests/smoke_ocr_samples.py
```

## Build exe

Build mặc định dạng `onedir`:

```bash
.venv/Scripts/python scripts/build_exe.py
```

Build dạng `onefile`:

```bash
.venv/Scripts/python scripts/build_exe.py --mode onefile
```

Output nằm trong `dist/`.

## Cấu trúc repo

```text
core/     logic chính: hotkey, screenshot, OCR, settings, history
ui/       selection overlay và result overlay
utils/    logger
scripts/  google translate script và build helper
tests/    unit test và smoke test
imgs/     icon app và ảnh mẫu OCR
config/   settings runtime mặc định
```

## Ghi chú hiện tại

- App ưu tiên Windows vì hotkey toàn cục dùng Windows API.
- Lần chạy OCR đầu có thể chậm do PaddleOCR tải hoặc khởi tạo model.
- Dịch text phụ thuộc endpoint web của Google Translate, nên có thể lỗi nếu mạng hoặc response format thay đổi.
