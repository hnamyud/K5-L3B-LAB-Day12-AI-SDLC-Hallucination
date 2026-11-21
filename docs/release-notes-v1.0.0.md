# Dự thảo release notes v1.0.0 · Quán Ăn Chợ Nổi

Bản nháp cho đợt phát hành của nhóm Hallucination (K5-L3B Day 12, AI SDLC), mục tiêu Test Contract v1.3. Chốt nội dung và kết quả benchmark/soak sau tích hợp, trước khi công bố Release.

## Điểm mới chính
- Vòng ngày 5 ngày liên tiếp qua ba pha `gather`, `quan` và `shop`: Út Sen lặn hái 6 loại nguyên liệu, tránh Cá Sấu Năm Chèo, nấu 6 món trên 2 bếp và 4 bàn, rồi mua nâng cấp Bình oxy hoặc Áo phao cho ngày sau.
- Kho cá thể và độ tươi (v1.2): từng nguyên liệu mang `{id, kind, fresh}` từ lúc thu hoạch đến khi nấu. Hàng có độ tươi dưới `30` chuyển sang ươn (`spoiled`); đơn bị ảnh hưởng tự nhả và giữ lại phần thay thế nếu còn hàng, còn giá bán chốt theo công thức `floor(giá niêm yết × độ tươi TB / 100)`.
- Giao diện, cảnh báo và mở rộng: thêm HUD độ tươi, bản đồ nhỏ ca sáng, cảnh báo bằng chữ và biểu tượng (thủy quái gần, oxy sắp hết, khách sắp giận), chế độ tương phản cao, cùng phần mở rộng Settings và âm thanh (lưu mức Master, Music, SFX) dùng đồ họa Canvas 2D và Web Audio API tự tổng hợp.
- Lệnh kiểm chứng CLI dự kiến sau tích hợp TV2/TV3: `headless_cmd`, `bench_cmd` đo FPS ở `1280×720` và `soak_cmd` chạy lặp 10 ngày tất định.

## Cách chạy từ clone sạch (tối đa 3 lệnh, Python từ 3.10 trở lên)
```bash
git clone https://github.com/hnamyud/K5-L3B-LAB-Day12-AI-SDLC-Hallucination.git && cd K5-L3B-LAB-Day12-AI-SDLC-Hallucination
python3 -m chonoi.live --mode day
```
Các lệnh kiểm tra dự kiến cho bản phát hành (bench/soak chờ tích hợp):
- Chạy toàn bộ test: `PYTHONPATH=tests:. python3 -m unittest discover -s tests -v`
- Chạy headless: `python3 -m chonoi.headless --mode day --seed 42 --days 1 --ticks 22200 --out day1.jsonl`
- Chạy benchmark: `python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json`
- Chạy soak 10 ngày: `python3 -m chonoi.soak --seed 7 --days 10 --out soak.json`

## Giới hạn đã biết
- Phần Chợ Chú Sáu (`vendor`) mới chạy trong cửa sổ chơi trực tiếp (`chonoi/live_day.py`), chưa khai báo mã `vendor` trong `extensions` của chế độ headless.
- Chế độ chơi trực tiếp yêu cầu trình duyệt hỗ trợ HTML5 Canvas và Web Audio API (Chrome, Edge, Safari hoặc Firefox).
