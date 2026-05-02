# Roadmap: Windows OCR Overlay Tool

> Stack định hướng: Python 3.11 · PaddleOCR · PyQt6 · OpenCV · mss

---

## 1. Tổng quan dự án

| Thông tin | Chi tiết |
|---|---|
| **Mục tiêu** | Tool Windows chụp vùng màn hình, OCR local, hiển thị text gốc dưới dạng overlay |
| **Hotkey** | `Ctrl + Shift + Z` |
| **OCR Engine** | PaddleOCR, chạy CPU-only để ưu tiên độ ổn định |
| **Hardware target** | Ryzen 5 7500F |
| **Ngôn ngữ** | Python 3.11+ |
| **Ưu tiên giai đoạn đầu** | OCR ổn định trước, translation làm sau |

---

## 2. MVP scope và non-goals

### MVP cần đạt

MVP của dự án là pipeline chạy được từ đầu tới cuối:

1. Bấm hotkey toàn cục
2. Chụp màn hình hiện tại
3. Chọn vùng bằng overlay
4. Crop ảnh theo vùng chọn
5. Chạy OCR local
6. Hiển thị text gốc bằng overlay nổi

### MVP chưa bao gồm

Các mục sau không phải trọng tâm của MVP ban đầu:

- Translation API
- System tray hoàn chỉnh
- History UI
- Settings panel đầy đủ
- Quadrilateral selection
- Tối ưu cho mọi game fullscreen exclusive
- Packaging `.exe` sớm
- Tối ưu cho mọi kiểu font khó ngay từ đầu

Nguyên tắc: nếu một hạng mục không giúp validate pipeline OCR sớm hơn, không đẩy vào Phase 1.

---

## 3. Kiến trúc tổng thể

```text
[Hotkey Listener]
      │
      ▼
[Screenshot Capture] ──► mss
      │
      ▼
[Selection Overlay] ──► PyQt6 fullscreen transparent overlay
      │
      ▼
[Crop + Coordinate Mapping]
      │
      ▼
[Preprocessor] ──► OpenCV
      │
      ▼
[OCR Engine] ──► PaddleOCR (CPU-only)
      │
      ▼
[Result Overlay] ──► PyQt6 always-on-top, click-through
      │
      └──► [Translation Layer] (Phase 3)
```

### App state tối thiểu

App nên có state đơn giản ngay từ đầu để tránh logic chồng chéo:

```text
idle -> selecting -> processing -> showing_result -> idle
```

State này đủ cho MVP và giúp nối hotkey, overlay, OCR, dismiss logic gọn hơn.

---

## 4. Nguyên tắc triển khai

| Nguyên tắc | Áp dụng |
|---|---|
| **OCR first** | Translation chỉ thêm sau khi OCR đã đủ ổn định |
| **Validate sớm** | Có bộ ảnh mẫu và tiêu chí pass/fail từ Phase 1 |
| **Fail mềm** | OCR fail không crash app, app giữ được hành vi ổn định trên CPU |
| **Không overbuild** | Chưa thêm tray/history/quadrilateral nếu chưa cần để validate lõi |
| **Đo được** | Mỗi phase có deliverable và tiêu chí kiểm chứng rõ |
| **Windows thực chiến** | Phải tính tới DPI scaling, multi-monitor, fullscreen app behavior |

---

## 5. Tech stack đề xuất

| Layer | Thư viện | Mục đích |
|---|---|---|
| Hotkey | `pynput` | Bắt global hotkey ở mức cơ bản |
| Screenshot | `mss` | Chụp màn hình nhanh |
| Selection UI | `PyQt6` | Overlay trong suốt để chọn vùng |
| Preprocessing | `opencv-python` | Tiền xử lý ảnh trước OCR |
| OCR | `paddleocr` + `paddlepaddle` | OCR local, chạy CPU-only |
| Image conversion | `Pillow` | Chuyển đổi format khi cần |
| Packaging | `PyInstaller` | Đóng gói `.exe` ở phase sau |

### Ghi chú kỹ thuật

- `pynput` đủ để bắt đầu, nhưng không nên coi là nghiệm đúng cho mọi game fullscreen exclusive.
- OCR engine nên preload khi app khởi động để tránh cold start quá lớn trên CPU.

### Môi trường hiện tại đã verify

