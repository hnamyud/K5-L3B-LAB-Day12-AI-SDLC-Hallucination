# Ma trận kiểm chứng Phase 4 · Test Contract v1.3 & Release v1.0.0

> Chủ sở hữu file: **TV5 (`bachvx1709`) — QA Lead / Accessibility / Release Verification**
> Tham chiếu checklist nghiệm thu: [docs/phan-cong.md](../phan-cong.md) (mục Checklist nghiệm thu chung Phase 4, dòng 127–135).

---

## 1. Ma trận Tiêu chí nghiệm thu (AC-P4-01 đến AC-P4-06)

| Mã AC | Phụ trách | Nội dung tiêu chí | Cách kiểm chứng | Bằng chứng & Tài liệu liên quan | Trạng thái |
|---|---|---|---|---|---|
| **AC-P4-01** | TV1 + TV3 | `contract_version: "1.3"`, khai đúng `bench_cmd` và `soak_cmd`; `<bench_cmd> --seed 42 --duration 30 --out bench.json` chạy cảnh sáng lõi `1280×720` và tạo đúng 5 trường JSON (`avg_fps`, `p1_low_fps`, `frames`, `measured_s`, `load_ms`). | TV1 & TV3 chạy benchmark script và đối chiếu mốc `avg_fps >= 60`, `p1_low_fps >= 30`, `load_ms <= 10000`. | `docs/proof/phase-4/bench.json` | **Đang hoàn thiện / Chờ TV1 & TV3 ghép** |
| **AC-P4-02** | TV2 | `<soak_cmd> --seed 7 --days 10 --out soak.json` chạy đủ 10 Ngày lặp D1–D5, `days_completed == 10`, `crashes == 0`, tất định ở các trường gameplay. | TV2 chạy soak test mô phỏng 10 ngày dài hạn không rò rỉ bộ nhớ hay crash. | `docs/proof/phase-4/soak.json` | **Đang hoàn thiện / Chờ TV2 ghép** |
| **AC-P4-03** | **TV5** | Cả 3 cảnh báo (thủy quái gần, oxy sắp hết, khách sắp giận) có chữ/biểu tượng rõ ràng và đã chơi thử ở chế độ tương phản cao (có ảnh bằng chứng). | Kiểm chứng trên Web Client `chonoi/web/index.html`: Toggle Tương phản cao qua nút Menu, Pause, Settings và phím `H`. Kích hoạt 3 cảnh báo trực quan chữ + icon: `🐊 ⚠ THỦY QUÁI!`, `🫁 ⚠ HẾT HƠI!`, `😠 ⚠ KHÁCH SẮP GIẬN!`. | [tv5-high-contrast.md](../proof/phase-4/tv5-high-contrast.md) · 6 ảnh bằng chứng [ui/](../proof/phase-4/ui/) | **ĐẠT** |
| **AC-P4-04** | TV4 + TV1 | Clone sạch chạy bản có giao diện trong ≤ 3 lệnh theo `README.md`; `CHANGELOG.md`, `CREDITS.md`, `LICENSE`, Release notes và gói đóng gói đầy đủ trên GitHub Release `v1.0.0`. | Kiểm tra đóng gói độc lập, chạy thử lệnh `git clone`, `cd`, `python3 -m chonoi.live --mode day`. | `README.md`, `CHANGELOG.md`, `CREDITS.md`, `LICENSE` | **Đang hoàn thiện / TV4 + TV1 chuẩn bị** |
| **AC-P4-05** | **TV5** + TV1 | Regression P1–P3 còn hiệu lực đạt; `docs/verification/phase-4.md`, `docs/clarify.md`, `docs/ai-usage-log.md` cập nhật và khớp commit gắn tag `phase-4` / Release `v1.0.0`. | Chạy toàn bộ 124 unit tests hồi quy P1–P3 qua `python3 -m unittest discover -s tests -v`. | [test_suite.log](../proof/phase-4/test_suite.log) (124/124 tests OK) · [ai-usage-log.md](../ai-usage-log.md) | **ĐẠT (TV5 hoàn thành phần mình)** |
| **AC-P4-06** | TV4 + Cả nhóm | `docs/retro.md` đã rà lại hành động P2 và nêu 1 lỗi AI + cách xác minh; đủ 5 file `docs/members/<handle>.md` (≤ 200 từ/người) và bằng chứng đóng góp trên repo chung. | Kiểm tra 5 file phản tư cá nhân, từ ngữ ≤ 200 từ, dẫn commit thật, cập nhật retro Phase 4. | [bachvx1709.md](../members/bachvx1709.md) · [retro.md](../retro.md) | **ĐẠT (TV5 hoàn thành phần mình)** |

---

## 2. Chi tiết Nghiệm thu phần TV5 (AC-P4-03 & AC-P4-05)

### 2.1. Chế độ Tương phản cao (High Contrast)
- **CSS**: Áp dụng class `.high-contrast` cho `body` với bảng màu chuẩn trợ năng WCAG: Nền đen tuyệt đối (`#000000`), chữ trắng (`#ffffff`), viền vàng chanh (`#ffff00`), điểm nhấn xanh/đỏ/tím có độ sáng cao.
- **Điều khiển**:
  - Phím tắt `H` hoạt động toàn cục.
  - Nút bấm trực tiếp tại Menu chính và màn hình Tạm dừng (Pause).
  - Checkbox cài đặt trong modal Cài đặt (Settings).
  - Tự động lưu và phục hồi qua `localStorage.setItem("chonoi_high_contrast", ...)`.

### 2.2. Ba Cảnh báo trực quan bằng CHỮ + BIỂU TƯỢNG
- **Thủy quái gần / đuổi bắt**: Hiển thị `🐊 ⚠ THỦY QUÁI!` trên banner HUD kèm hiệu ứng viền màn hình tím neon `vignette.on`.
- **Oxy sắp cạn / Hết hơi**: Hiển thị `🫁 ⚠ OXY SẮP HẾT!` (dưới 25%) và `🫁 ⚠ HẾT HƠI!` (khi cạn oxy về 0), nhấp nháy đỏ rực rỡ.
- **Khách sắp giận**: Hiển thị `😠 ⚠ KHÁCH SẮP GIẬN! (Tên + Bàn)` trên banner HUD trung tâm và nhãn cảnh báo trực tiếp trên đầu bàn khách khi độ kiên nhẫn dưới 25%.

### 2.3. Bằng chứng trực quan (Screenshots)
Toàn bộ ảnh chụp thực tế phân giải 1280×720 đã được lưu tại [docs/proof/phase-4/ui/](../proof/phase-4/ui/):
- `01-menu-high-contrast.png`: Menu tương phản cao.
- `02-settings-contrast.png`: Modal cài đặt trợ năng.
- `03-alert-monster.png`: Cảnh báo thủy quái `🐊 ⚠ THỦY QUÁI!`.
- `04-alert-oxy.png`: Cảnh báo oxy `🫁 ⚠ HẾT HƠI!`.
- `05-alert-angry-customer.png`: Cảnh báo khách giận `😠 ⚠ KHÁCH SẮP GIẬN!`.
- `06-pause-contrast.png`: Màn hình tạm dừng tương phản cao.

### 2.4. Kiểm thử Hồi quy (Regression Test)
- Kết quả chạy `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`:
  - `Ran 124 tests in 7.894s`
  - `OK` (100% tests pass, chi tiết tại [test_suite.log](../proof/phase-4/test_suite.log)).
- Không gây ảnh hưởng hay vi phạm tính tất định của headless simulation.
