"""Tests Phase 4 cho TV2: Soak headless 10 ngày (AC-P4-02)."""

import json
import subprocess
import sys
import unittest

from chonoi.soak import run_soak
from helpers import Workdir, run_headless


class SoakPhase4Tests(unittest.TestCase):
    def test_soak_10_days_cli_and_schema(self):
        """Chạy CLI --seed 7 --days 10: đủ 5 trường, days_completed=10, crashes=0."""
        with Workdir() as w:
            out = w.path("soak.json")
            res = subprocess.run(
                [sys.executable, "-m", "chonoi.soak", "--seed", "7", "--days", "10", "--out", out],
                capture_output=True, text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            with open(out, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(set(data.keys()), {"days", "days_completed", "crashes", "results", "duration_s"})
            self.assertEqual(data["days"], 10)
            self.assertEqual(data["days_completed"], 10)
            self.assertEqual(data["crashes"], 0)
            self.assertIsInstance(data["duration_s"], float)
            self.assertEqual(len(data["results"]), 10)
            for idx, row in enumerate(data["results"], start=1):
                self.assertEqual(set(row.keys()), {"day", "earned", "reputation", "score"})
                self.assertEqual(row["day"], idx)

    def test_soak_deterministic_same_seed(self):
        """Cùng seed cho kết quả gameplay giống nhau hoàn toàn."""
        r1 = run_soak(7, 10)
        r2 = run_soak(7, 10)
        self.assertEqual(r1["days_completed"], r2["days_completed"])
        self.assertEqual(r1["crashes"], r2["crashes"])
        self.assertEqual(r1["results"], r2["results"])

    def test_headless_day_still_caps_at_5_and_soak_rejects_zero_days(self):
        """headless --mode day giữ nguyên giới hạn 1..5; soak --days 0 trả mã 2."""
        with Workdir() as w:
            code, _ = run_headless("--mode", "day", "--seed", "1", "--days", "6", "--ticks", "0", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 2)
            res = subprocess.run(
                [sys.executable, "-m", "chonoi.soak", "--seed", "1", "--days", "0", "--out", w.path("s.json")],
                capture_output=True, text=True,
            )
            self.assertEqual(res.returncode, 2)