Trạng thái này được ghi lại để làm mốc trước khi bắt đầu implement Phase 1:

| Hạng mục | Trạng thái hiện tại |
|---|---|
| Python | `3.11.9` |
| Virtual environment | `.venv` trong root project |
| Core packages | `PyQt6`, `mss`, `opencv-python`, `pynput`, `Pillow`, `paddleocr` đã import OK |
| Paddle runtime | `paddlepaddle==3.3.1` |
| Paddle device | `cpu` |
| OCR engine load | `PaddleOCR(lang='en')` load OK trên CPU |
| Model cache | Đã bắt đầu được tải vào cache người dùng qua PaddleX/PaddleOCR |

Ghi chú quan trọng:
- Với version hiện tại, nên dùng `predict()` thay vì bám theo các ví dụ cũ dùng `.ocr()`.
- Repo hiện chốt CPU-only vì đây là đường chạy ổn định trên bộ ảnh mẫu thực tế.
- Nếu sau này môi trường bị lệch, cần check lại Python path, `.venv`, và Paddle device trước khi debug code ứng dụng.

---

## 6. Phase 1 — OCR Core MVP

> **Mục tiêu:** Ra bản chạy được: hotkey → chọn vùng → OCR → overlay text gốc

### 6.1 Thiết lập môi trường

- [x] Cài Python 3.11
- [x] Tạo virtual environment
- [x] Cài dependencies cơ bản
- [x] Cài PaddleOCR cho runtime CPU ổn định
- [ ] Kiểm tra app chạy ổn định trên CPU với bộ ảnh mẫu thực tế đủ rộng

Trạng thái thực tế:
- Repo đang chạy bằng `.venv` trong root project.
- Runtime OCR hiện chốt CPU-only và đã verify import/load thành công trong môi trường hiện tại.
- App đã chạy được flow thật trên Windows ở mức smoke/manual, nhưng chưa có bộ ảnh mẫu rộng để chốt độ ổn định OCR.

### 6.2 App shell và lifecycle

- [x] Tạo `QApplication` và entry point tối thiểu
- [x] Tạo app controller hoặc state holder đơn giản
- [x] Khai báo state: `idle`, `selecting`, `processing`, `showing_result`
- [x] Thêm logging cơ bản ra console hoặc file

Deliverable:
- App mở được
- Có vòng đời rõ
- Không block UI khi chuyển state

### 6.3 Hotkey listener

- [x] Đăng ký global hotkey `Ctrl + Shift + Z`
- [x] Chạy listener theo cách không block UI chính
- [x] Trigger được flow mở selection overlay
- [x] Test khi app khác đang được focus ở mức manual cơ bản

Deliverable:
- Bấm hotkey từ desktop hoặc app thường thì selection overlay bật lên được
- Phase 1 chỉ cam kết hỗ trợ desktop, app thường, và app chạy windowed/borderless ở mức cơ bản
- Fullscreen exclusive game behavior nằm ngoài phạm vi MVP ban đầu

### 6.4 Screenshot capture và mapping

- [x] Chụp đúng màn hình hiện tại bằng `mss`
- [x] Xác định monitor liên quan tới vùng thao tác hoặc con trỏ
- [x] Chuẩn hóa mapping giữa screenshot pixel và tọa độ PyQt6
- [x] Test single monitor trước
- [x] Test thêm case monitor chứa con trỏ trong môi trường multi-monitor ở mức unit test/mapping logic
- [ ] Test ở DPI scale 100% và ít nhất một mức >100% bằng runtime manual đầy đủ

Phạm vi Phase 1:
- Chỉ cần support ổn định cho monitor đang chứa con trỏ hoặc monitor người dùng đang thao tác
- Full support cho mọi layout multi-monitor không phải điều kiện pass bắt buộc của MVP ban đầu

Rủi ro lớn ở bước này:
- Qt có thể dùng logical coordinates
- screenshot dùng physical pixels
- monitor phụ có thể có tọa độ âm

Deliverable:
- Vùng người dùng chọn khớp đúng vùng crop OCR trên case single monitor
- Với multi-monitor, ít nhất case monitor chứa con trỏ hoạt động đúng

### 6.5 Selection overlay

