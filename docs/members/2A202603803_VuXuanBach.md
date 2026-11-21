# bachvx1709 — phản tư cá nhân (≤ 200 từ)

- Tôi đã làm (kèm link commit): UI, QA, Release.
  - P1–P3: HUD 2 ca, sáng tạo âm thanh, vòng ngày DaySim, HUD độ tươi, QA tools — commit [1d4943e](https://github.com/hnamyud/K5-L3B-LAB-Day12-AI-SDLC-Hallucination/commit/1d4943e), [cb86f34](https://github.com/hnamyud/K5-L3B-LAB-Day12-AI-SDLC-Hallucination/commit/cb86f34), [c06f014](https://github.com/hnamyud/K5-L3B-LAB-Day12-AI-SDLC-Hallucination/commit/c06f014).
  - P4: Chế độ tương phản cao (High Contrast WCAG AAA), 3 cảnh báo trực quan chữ + icon (`🐊 THỦY QUÁI`, `🫁 HẾT HƠI`, `😠 KHÁCH SẮP GIẬN`), ma trận [verification P4](../verification/phase-4.md), bằng chứng [tv5-high-contrast.md](../proof/phase-4/tv5-high-contrast.md).
- Tôi đã review (kèm link): regression suite 124/124 tests xanh — [test_suite.log](../proof/phase-4/test_suite.log); kiểm tra chéo giao diện và tương thích ngược với headless simulation.
- AI sai ở đâu và tôi phát hiện thế nào:
  - Giữ `interact=True` liên tục làm mất cạnh lên → unittest bắt được.
  - Tick con đè tick tổng làm nhảy màn → chơi thử trên web.
  - Phím `H` đè phím tắt hướng dẫn → kiểm tra bàn phím, tách hướng dẫn sang phím `T`.
- Điều tôi học được: tách biệt rõ ràng tầng hiển thị trợ năng và mô phỏng xác định giúp mở rộng giao diện người dùng an toàn tuyệt đối mà không phá vỡ hợp đồng dữ liệu.
