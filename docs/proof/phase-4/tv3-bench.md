# TV3 · Phase 4 — Benchmark có render (`bench_cmd`)

```bash
python3 -m chonoi.bench --seed 42 --duration 30 --out docs/proof/phase-4/bench.json
```

| Trường | Kết quả (commit bàn giao) | Mốc báo cáo |
|---|---|---|
| `avg_fps` | **60.04** | ≥ 60 |
| `p1_low_fps` | **59.52** | ≥ 30 |
| `frames` | 1802 | — |
| `measured_s` | 30.015 | — |
| `load_ms` | **8.5** | ≤ 10 000 |

Artifact: [`bench.json`](bench.json)

## Điều kiện đo

| Mục | Chi tiết |
|---|---|
| Máy | macOS Darwin 27.2.0 arm64 (macOS 27.2.1) |
| Trình duyệt | Google Chrome `--headless=new`, `--window-size=1280,720` |
| Cảnh | `gather` seed 42: Út Sen đứng yên ở bến, cá bơi + Cá Sấu (tuning mặc định), giỏ 3 cá thể có `fresh` (bật `_contract_version` 1.2 chỉ trong tiến trình bench) |
| Warm-up | 3 s rồi đo 30 s qua `requestAnimationFrame` (hook `window.__perf.samples`) |
| Công thức | `avg_fps = frames / measured_s`; `p1_low_fps` = FPS của `max(1, ceil(0.01 * frames))` khung chậm nhất |

## Kiểm tra kèm

```bash
PYTHONPATH=tests:. python3 -m unittest tests.test_bench_p4 -v
```

3/3 đạt (công thức + bench ngắn 2 s có Chrome).