- [x] Tạo fullscreen transparent overlay
- [x] Vẽ nền tối mờ trên screenshot
- [x] Kéo chuột để chọn **rectangle**
- [x] Hỗ trợ click 2 góc để xác định **rectangle**
- [x] `Esc` để hủy
- [x] Tự xác nhận khi thả chuột sau drag hoặc khi click góc thứ hai
- [x] Bỏ UI hiển thị toạ độ/kích thước realtime

Phạm vi Phase 1:
- Chỉ cần rectangle
- Chưa cần quadrilateral
- Chưa cần preview preprocessing realtime

Deliverable:
- Người dùng nhìn thấy screenshot nền và chọn được vùng ổn định

### 6.6 OCR engine

- [x] Preload OCR engine trên CPU khi app khởi động
- [x] Nhận ảnh crop và trả ra text + confidence
- [x] Log rõ runtime CPU đang hoạt động
- [x] Lọc kết quả theo confidence threshold ban đầu, ví dụ `>= 0.7`

Ví dụ cấu hình khởi đầu:

```python
from paddleocr import PaddleOCR

ocr = PaddleOCR(
    lang='en',
    device='cpu',
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    enable_mkldnn=False,
    cpu_threads=1,
)
```

Ghi chú:
- Đây là cấu hình khởi điểm để benchmark, không phải cấu hình chốt cuối.
- CPU là runtime chuẩn hiện tại của repo; benchmark và kiểm chứng nên bám theo đường chạy này.

Deliverable:
- OCR trả được text từ ảnh crop thật trong app

```bash
pip install paddleocr
pip install PyQt6
pip install mss
pip install opencv-python
pip install pynput
pip install Pillow
```

CPU setup nên được giữ đơn giản và ổn định ở giai đoạn đầu, không phụ thuộc driver/CUDA/CUDNN.

### 6.7 Result overlay

- [x] Hiển thị text OCR bằng PyQt6 overlay nổi
- [x] Mặc định đặt gần vùng đã chọn nhưng không che lên vùng gốc nếu có thể
- [x] Nếu sát mép màn hình thì tự reposition
- [x] Style tối giản: nền tối bán trong suốt, chữ sáng, dễ đọc
- [x] Phase 1 mặc định giữ overlay tới khi người dùng nhấn `Esc` hoặc bắt đầu lần capture kế tiếp
- [x] Log text OCR sau khi nhận được kết quả thành công

Deliverable:
- Sau khi OCR xong, text gốc hiển thị ổn định bằng overlay
- Hành vi đóng overlay đơn giản, dễ đoán, không phụ thuộc timeout sớm

### 6.8 Verification cho Phase 1

Chuẩn bị bộ ảnh mẫu nhỏ để kiểm tra ngay từ đầu:

- [ ] Text UI rõ nét nền đơn giản
- [ ] Text game có outline trắng
- [ ] Text nhỏ
- [ ] Text trên nền phức tạp vừa phải
- [ ] Ảnh chụp từ app thực tế hoặc game nhẹ

Trạng thái verify hiện tại:
- [x] Unit test cho coordinate mapping
- [x] Unit test cho preprocessor
- [x] Unit test cho OCR engine
- [x] Unit test cho controller flow hotkey → select → OCR → result overlay
- [x] Unit test cho interaction của selection overlay
- [x] Smoke test manual trên app thật để xác nhận flow chọn vùng hiện hoạt động và artifact UI lớn đã được sửa
- [ ] Chưa có checklist manual đầy đủ cho nhiều nhóm ảnh / nhiều mức DPI / nhiều app thực tế

Tiêu chí hoàn thành Phase 1:

- [x] Bấm hotkey mở được selection overlay
- [x] Chọn vùng xong OCR chạy được trên ảnh thật ở mức smoke test
- [x] Overlay hiện được text gốc
- [x] App không crash nếu OCR fail trên CPU runtime
- [ ] Vùng crop khớp vùng chọn ở các case DPI đã test đầy đủ

### ✅ Deliverable Phase 1

Trạng thái hiện tại gần hoàn tất Phase 1 ở mức code và smoke test manual: hotkey → chọn vùng → OCR → result overlay đã chạy được trên Windows, chưa có translation.

### 6.9 Ghi chú tiến độ thực tế sau vòng sửa UI

