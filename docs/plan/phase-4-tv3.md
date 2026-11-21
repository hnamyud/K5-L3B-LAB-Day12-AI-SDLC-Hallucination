# Kế hoạch TV3 · Phase 4 — `bench_cmd`

1. `chonoi/bench.py`: Live gather + Chrome 1280×720, inject harness `?bench=1`, warm 3 s / đo 30 s.
2. Xuất đúng 5 trường JSON; lưu `docs/proof/phase-4/bench.json`.
3. Test công thức `p1_low_fps` + integration ngắn khi có Chrome.
4. Không đụng `game.contract.json` (`bench_cmd` / `contract_version` 1.3 do TV1).
