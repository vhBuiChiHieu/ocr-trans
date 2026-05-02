# 🗺️ Roadmap: Windows OCR Overlay Tool
> Stack: Python 3.11 · PaddleOCR (GPU) · PyQt6 · OpenCV · mss

---

## 📋 Tổng quan dự án

| Thông tin | Chi tiết |
|---|---|
| **Mục tiêu** | Overlay dịch thuật real-time cho Windows |
| **Hotkey** | `Ctrl + Shift + Z` |
| **OCR Engine** | PaddleOCR (local, GPU-accelerated) |
| **Hardware target** | Ryzen 5 7500F + RTX 5060 Ti 16GB |
| **Ngôn ngữ** | Python 3.11+ |

---

## 🏗️ Kiến trúc tổng thể

```
[Hotkey Listener]
      │
      ▼
[Screenshot] ──► mss
      │
      ▼
[Selection UI] ──► PyQt6 fullscreen transparent overlay
      │               (vẽ rectangle / quadrilateral)
      ▼
[Preprocessor] ──► OpenCV
      │               - Upscale, denoise, contrast
      │               - Perspective transform
      ▼
[OCR Engine] ──► PaddleOCR (CUDA / RTX 5060 Ti)
      │
      ▼
[Translation] ──► API (Phase 3)
      │
      ▼
[Result Overlay] ──► PyQt6 always-on-top, click-through
```

---

## 📦 Tech Stack

| Layer | Thư viện | Mục đích |
|---|---|---|
| Hotkey | `pynput` | Capture global hotkey |
| Screenshot | `mss` | Chụp màn hình nhanh (<10ms) |
| Selection UI | `PyQt6` | Overlay trong suốt để chọn vùng |
| Preprocessing | `opencv-python` | Xử lý ảnh trước OCR |
| OCR | `paddlepaddle-gpu` + `paddleocr` | OCR local, chạy GPU |
| Translation | TBD (DeepL / Google) | Dịch EN → VI |
| Result UI | `PyQt6` | Hiển thị kết quả dịch |
| Packaging | `PyInstaller` | Build .exe |

---

## 🚀 Phase 1 — MVP Core (Tuần 1–2)

> **Mục tiêu:** Chụp → Chọn vùng → OCR → Hiển thị text gốc

### 1.1 Thiết lập môi trường

- [ ] Cài Python 3.11 (khuyến nghị dùng `pyenv` hoặc `conda`)
- [ ] Tạo virtual environment
- [ ] Cài CUDA Toolkit 12.x (tương thích RTX 5060 Ti)
- [ ] Cài cuDNN tương ứng
- [ ] Cài dependencies:

```bash
pip install paddlepaddle-gpu paddleocr
pip install PyQt6
pip install mss
pip install opencv-python
pip install pynput
pip install Pillow
```

### 1.2 Hotkey Listener

- [ ] Đăng ký global hotkey `Ctrl + Shift + Z` bằng `pynput`
- [ ] Chạy listener trong background thread (không block UI)
- [ ] Test: hotkey hoạt động khi focus ở app khác (game, browser)

```python
# Cấu trúc cơ bản
from pynput import keyboard

HOTKEY = {keyboard.Key.ctrl, keyboard.Key.shift, keyboard.KeyCode.from_char('z')}
```

### 1.3 Screenshot Module

- [ ] Chụp toàn bộ màn hình bằng `mss`
- [ ] Hỗ trợ multi-monitor (lấy đúng monitor có cursor)
- [ ] Convert sang format phù hợp cho PyQt6 và OpenCV

### 1.4 Selection UI Overlay

- [ ] Tạo PyQt6 window fullscreen, trong suốt, always-on-top
- [ ] Vẽ darkened overlay lên screenshot
- [ ] Cho phép kéo chuột để vẽ **rectangle**
- [ ] Hiển thị tọa độ và kích thước vùng chọn real-time
- [ ] Nhấn `Enter` để xác nhận, `Esc` để hủy

### 1.5 OCR Engine (PaddleOCR)

