# cuong-huynh — phản tư cá nhân (≤ 200 từ)

- **Tôi đã làm (kèm link commit):**
  - TV3 · `sim/quan`: P1 khách/reserved/`no_dish` ([`267faff`](https://github.com/hnamyud/K5-L3B-LAB-Day12-AI-SDLC-Hallucination/commit/267faff)); P2 sáu món, `day_plan`, 2 bếp/4 bàn ([`615dda9`](https://github.com/hnamyud/K5-L3B-LAB-Day12-AI-SDLC-Hallucination/commit/615dda9), PR #9); P3 kho cá thể, hao tươi, giữ lại khi ươn, dual-mode v1.1 ([`43b48f2`](https://github.com/hnamyud/K5-L3B-LAB-Day12-AI-SDLC-Hallucination/commit/43b48f2), PR #15); P4 `chonoi.bench` đo FPS 1280×720 ([`05624bb`](https://github.com/hnamyud/K5-L3B-LAB-Day12-AI-SDLC-Hallucination/commit/05624bb), [`docs/proof/phase-4/`](../proof/phase-4/tv3-bench.md)).
- **Tôi đã review:** đọc vòng tick/cook của TV4 trước khi gắn spawn lên quan; đối chiếu fixture freshness với schema TV1 khi làm dual-mode.
- **AI sai ở đâu và tôi phát hiện thế nào:** AI để `random_customers: false` trong ca `no_dish` nên không bao giờ spawn — bắt bằng test đỏ, bật spawn có kiểm soát. Harness bench coi `load_ms` xong trước khi `/state` có cá — sửa bằng chờ `player`+`fish` rồi mới đo.
- **Điều tôi học được:** giữ dual-mode và proof theo phase giúp `main` xanh khi nhóm đổi hợp đồng song song; đo render phải neo vào snapshot thật, không chỉ rAF trống.
