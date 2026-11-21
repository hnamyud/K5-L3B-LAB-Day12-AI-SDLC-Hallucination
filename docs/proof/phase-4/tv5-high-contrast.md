# TV5 · Chế độ Tương phản cao & 3 Cảnh báo trực quan (Phase 4, AC-P4-03)

Thành viên: **Vũ Xuân Bách (`bachvx1709`)** — Vai trò: **Client / Accessibility / QA Lead**

---

## 1. Mục tiêu & Yêu cầu AC-P4-03

> **AC-P4-03 · TV5**: *"Cả 3 cảnh báo (thủy quái gần, oxy sắp hết, khách sắp giận) có chữ/biểu tượng rõ ràng và đã chơi thử ở chế độ tương phản cao (có ảnh bằng chứng)."*

Để đáp ứng tiêu chuẩn Accessibility (Trợ năng WCAG AAA) cho game web chạy trên sông nước miền Tây:
1. **Chế độ Tương phản cao (High Contrast Mode)**:
   - Nền đen sâu (`#000000`), viền và văn bản màu vàng neon (`#ffff00`), chữ trắng nổi bật (`#ffffff`), điểm nhấn xanh lá (`#00ff66`), tím sáng (`#ff00ff`) và đỏ cảnh báo (`#ff0033`).
   - Tăng độ tương phản cho tất cả thẻ card, panel, button, dialog, HUD thanh máu/oxy và thanh độ tươi.
   - Hỗ trợ bật/tắt linh hoạt qua:
     - Nút bấm trực tiếp tại Menu chính (`#b-contrast-menu`)
     - Phím tắt nhanh **`H`** (High Contrast) ở mọi thời điểm trong game
     - Nút toggle trong màn hình Tạm dừng (`#b-contrast-toggle`)
     - Checkbox trong màn hình Cài đặt (`#chk-contrast`)
     - Lưu trạng thái vào `localStorage` (`chonoi_high_contrast`) để giữ cài đặt qua các phiên chơi.

2. **3 Cảnh báo trực quan bằng CHỮ + BIỂU TƯỢNG (Không phụ thuộc màu sắc đơn thuần)**:
   - **Thủy quái đến gần / đuổi bắt**: `🐊 ⚠ THỦY QUÁI!` hiển thị chữ hoa đậm + icon cá sấu + biển báo tam giác, kết hợp hiệu ứng viền sáng vignette tím neon bao quanh màn hình khi quái vật trong tầm phát hiện (`detect_radius`).
   - **Oxy sắp cạn / Hết hơi**: `🫁 ⚠ OXY SẮP HẾT!` khi oxy dưới 25% và `🫁 ⚠ HẾT HƠI!` khi oxy về 0, hiển thị chữ + icon phổi cảnh báo nhấp nháy đỏ nổi bật.
   - **Khách sắp giận (Ca quán)**: `😠 ⚠ KHÁCH SẮP GIẬN! (Tên khách + Bàn)` xuất hiện trên banner HUD trung tâm và nhãn cảnh báo trên đầu khách khi thời gian chờ còn dưới 25% lòng kiên nhẫn (`patience < 25%`).

---

## 2. Bằng chứng ảnh chụp thực tế (1280×720)

Thư mục lưu ảnh: `docs/proof/phase-4/ui/`

| STT | Tên ảnh | Nội dung hiển thị |
|---|---|---|
| 01 | [01-menu-high-contrast.png](ui/01-menu-high-contrast.png) | Menu chính ở chế độ Tương phản cao: nút toggle và hướng dẫn phím `H`. |
| 02 | [02-settings-contrast.png](ui/02-settings-contrast.png) | Màn hình Cài đặt: checkbox Trợ năng & Chế độ tương phản cao. |
| 03 | [03-alert-monster.png](ui/03-alert-monster.png) | Cảnh báo Thủy quái: Biểu tượng `🐊 ⚠ THỦY QUÁI!` + viền tím neon đậm nét. |
| 04 | [04-alert-oxy.png](ui/04-alert-oxy.png) | Cảnh báo Oxy: Biểu tượng `🫁 ⚠ HẾT HƠI!` / `🫁 ⚠ OXY SẮP HẾT!`. |
| 05 | [05-alert-angry-customer.png](ui/05-alert-angry-customer.png) | Cảnh báo Khách sắp giận: Banner `😠 ⚠ KHÁCH SẮP GIẬN!` + nhãn bàn khách. |
| 06 | [06-pause-contrast.png](ui/06-pause-contrast.png) | Màn hình Tạm dừng: nút chuyển đổi Tương phản cao (H). |

---

## 3. Kiểm chứng Hồi quy & Không phá vỡ Hợp đồng

- Chạy toàn bộ 124 unit test của hệ thống (P1 đến P3, live sim, gameplay determinism):
  - Kết quả: `Ran 124 tests in 7.894s - OK` (xem chi tiết tại [test_suite.log](test_suite.log)).
- Tương thích ngược:
  - Game chạy mượt mà ở cả chế độ thường và chế độ tương phản cao.
  - Snapshot dữ liệu và headless engine hoàn toàn độc lập với tầng rendering trợ năng.
