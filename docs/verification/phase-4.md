# Ma trận truy vết Phase 4 · Phát hành v1.0.0

| AC | Cách kiểm chứng | Bằng chứng | Kết quả |
|---|---|---|---|
| **AC-P4-02 · TV2 (`soak_cmd`)** | `python3 -m chonoi.soak --seed 7 --days 10 --out docs/proof/phase-4/soak.json` + `PYTHONPATH=tests:. python3 -m unittest tests/test_soak_p4.py tests/test_day_cycle.py tests/test_tv4_freshness_p3.py -v` | [soak.json](../proof/phase-4/soak.json) · [tv2-soak-test.txt](../proof/phase-4/tv2-soak-test.txt) | **đạt** (`days_completed=10`, `crashes=0`, 14/14 test đạt, tất định cùng seed) |
