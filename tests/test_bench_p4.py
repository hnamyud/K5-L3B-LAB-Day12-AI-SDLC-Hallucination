"""TV3 Phase 4 — chonoi.bench: công thức p1_low + CLI xuất đủ 5 trường."""

import json
import math
import os
import tempfile
import unittest

from chonoi.bench import BENCH_FIELDS, find_chrome, p1_low_fps, run_bench, summarize


class P1LowFormulaTest(unittest.TestCase):
    def test_n_is_ceil_one_percent(self):
        # 100 khung → n=1; 101 → n=2
        dts = [10.0] * 99 + [50.0]
        self.assertEqual(max(1, math.ceil(0.01 * 100)), 1)
        self.assertAlmostEqual(p1_low_fps(dts), 1000.0 / 50.0)

        dts2 = [10.0] * 99 + [40.0, 50.0]  # 101 khung
        n = max(1, math.ceil(0.01 * 101))
        self.assertEqual(n, 2)
        self.assertAlmostEqual(p1_low_fps(dts2), (2 * 1000.0) / (50.0 + 40.0))

    def test_summarize_five_fields(self):
        dts = [16.67] * 60
        out = summarize(dts, 1.0, 120.5)
        self.assertEqual(list(out.keys()), list(BENCH_FIELDS))
        self.assertEqual(out["frames"], 60)
        self.assertAlmostEqual(out["avg_fps"], 60.0)
        self.assertAlmostEqual(out["load_ms"], 120.5)


@unittest.skipUnless(find_chrome(), "cần Chrome/Chromium để chạy bench có render")
class BenchIntegrationTest(unittest.TestCase):
    def test_short_bench_writes_five_fields(self):
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, "bench.json")
            result = run_bench(seed=42, duration=2.0, warmup=0.5, out_path=out)
            self.assertTrue(os.path.isfile(out))
            with open(out, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(set(data), set(BENCH_FIELDS))
            self.assertEqual(data["frames"], result["frames"])
            self.assertGreater(data["frames"], 30)  # ~2s @ ≥15 FPS tối thiểu
            self.assertGreater(data["avg_fps"], 15.0)
            self.assertGreater(data["measured_s"], 1.5)
            self.assertGreater(data["load_ms"], 0.0)
            self.assertLess(data["load_ms"], 15000.0)


if __name__ == "__main__":
    unittest.main()