Các thay đổi đã có trong codebase hiện tại:
- Selection overlay hiện hỗ trợ cả kéo-thả và click 2 góc để tạo vùng chữ nhật.
- Xác nhận vùng chọn diễn ra ngay khi thả chuột sau drag hoặc khi click góc thứ hai; không còn bắt buộc nhấn `Enter`.
- Đã bỏ hộp hiển thị toạ độ/kích thước realtime để UI gọn hơn.
- Đã sửa lỗi render tạo khối xám/đen lớn nối vào vùng chọn do tính sai `QRect` cho metrics box.
- OCR hoàn tất sẽ log `display_text` ra logger khi có kết quả hiển thị được.

Kết luận thực tế:
- Phase 1 không còn ở trạng thái "chưa làm xong core flow".
- Phase 1 đang ở trạng thái "core flow đã xong, cần mở rộng manual verification nếu muốn chốt hoàn tất theo roadmap ban đầu".
- Các hạng mục tiếp theo nên ưu tiên sang Phase 2 nếu không cần thêm vòng verify DPI/sample set trước.

### ✅ Deliverable Phase 1

Có bản OCR MVP dùng được để validate pipeline end-to-end trên Windows. Chưa có translation.

> Ghi chú: nếu dùng chuẩn roadmap nghiêm ngặt, Phase 1 chưa thể coi là đóng hoàn toàn cho tới khi có manual verification rộng hơn theo sample set và DPI cases.

---

## 7. Phase 2 — Accuracy + UX tối thiểu

> **Mục tiêu:** Tăng độ chính xác OCR và cải thiện UX vừa đủ để dùng thường xuyên hơn

### 7.1 Preprocessing pipeline

Không nên mặc định bật mọi filter cho mọi ảnh. Nên đi theo hướng preset hoặc strategy.

- [ ] Tạo baseline: ảnh gốc hoặc grayscale nhẹ
- [ ] Tạo preset cho text nhỏ: upscale trước OCR
- [ ] Tạo preset cho outlined text: contrast + threshold phù hợp
- [ ] So sánh kết quả theo confidence hoặc sample accuracy
- [ ] Chỉ giữ các bước thật sự giúp tăng chất lượng

Ví dụ pipeline thử nghiệm:

```python
def preprocess_game_text(img):
    h, w = img.shape[:2]
    if h < 64:
        scale = max(2, 64 // h)
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
```

### 7.2 White outline / inverted text handling

- [ ] Thử OCR trên ảnh gốc và ảnh invert
- [ ] So sánh confidence hoặc chất lượng thực tế
- [ ] Tạo mode đơn giản: `auto`, `normal`, `inverted`

### 7.3 UX cải thiện tối thiểu

- [ ] Crosshair cursor khi chọn vùng
- [ ] Copy text OCR vào clipboard tự động hoặc bằng shortcut đơn giản
- [ ] Tinh chỉnh vị trí result overlay cho dễ đọc
- [ ] Indicator đơn giản cho confidence nếu thực sự hữu ích

### 7.4 Kiểm chứng lại độ chính xác

- [ ] So sánh kết quả giữa ảnh gốc và ảnh preprocess
- [ ] Test thêm với vài kiểu font game phổ biến
- [ ] Ghi lại preset nào hợp với từng nhóm ảnh
- [ ] Dùng bộ ảnh mẫu ít nhất 10 ảnh để so baseline với từng preset chính

Tiêu chí hoàn thành Phase 2:

- Dùng rubric `usable / partially usable / unusable` để chấm cùng một bộ ảnh mẫu ít nhất 10 ảnh
- Số ảnh đạt mức `usable` phải tăng so với baseline
- Tổng số ảnh đạt `usable + partially usable` nên đạt ít nhất 8/10 trước khi coi preset hiện tại là đủ tốt để dùng tiếp
- UX đủ mượt để dùng lặp lại nhiều lần trên flow cơ bản: chọn vùng, xem kết quả, capture lại
- Không thêm complexity lớn ngoài phạm vi OCR-first

Không cần tối ưu theo độ chính xác tuyệt đối ở Phase 2. Mục tiêu là cải thiện đáng đo trên sample set thực tế bằng cùng một rubric.

### ✅ Deliverable Phase 2

OCR đủ ổn định cho nhiều trường hợp text game/app phổ biến, UX gọn hơn nhưng vẫn tập trung vào lõi.

