# nguyenduymanh — phản tư cá nhân (TV2)

- **Tôi đã làm:**
  - **Phase 1 (`dcf5b50`):** Hoàn thiện hái nút, bắt cá, cooldown, hòa ID (`_nearest_in_radius`, `_harvest`, `_catch`) trong `chonoi/sim/gather.py` và 9 test biên trong `tests/test_gather_harvest.py`.
  - **Phase 2 (`ef6f4c1`):** Cập nhật 6 nguyên liệu, nút N5/N6 (`keo_neo`), `ca_keo`, 8 đàn cá ban đầu, cá bơi/phản xạ/đổi hướng tick 120 và sinh cá tick 360 (`tests/test_gather_fish_p2.py`).
  - **Phase 3 (`513ea6c`):** Triển khai kho cá thể v1.2, hao tươi 0.5/s, ngưỡng `spoiled` tại 30, cấp ID `fresh=100` và LIFO cá thể (`tests/test_gather_freshness_p3.py`).
  - **Phase 4 (`5ca7c8f`):** Viết `chonoi/soak.py` (`--seed 7 --days 10`), lặp kế hoạch D1–D5 ở Ngày 6–10 trong `chonoi/sim/day.py`, và `tests/test_soak_p4.py` (10 ngày, 0 crash, tất định).
- **AI sai ở đâu & tôi phát hiện thế nào:**
  - Khi sang Phase 2 có cá bơi mặc định, test bắt cá ở mép bán kính bị rớt do cá bơi ra ngoài sau tick 0; tôi phát hiện qua chạy `unittest` và thêm `random_fish: false` cho fixture tĩnh.
  - Ở Phase 3, phép trừ float `0.5/60` dễ lệch ở ngưỡng `30`; kiểm tra bằng scenario `fresh=30` và chuyển sang biểu diễn `240` đơn vị/điểm.
- **Điều tôi học được:** Khóa hành vi bằng test biên và fixture tất định trước khi ghép giúp tích hợp 4 phase nhanh và không vỡ `main`.