- [ ] Pre-load model khi khởi động app (tránh delay lần đầu)
- [ ] Cấu hình PaddleOCR với GPU:

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    use_angle_cls=True,
    lang='en',
    use_gpu=True,
    det_db_thresh=0.3,
    det_db_box_thresh=0.5,
    rec_batch_num=6,
    enable_mkldnn=False   # Tắt khi dùng GPU
)
```

- [ ] Crop ảnh theo vùng đã chọn
- [ ] Chạy OCR, trả về list `(text, confidence)`
- [ ] Filter kết quả theo confidence threshold (>= 0.7)

### 1.6 Result Display (Text gốc)

- [ ] Tạo PyQt6 overlay đơn giản hiển thị text OCR
- [ ] Vị trí: ngay bên dưới vùng đã chọn
- [ ] Style: nền tối bán trong suốt, chữ trắng, bo góc
- [ ] Flags: `FramelessWindowHint | WindowStaysOnTopHint | WA_TransparentForMouseEvents`
- [ ] Auto-dismiss sau 10 giây hoặc nhấn `Esc`

### ✅ Deliverable Phase 1
Bấm hotkey → kéo chọn vùng → thấy text OCR hiển thị overlay. Chưa có dịch thuật.

---

## 🎯 Phase 2 — Accuracy & UX (Tuần 3–4)

> **Mục tiêu:** OCR chính xác hơn với game text, UX mượt hơn

### 2.1 Preprocessing Pipeline (OpenCV)

- [ ] **Upscale** ảnh nếu chiều cao text < 64px (scale 2x–4x)
- [ ] **CLAHE** — tăng contrast cục bộ (tốt hơn global)
- [ ] **Bilateral filter** — giảm noise, giữ edge
- [ ] **Adaptive threshold** — xử lý background phức tạp
- [ ] Test với các loại game font: pixel font, outline text, gradient background

```python
def preprocess_game_text(img):
    h, w = img.shape[:2]
    if h < 64:
        scale = max(2, 64 // h)
        img = cv2.resize(img, (w*scale, h*scale), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    binary = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
```

### 2.2 Quadrilateral Selection

- [ ] Thêm mode chọn tứ giác (4 điểm click)
- [ ] Toggle giữa rectangle và quadrilateral mode (phím `Q`)
- [ ] Perspective transform trước khi OCR:

```python
def four_point_transform(image, pts):
    # Dùng cv2.getPerspectiveTransform + cv2.warpPerspective
    ...
```

### 2.3 White Outline Text (phổ biến trong game)

- [ ] Thử OCR cả ảnh gốc lẫn ảnh invert
- [ ] So sánh confidence score, lấy kết quả cao hơn
- [ ] Thêm option cho user chọn mode: Auto / Normal / Inverted

### 2.4 UX Improvements

- [ ] Thêm crosshair cursor khi đang chọn vùng
- [ ] Hiển thị preview preprocessing real-time (toggle bằng phím `P`)
- [ ] Confidence indicator: màu xanh/vàng/đỏ theo độ chính xác
- [ ] Copy text OCR vào clipboard tự động
- [ ] Lịch sử OCR (lưu 10 lần gần nhất, xem lại bằng tray icon)

### 2.5 System Tray

- [ ] Chạy app ẩn dưới system tray
- [ ] Menu: Enable/Disable, History, Settings, Exit
- [ ] Hiển thị icon khác nhau khi đang OCR (loading state)

### ✅ Deliverable Phase 2
OCR hoạt động tốt với game text, có preprocessing tự động, UX gọn gàng với system tray.

---

## 🌐 Phase 3 — Translation (Tuần 5–6)

> **Mục tiêu:** Tích hợp dịch EN → VI

### 3.1 Đánh giá Translation Options

| Option | Free | Chất lượng | Offline | Ghi chú |
|---|---|---|---|---|
| **DeepL Free API** | ✅ 500k ký tự/tháng | ⭐⭐⭐⭐⭐ | ❌ | **Khuyến nghị** |
| Google Translate API | ❌ (có free tier nhỏ) | ⭐⭐⭐⭐ | ❌ | Cần billing |
| `googletrans` (unofficial) | ✅ | ⭐⭐⭐ | ❌ | Không ổn định |
| LibreTranslate (local) | ✅ | ⭐⭐⭐ | ✅ | Self-host, nặng |
| OPUS-MT (local model) | ✅ | ⭐⭐⭐ | ✅ | ~300MB model |

### 3.2 Tích hợp DeepL (Khuyến nghị)

- [ ] Đăng ký DeepL Free API key
- [ ] Cài `deepl` package
- [ ] Implement async translation (không block OCR pipeline)
- [ ] Cache kết quả dịch cho text trùng lặp
- [ ] Fallback sang googletrans nếu DeepL hết quota

### 3.3 Result Overlay — Translation View

- [ ] Layout 2 phần: text gốc (xám nhạt) + bản dịch (trắng, to hơn)
- [ ] Nút copy riêng cho từng phần
- [ ] Loading spinner trong lúc đợi API
- [ ] Hiển thị nguồn dịch (DeepL / Google / etc.)

### 3.4 Settings Panel

- [ ] Ngôn ngữ nguồn: Auto-detect / English / Japanese / Chinese / Korean
- [ ] Ngôn ngữ đích: Vietnamese (mặc định)
- [ ] API key management (DeepL, Google)
- [ ] OCR confidence threshold
- [ ] Auto-dismiss delay

### ✅ Deliverable Phase 3
Pipeline hoàn chỉnh: Hotkey → Chọn vùng → OCR → Dịch → Overlay song ngữ.

---

## 📦 Phase 4 — Polish & Packaging (Tuần 7–8)

> **Mục tiêu:** App sẵn sàng dùng hàng ngày, có thể share

### 4.1 Performance Optimization

- [ ] Profile pipeline, tìm bottleneck
- [ ] Model warm-up khi startup (giảm cold start)
- [ ] Async/threading: OCR và Translation chạy song song nếu có thể
- [ ] Target: < 200ms từ lúc confirm selection đến hiện kết quả OCR

### 4.2 Error Handling & Robustness

- [ ] Xử lý trường hợp OCR không detect được text
- [ ] Timeout cho Translation API
- [ ] Log lỗi ra file (không crash app)
- [ ] Graceful degradation: nếu GPU không dùng được → fallback CPU

### 4.3 Packaging với PyInstaller

```bash
pyinstaller --onefile --windowed \
  --add-data "models;models" \
  --icon=icon.ico \
  main.py
```

- [ ] Bundle PaddleOCR models vào package
- [ ] Test .exe trên máy không có Python
- [ ] Cài đặt không cần quyền admin
- [ ] Auto-start với Windows (tùy chọn)

### 4.4 Configuration File

```toml
# config.toml
[ocr]
lang = "en"
use_gpu = true
confidence_threshold = 0.7
preprocess = "auto"   # auto | normal | inverted | pixel_font

[translation]
provider = "deepl"    # deepl | google | local
target_lang = "vi"
cache_size = 100

[ui]
overlay_opacity = 0.85
auto_dismiss_seconds = 10
font_size = 14
```

### 4.5 Testing

- [ ] Unit test preprocessing pipeline với nhiều loại game screenshot
- [ ] Test hotkey conflict detection
- [ ] Test với các resolution: 1080p, 1440p, 4K
- [ ] Test với các game phổ biến: RPG, visual novel, strategy

### ✅ Deliverable Phase 4
File `.exe` hoàn chỉnh, cài được, dùng được hàng ngày.

---

## 🗂️ Cấu trúc thư mục đề xuất

```
ocr-overlay/
├── main.py                  # Entry point, app lifecycle
├── config.toml              # User configuration
├── requirements.txt
│
├── core/
│   ├── hotkey.py            # Global hotkey listener
│   ├── screenshot.py        # mss wrapper
│   ├── preprocessor.py      # OpenCV pipeline
│   ├── ocr_engine.py        # PaddleOCR wrapper
│   └── translator.py        # Translation API wrapper
│
├── ui/
│   ├── selection_overlay.py # Vẽ vùng chọn
│   ├── result_overlay.py    # Hiển thị kết quả
│   ├── tray_icon.py         # System tray
│   └── settings_dialog.py  # Settings UI
│
├── utils/
│   ├── clipboard.py
│   ├── history.py
│   └── logger.py
│
└── assets/
    ├── icon.ico
    └── icon.png
```

---

## ⚡ Quick Start (bắt đầu ngay)

```bash
# 1. Tạo project
mkdir ocr-overlay && cd ocr-overlay
python -m venv venv
venv\Scripts\activate

# 2. Cài CUDA dependencies (làm trước tiên)
# Download CUDA 12.x tại: https://developer.nvidia.com/cuda-downloads
# Download cuDNN tại: https://developer.nvidia.com/cudnn

# 3. Cài Python packages
pip install paddlepaddle-gpu paddleocr PyQt6 mss opencv-python pynput Pillow

# 4. Verify GPU hoạt động
python -c "import paddle; print(paddle.device.get_device())"
# Kỳ vọng output: gpu:0

# 5. Test PaddleOCR load
python -c "
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_gpu=True, lang='en')
print('PaddleOCR loaded OK')
"
```

---

## ⚠️ Rủi ro & lưu ý

| Rủi ro | Khả năng | Giải pháp |
|---|---|---|
| RTX 5060 Ti driver chưa tương thích CUDA 12.x | Trung bình | Thử CUDA 11.8, hoặc dùng EasyOCR thay thế |
| PaddleOCR cold start chậm (~3s) | Chắc chắn | Pre-load khi app khởi động |
| Game fullscreen exclusive → hotkey không bắt được | Có thể | Dùng `keyboard` thay `pynput`, hoặc DirectX hook |
| Text quá nhỏ (<12px) → OCR kém | Có thể | Upscale 4x + pixel font mode |
| API dịch thuật rate limit | Thấp | Implement cache + fallback |

---

*Roadmap thiết kế theo hướng incremental — mỗi phase đều có deliverable chạy được. Bắt đầu từ Phase 1 MVP để validate toàn bộ pipeline sớm nhất có thể.*