---

## 8. Phase 3 — Translation

> **Mục tiêu:** Thêm dịch sau khi OCR đã đủ ổn định

### 8.1 Nguyên tắc

Translation không được làm rối hoặc làm chậm việc xác thực OCR core. Chỉ bắt đầu phase này khi:

- OCR pipeline đã ổn định
- Crop và coordinate mapping đã đáng tin cậy
- Có bộ ảnh mẫu chứng minh OCR đủ tốt để dịch có ý nghĩa

### 8.2 Hướng triển khai translation

Translation chỉ nên bắt đầu sau khi OCR core đã được chứng minh đủ ổn định trên sample set thực tế.

- [ ] Chọn một provider chính sau khi đánh giá nhu cầu chất lượng, chi phí, và độ ổn định
- [ ] Gọi translation bất đồng bộ, không block UI
- [ ] Giữ thiết kế phần dịch tách rời khỏi OCR core để dễ bật/tắt
- [ ] Nếu provider lỗi hoặc hết quota thì báo mềm, không crash app

### 8.3 Result overlay song ngữ

- [ ] Hiển thị text gốc và bản dịch tách rõ
- [ ] Có trạng thái loading trong lúc chờ dịch
- [ ] Chỉ thêm thao tác copy/phím tắt nếu thật sự cần sau khi flow OCR đã ổn

Tiêu chí hoàn thành Phase 3:

- OCR → translation → overlay song ngữ chạy được
- Translation không làm hỏng trải nghiệm OCR đã có
- Quyết định provider dựa trên kết quả thử nghiệm thật, không chốt từ roadmap này

### ✅ Deliverable Phase 3

Pipeline hoàn chỉnh: hotkey → chọn vùng → OCR → dịch → overlay song ngữ.

Translation vẫn là phase phụ thuộc vào chất lượng OCR. Nếu OCR chưa đủ ổn, không nên đẩy nhanh phase này.

---

## 9. Phase 4 — Polish + Packaging

> **Mục tiêu:** Tối ưu để dùng hàng ngày và có thể chia sẻ

### 6.7 Result overlay

- [x] Hiển thị text OCR bằng PyQt6 overlay nổi
- [x] Mặc định đặt gần vùng đã chọn nhưng không che lên vùng gốc nếu có thể
- [x] Nếu sát mép màn hình thì tự reposition
- [x] Style tối giản: nền tối bán trong suốt, chữ sáng, dễ đọc
- [x] Phase 1 mặc định giữ overlay tới khi người dùng nhấn `Esc` hoặc bắt đầu lần capture kế tiếp
- [x] Log text OCR sau khi nhận được kết quả thành công

Deliverable:
- Sau khi OCR xong, text gốc hiển thị ổn định bằng overlay
- Hành vi đóng overlay đơn giản, dễ đoán, không phụ thuộc timeout sớm

### 6.8 Verification cho Phase 1

Chuẩn bị bộ ảnh mẫu nhỏ để kiểm tra ngay từ đầu:

- [ ] Text UI rõ nét nền đơn giản
- [ ] Text game có outline trắng
- [ ] Text nhỏ
- [ ] Text trên nền phức tạp vừa phải
- [ ] Ảnh chụp từ app thực tế hoặc game nhẹ

Trạng thái verify hiện tại:
- [x] Unit test cho coordinate mapping
- [x] Unit test cho preprocessor
- [x] Unit test cho OCR engine
- [x] Unit test cho controller flow hotkey → select → OCR → result overlay
- [x] Unit test cho interaction của selection overlay
- [x] Smoke test manual trên app thật để xác nhận flow chọn vùng hiện hoạt động và artifact UI lớn đã được sửa
- [ ] Chưa có checklist manual đầy đủ cho nhiều nhóm ảnh / nhiều mức DPI / nhiều app thực tế

Tiêu chí hoàn thành Phase 1:

- [x] Bấm hotkey mở được selection overlay
- [x] Chọn vùng xong OCR chạy được trên ảnh thật ở mức smoke test
- [x] Overlay hiện được text gốc
- [x] App không crash nếu OCR fail trên CPU runtime
- [ ] Vùng crop khớp vùng chọn ở các case DPI đã test đầy đủ

### ✅ Deliverable Phase 1

