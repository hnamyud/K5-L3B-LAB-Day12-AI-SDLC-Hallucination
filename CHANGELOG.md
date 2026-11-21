# Changelog

## v1.0.0 (2026-11-21)

### Phase 4: Phát hành v1.0.0 (Test Contract v1.3)
- Hỗ trợ `contract_version: "1.3"` và kiểm tra `bench_cmd`, `soak_cmd` trong `chonoi/contract.py`.
- Bổ sung `LICENSE` (MIT), cập nhật `CREDITS.md`, `CHANGELOG.md` theo từng phase và bản nháp release notes `docs/release-notes-v1.0.0.md`.
- Còn chờ ghép từ TV2 đến TV5 trước khi gắn tag `phase-4`: `bench_cmd`, `soak_cmd`, chế độ tương phản cao cùng 3 cảnh báo, kiểm chứng clone sạch tối đa 3 lệnh và `docs/verification/phase-4.md`.

### Phase 3: Mùa Nước Nổi, độ tươi và kho cá thể (Test Contract v1.2)
- Breaking change (v1.2): file kho và cấu trúc `hold`/`stock` chuyển từ dạng đếm (`{"items":{"ca_loc":1}}`) sang mảng cá thể `{"items":[{"id":"I1","kind":"ca_loc","fresh":100}]}`; `customers[].reserved` chuyển sang mảng ID cá thể.
- Thêm `tuning.freshness` (`initial: 100`, `gather_decay_per_s: 0.5`, `quan_decay_per_s: 0.25`, `spoiled_below: 30`) vào `game.contract.json` và kiểm tra trong `chonoi/contract.py`.
- TV1: `chonoi/inventory.py` và `chonoi/ids.py` hỗ trợ đọc/ghi nguyên tử theo `contract_version` (v1.2 từ chối kho đếm bằng mã `2`), tính độ tươi chính xác bằng `Fraction` (khôi phục lưới `1/240` qua JSON), chọn tươi nhất, tính giá theo độ tươi trung bình và `IdAllocator.reserve_all`.
- TV2: hao tươi ca sáng (`0.5/s`), phát `spoiled` một lần theo `id_key`, cấp ID cá thể mới khi hái/bắt, `monster_hit`/`faint` trả `lost` dạng cá thể theo LIFO.
- TV3: kho quán dạng cá thể, hao tươi (`0.25/s`) cả phần đang giữ chỗ, phát `spoiled` rồi nhả hoặc thử giữ lại theo `order_tick`/`table_id`, thiếu hàng chuyển `unfulfillable`.
- TV4: tiêu đúng ID đã giữ khi nấu, chốt `base_price = floor(giá niêm yết × fresh TB / 100)`, boa theo giá đã chốt, giữ nguyên ID trong `day` và tiếp tục cấp ID tăng xuyên ngày; Shop và pause không hao tươi.
- TV5: HUD độ tươi và hàng ươn, bản đồ nhỏ ca sáng, đồ họa mới, đóng quán sớm, `tools/qa_p3.py` (8 checkpoint) và `docs/verification/phase-3.md`.

### Phase 2: Một ngày ở chợ nổi (Test Contract v1.1)
- Số chuẩn và ca sáng (TV1, TV2): 6 nguyên liệu (`ca_loc`, `ca_linh`, `ca_keo`, `bong_dien_dien`, `bong_sung`, `keo_neo`), nút N1 đến N6, 8 đàn cá bơi/phản xạ/đổi hướng (`120·k`)/sinh (`360·k`, trần 12), Cá Sấu Năm Chèo (`M1`, `M2` từ D3) với patrol/chase/recoil, bất tử 90 tick và rơi `floor(n/2)` LIFO.
- Quán và vòng ngày (TV3, TV4): 6 món, 2 bếp (`B1`, `B2`), 4 bàn (`T1` đến `T4`), kế hoạch `day_plan` D1 đến D5, `--mode day` (qua ba pha `gather`, `quan`, `shop`), pause (`Esc/P`), Shop nâng cấp `oxygen`/`hp` áp dụng từ Ngày kế.
- UI, mở rộng và QA (TV5): cửa sổ chơi trọn vòng ngày (`chonoi/live_day.py`), mở rộng Settings và âm thanh (lưu Master/Music/SFX), Chợ Chú Sáu (live), thời tiết/chuyện Má Tư/khách quen, `tools/qa_p2.py` (7 checkpoint, 60 FPS ở 1280×720).

### Phase 1: Hai ca chơi được (Test Contract v1.0)
- TV1: sinh tồn ca sáng (`dive`/`surface`, oxy, `oxygen_empty`, `choke`, `faint` bỏ giỏ LIFO và xuất kho rỗng).
- TV2: hái nút mặt nước, bắt cá dưới nước, ưu tiên bến, hòa ID, mọc lại, cooldown và xuất kho nguyên tử.
- TV3 và TV4: lịch khách, chọn món theo seed, giữ nguyên liệu, kiên nhẫn, từ bếp ra tay tới bàn, tính boa, uy tín và quyết toán đóng ca.
- TV5: HUD hai ca, Web Audio API, lời thoại Nam Bộ, smoke test hai tiến trình và ma trận `docs/verification/phase-1.md`.
