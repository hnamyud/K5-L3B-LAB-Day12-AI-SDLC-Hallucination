# Credits

## Tài sản đồ họa và âm thanh
- Đồ họa 2D (`chonoi/web/index.html`): các nhân vật (Út Sen, Má Tư, khách quen), sinh vật (cá linh, cá lóc, cá kèo, Cá Sấu Năm Chèo), cảnh sông Chín Khúc, nhà bè và hiệu ứng thời tiết đều do nhóm Hallucination vẽ bằng HTML5 Canvas 2D, không dùng ảnh hay sprite bên ngoài.
- Âm thanh và nhạc nền (`chonoi/web/index.html`): hiệu ứng âm thanh và nhạc nền ngũ cung được tổng hợp trực tiếp bằng Web Audio API trong trình duyệt, không dùng tệp âm thanh bên ngoài.
- Khung starter và đề bài: khung Python `chonoi/` cùng các tài liệu đặc tả PRD-0 và TICKET-02 đến TICKET-04 thuộc bài lab Day 12 (Quán Ăn Chợ Nổi).
- Giấy phép mã nguồn do nhóm đóng góp: MIT (xem [LICENSE](LICENSE)).

## Công cụ AI đã sử dụng (theo `docs/ai-usage-log.md`)
- Antigravity (Gemini 4 Hydrogen / Gemini 4 Neon) do TV1 và TV2 dùng cho sinh tồn ca sáng, thu hoạch, cá bơi, schema kho cá thể v1.2, độ tươi `Fraction`, hợp đồng và test.
- Codex (GPT-6.1) do TV1 và TV4 dùng cho Cá Sấu Năm Chèo, bếp, thanh toán, vòng ngày `DaySim`, Shop và test headless.
- Claude Code (Claude Opus 5.5) và Gemini 3.8 Flash do TV5 dùng cho giao diện web trọn vòng ngày, HUD độ tươi, Chợ Chú Sáu bản live, script QA (`tools/qa_p2.py`, `tools/qa_p3.py`) và tài liệu kiểm chứng.