Trạng thái hiện tại gần hoàn tất Phase 1 ở mức code và smoke test manual: hotkey → chọn vùng → OCR → result overlay đã chạy được trên Windows, chưa có translation.

### 6.9 Ghi chú tiến độ thực tế sau vòng sửa UI

Các thay đổi đã có trong codebase hiện tại:
- Selection overlay hiện hỗ trợ cả kéo-thả và click 2 góc để tạo vùng chữ nhật.
- Xác nhận vùng chọn diễn ra ngay khi thả chuột sau drag hoặc khi click góc thứ hai; không còn bắt buộc nhấn `Enter`.
- Đã bỏ hộp hiển thị toạ độ/kích thước realtime để UI gọn hơn.
- Đã sửa lỗi render tạo khối xám/đen lớn nối vào vùng chọn do tính sai `QRect` cho metrics box.
- OCR hoàn tất sẽ log `display_text` ra logger khi có kết quả hiển thị được.

Kết luận thực tế:
- Phase 1 không còn ở trạng thái "chưa làm xong core flow".
- Phase 1 đang ở trạng thái "core flow đã xong, cần mở rộng manual verification nếu muốn chốt hoàn tất theo roadmap ban đầu".
- Các hạng mục tiếp theo nên ưu tiên sang Phase 2 nếu không cần thêm vòng verify DPI/sample set trước.

### ✅ Deliverable Phase 1

Có bản OCR MVP dùng được để validate pipeline end-to-end trên Windows. Chưa có translation.

> Ghi chú: nếu dùng chuẩn roadmap nghiêm ngặt, Phase 1 chưa thể coi là đóng hoàn toàn cho tới khi có manual verification rộng hơn theo sample set và DPI cases.

---

## 7. Phase 2 — Accuracy + UX tối thiểu

> **Mục tiêu:** Tăng độ chính xác OCR và cải thiện UX vừa đủ để dùng thường xuyên hơn

### 7.1 Preprocessing pipeline

Không nên mặc định bật mọi filter cho mọi ảnh. Nên đi theo hướng preset hoặc strategy.

- [ ] Tạo baseline: ảnh gốc hoặc grayscale nhẹ
- [ ] Tạo preset cho text nhỏ: upscale trước OCR
- [ ] Tạo preset cho outlined text: contrast + threshold phù hợp
- [ ] So sánh kết quả theo confidence hoặc sample accuracy
- [ ] Chỉ giữ các bước thật sự giúp tăng chất lượng

Ví dụ pipeline thử nghiệm:

```python
def preprocess_game_text(img):
    h, w = img.shape[:2]
    if h < 64:
        scale = max(2, 64 // h)
        img = cv2.resize(img, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    binary = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11,
        2,
    )
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
```

### 7.2 White outline / inverted text handling

- [ ] Thử OCR trên ảnh gốc và ảnh invert
- [ ] So sánh confidence hoặc chất lượng thực tế
- [ ] Tạo mode đơn giản: `auto`, `normal`, `inverted`

### 7.3 UX cải thiện tối thiểu

- [ ] Crosshair cursor khi chọn vùng
- [ ] Copy text OCR vào clipboard tự động hoặc bằng shortcut đơn giản
- [ ] Tinh chỉnh vị trí result overlay cho dễ đọc
- [ ] Indicator đơn giản cho confidence nếu thực sự hữu ích

### 7.4 Kiểm chứng lại độ chính xác

- [ ] So sánh kết quả giữa ảnh gốc và ảnh preprocess
- [ ] Test thêm với vài kiểu font game phổ biến
- [ ] Ghi lại preset nào hợp với từng nhóm ảnh
- [ ] Dùng bộ ảnh mẫu ít nhất 10 ảnh để so baseline với từng preset chính

Tiêu chí hoàn thành Phase 2:

- Dùng rubric `usable / partially usable / unusable` để chấm cùng một bộ ảnh mẫu ít nhất 10 ảnh
- Số ảnh đạt mức `usable` phải tăng so với baseline
- Tổng số ảnh đạt `usable + partially usable` nên đạt ít nhất 8/10 trước khi coi preset hiện tại là đủ tốt để dùng tiếp
- UX đủ mượt để dùng lặp lại nhiều lần trên flow cơ bản: chọn vùng, xem kết quả, capture lại
- Không thêm complexity lớn ngoài phạm vi OCR-first

