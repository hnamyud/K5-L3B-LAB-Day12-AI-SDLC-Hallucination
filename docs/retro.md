# Retro nhóm

## Phase 2 (nhanh)
- Điều tốt: chia lát theo hợp đồng v1.1 nên TV1–TV4 làm song song bằng fixture; TV5 làm UI từ snapshot mẫu trước khi có `--mode day`, lúc ghép chỉ đổi lớp lõi, client không phải sửa. Có một lệnh QA (`python3 tools/qa_p2.py`) chạy lại toàn bộ checkpoint trên commit bất kỳ.
- Điều tệ: `--mode day` vào main muộn (PR #11) nên smoke day và kiểm UI trên DaySim thật dồn về cuối phase; `chonoi/live.py` bị hai người sửa cùng lúc (TV4 + TV5) gây xung đột khi gộp.
- 1 hành động cho Phase 3: mỗi file dùng chung (`live.py`, `runner.py`, `game.contract.json`) có một chủ duy nhất ghi trong `docs/phan-cong.md`; người khác sửa qua PR nhỏ có tag chủ file review. **Người nhận: TV5 (Vũ Xuân Bách)** cập nhật bảng chủ file đầu Phase 3 và nhắc trong standup phút 20.

## Phase 4 (cuối)
- Rà lại hành động Phase 2: đã làm chưa? vì sao?
- Điều tốt / điều tệ:
- Số liệu: số commit theo người, cách đọc code của nhau, token theo người:
- Một lần AI sai và cách nhóm phát hiện:
- Nếu làm lại, đổi gì:

## Ghi nhận Phase 2 · TV1

- Điều tốt là fixture headless kiểm được ranh giới hit, recoil và LIFO trước khi có vòng ngày/UI.
- Vướng mắc hiện tại là CLI và manifest đang v1.0 nên các ca chuyển ngày cần TV4 tích hợp.
- TV1 và TV4 nhận hành động kiểm day=3 sinh M2 và ngất mở quán kho rỗng khi vòng ngày có mặt.

## Ghi nhận Phase 3 · TV4

- Ghép tạm các diff TV2 và TV3 giúp kiểm được handoff, ID xuyên ngày và dòng thanh toán trước khi đổi manifest.
- Ca nấu sau đúng 60 bước cho thấy sai số của kho thô đi vào phép chốt giá. Giữ ca này trong kiểm chứng khi TV1/TV3 ghép cách biểu diễn độ tươi dùng chung.

## Ghi nhận Phase 3 · TV5

- **Rà hành động Phase 2 (bảng chủ file):** phân công Phase 3 đã ghi chủ từng file (TV1 `inventory.py`/`contract_version`, TV3 `QuanSim.step`, TV5 client/QA). Kết quả: lần gộp main vào nhánh TV5 không có xung đột code; TV1 chỉ sửa 4 dòng `chonoi/live.py` trong PR của mình. Đã làm, giữ cho Phase 4.
- **Điều tốt:** checkpoint chạy bằng CLI trên bản sao bật 1.2 nên kiểm được v1.2 khi manifest chưa bật mà không đụng file của TV1; HUD làm từ snapshot mẫu trước, ghép sim thật chỉ phải nới bố cục.
- **Điều tệ (rút ra từ lần đổi kho):** đổi schema kho làm vỡ fixture ở 9 file test của 4 người; các lát tự đạt test của mình trên 1.1 nên tới cuối phase mới thấy 18 test hỏng khi bật 1.2.
- **1 hành động cho Phase 4:** khi đổi hợp đồng dữ liệu, TV5 chạy `qa_p3.py` (CP8b — suite trên bản bật version mới) ngay phút 20 và gửi danh sách test hỏng theo chủ lát vào standup. **Người nhận: TV5 (Vũ Xuân Bách).**

## Ghi nhận Phase 4 · TV5

- **Rà lại hành động Phase 2 & Phase 3:** Bảng chủ sở hữu file và phân tách trách nhiệm được duy trì triệt để. TV5 phụ trách toàn diện Accessibility (High Contrast) và 3 Cảnh báo trực quan (AC-P4-03) trên Web Client, độc lập với các lát `soak` (TV2) và `bench` (TV3).
- **Điều tốt:** Kiến trúc phân tách giao diện người dùng theo chuẩn web semantics và snapshot rendering giúp thêm chế độ Tương phản cao toàn diện (WCAG AAA) mà không ảnh hưởng bất kỳ luồng xử lý tick nào của engine headless. Toàn bộ 124 unit test hồi quy P1–P3 đạt 100% xanh (`Ran 124 tests in 7.894s - OK`).
- **Điều tệ:** Môi trường sandbox chặn loopback socket connection khiến kiểm thử `test_live.py` cần gắn cờ cấp quyền socket mạng cục bộ.
- **Một lần AI sai và cách nhóm phát hiện:** AI gán phím tắt `H` đè lên phím ẩn hướng dẫn của Phase 3 khiến không bật được tương phản cao khi đang xem tutorial. TV5 phát hiện khi rà soát bàn phím và kiểm thử trực tiếp trên trình duyệt, đã chủ động đổi phím hướng dẫn sang `T` (Tutorial) và nhường `H` (High Contrast) cho trợ năng, đồng thời bổ sung các nút bấm chuột trực quan trên Menu, Pause và Settings.
- **Nếu làm lại, đổi gì:** Xây dựng một module quản lý phím tắt tập trung (`input_shortcuts.js`) có kiểm tra xung đột phím ngay từ Phase 1 thay vì xử lý rải rác trong `keydown`.