Không cần tối ưu theo độ chính xác tuyệt đối ở Phase 2. Mục tiêu là cải thiện đáng đo trên sample set thực tế bằng cùng một rubric.

### ✅ Deliverable Phase 2

OCR đủ ổn định cho nhiều trường hợp text game/app phổ biến, UX gọn hơn nhưng vẫn tập trung vào lõi.

---

## 8. Phase 3 — Translation

> **Mục tiêu:** Thêm dịch sau khi OCR đã đủ ổn định

### 8.1 Nguyên tắc

Translation không được làm rối hoặc làm chậm việc xác thực OCR core. Chỉ bắt đầu phase này khi:

- OCR pipeline đã ổn định
- Crop và coordinate mapping đã đáng tin cậy
- Có bộ ảnh mẫu chứng minh OCR đủ tốt để dịch có ý nghĩa

### 8.2 Hướng triển khai translation

Translation chỉ nên bắt đầu sau khi OCR core đã được chứng minh đủ ổn định trên sample set thực tế.

- [ ] Chọn một provider chính sau khi đánh giá nhu cầu chất lượng, chi phí, và độ ổn định
- [ ] Gọi translation bất đồng bộ, không block UI
- [ ] Giữ thiết kế phần dịch tách rời khỏi OCR core để dễ bật/tắt
- [ ] Nếu provider lỗi hoặc hết quota thì báo mềm, không crash app

### 8.3 Result overlay song ngữ

- [ ] Hiển thị text gốc và bản dịch tách rõ
- [ ] Có trạng thái loading trong lúc chờ dịch
- [ ] Chỉ thêm thao tác copy/phím tắt nếu thật sự cần sau khi flow OCR đã ổn

Tiêu chí hoàn thành Phase 3:

- OCR → translation → overlay song ngữ chạy được
- Translation không làm hỏng trải nghiệm OCR đã có
- Quyết định provider dựa trên kết quả thử nghiệm thật, không chốt từ roadmap này

### ✅ Deliverable Phase 3

Pipeline hoàn chỉnh: hotkey → chọn vùng → OCR → dịch → overlay song ngữ.

Translation vẫn là phase phụ thuộc vào chất lượng OCR. Nếu OCR chưa đủ ổn, không nên đẩy nhanh phase này.

---

## 9. Phase 4 — Polish + Packaging

> **Mục tiêu:** Tối ưu để dùng hàng ngày và có thể chia sẻ

### 9.1 Performance optimization

- [ ] Warm-up OCR khi startup
- [ ] Đo bottleneck từng bước
- [ ] Tối ưu preprocess nếu quá nặng
- [ ] Xem xét threading hoặc task queue nếu cần

Performance nên đo sau khi đã có baseline thật trên phần cứng mục tiêu.

Baseline cần tách ít nhất:
- CPU-only path
- Ảnh dễ đọc vs ảnh khó hơn hoặc text nhỏ
- Ảnh dễ đọc
- Ảnh khó hơn hoặc text nhỏ

Budget dưới đây chỉ là mốc tham chiếu để quan sát bottleneck, không phải cam kết cứng ngay từ đầu:

| Bước | Mốc tham chiếu ban đầu |
|---|---|
| Screenshot | khoảng `< 15ms` |
| Crop + mapping | khoảng `< 10ms` |
| Preprocess | khoảng `< 30ms` |
| OCR | phụ thuộc mạnh vào loại ảnh và độ khó text trên CPU runtime |
| Overlay render | khoảng `< 20ms` |

Mục tiêu giai đoạn đầu:
- đo được latency end-to-end trên máy mục tiêu
- tách rõ số liệu theo nhóm ảnh dễ/khó trên CPU runtime
- chỉ đặt hard target sau khi đã có baseline thực tế

Có thể dùng mốc `< 200ms` end-to-end như target tối ưu về sau nếu CPU runtime và chất lượng OCR vẫn giữ ổn định; không coi đây là điều kiện pass sớm cho toàn roadmap.

### 9.2 Robustness

- [ ] Xử lý case không detect được text
- [ ] Log lỗi đủ để debug
- [ ] Không crash khi API dịch lỗi
- [ ] Kiểm tra CPU runtime hoạt động ổn định khi đóng gói

### 9.3 Packaging

- [ ] Build bằng PyInstaller
- [ ] Bundle model/dependency cần thiết
- [ ] Test trên máy không có Python dev environment
- [ ] Kiểm tra app khởi động không cần quyền admin nếu có thể

Ví dụ lệnh build sau này:

```bash
pyinstaller --onefile --windowed \
  --icon=icon.ico \
  main.py
```

### 9.4 Optional features sau khi lõi ổn

- [ ] System tray
- [ ] History
- [ ] Settings panel
- [ ] Auto-start cùng Windows
- [ ] Quadrilateral selection nếu thật sự cần cho text nghiêng

### ✅ Deliverable Phase 4

Bản app đủ ổn định để dùng hàng ngày, có thể build và chia sẻ.

---

## 10. Rủi ro kỹ thuật cần theo dõi sớm

| Rủi ro | Mức độ | Ghi chú |
|---|---|---|
| DPI scaling làm lệch vùng chọn và vùng crop | Cao | Rủi ro quan trọng ở Windows multi-monitor |
| Paddle runtime trên CPU chạy chậm hoặc lệch giữa môi trường dev và packaged app | Cao | Phải kiểm tra smoke test ảnh mẫu sớm và lặp lại sau khi đóng gói |
| `pynput` không bắt được hotkey ở vài game fullscreen exclusive | Cao | Không nên coi là bug blocker cho MVP app thường |
| Text quá nhỏ hoặc quá nhiễu | Cao | Cần preset preprocess và sample-based validation |
| Overlay che mất vùng text gốc | Vừa | Cần reposition logic |
| Translation rate limit / quota | Vừa | Chỉ xuất hiện ở phase sau |
| Anti-cheat hoặc game policy không thích overlay/capture | Vừa | Nên test kỹ với app thường trước, game sau |

---

## 11. Cấu trúc thư mục đề xuất

### 11.1 Cấu trúc tối thiểu cho MVP OCR-first

```text
ocr-overlay/
├── main.py
├── requirements.txt
│
├── core/
│   ├── app_controller.py
│   ├── hotkey.py
│   ├── screenshot.py
│   ├── coordinate_mapper.py
│   ├── preprocessor.py
│   └── ocr_engine.py
│
├── ui/
│   ├── selection_overlay.py
│   └── result_overlay.py
│
├── utils/
│   └── logger.py
│
└── assets/
    ├── icon.ico
    └── icon.png
```

### 11.2 Module có thể thêm ở phase sau

```text
ocr-overlay/
├── config.toml
├── core/
│   └── translator.py
├── ui/
│   ├── tray_icon.py
│   └── settings_dialog.py
└── utils/
    ├── clipboard.py
    └── history.py
```

Ghi chú:
- Chỉ scaffold module khi phase tương ứng thực sự bắt đầu.
- `coordinate_mapper.py` đáng tách riêng vì đây là chỗ dễ phát sinh lỗi khó debug.
- `clipboard.py` có thể đưa sớm hơn nếu Phase 2 xác nhận đây là UX cải thiện thật sự cần thiết.

---

## 12. Quick start định hướng

```bash
python -m venv venv
source venv/Scripts/activate
pip install paddleocr PyQt6 mss opencv-python pynput Pillow
```

Kiểm tra tối thiểu:

```bash
python -c "from paddleocr import PaddleOCR; print('PaddleOCR import OK')"
```

Repo hiện chốt CPU-only; nếu sau này muốn khôi phục GPU thì cần mở scope riêng và kiểm chứng lại từ đầu trên bộ ảnh mẫu thực tế.

---

## 13. Success criteria tổng thể

| Phase | Done khi nào |
|---|---|
| **Phase 1** | Có OCR MVP chạy end-to-end trên ảnh thật |
| **Phase 2** | OCR chính xác hơn rõ rệt, UX đủ dùng lặp lại |
| **Phase 3** | Có dịch mà không phá trải nghiệm OCR |
| **Phase 4** | App đủ ổn định để dùng hàng ngày và đóng gói |

---

## 14. Kết luận

Roadmap này ưu tiên một việc trước: chứng minh pipeline OCR local trên Windows hoạt động ổn định trong thực tế. Khi lõi đã đúng và đủ nhanh, translation và phần polish mới đáng đầu tư tiếp.
