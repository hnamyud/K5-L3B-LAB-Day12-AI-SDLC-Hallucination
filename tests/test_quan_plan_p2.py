"""TV3 Phase 2 · 6 món, 2 bếp/4 bàn, day_plan, lọc món theo kế hoạch."""

import unittest

from chonoi.contract import load_contract
from chonoi.day_plan import compute_ingredients, plan_for_day
from helpers import Workdir, events, read_jsonl, run_headless, snapshots, write_json


class DayPlanData(unittest.TestCase):
    def test_contract_has_six_dishes_two_stoves_four_tables(self):
        c = load_contract()
        self.assertIn(c["contract_version"], ("1.1", "1.2", "1.3"))
        menu = c["tuning"]["menu"]
        self.assertEqual(set(menu), {
            "ca_loc_nuong_trui", "goi_bong_sung", "lau_ca_linh_dien_dien",
            "canh_chua_ca_loc", "ca_keo_nuong", "lau_mam",
        })
        self.assertEqual([s["id"] for s in c["tuning"]["quan"]["stoves"]], ["B1", "B2"])
        self.assertEqual([t["id"] for t in c["tuning"]["quan"]["tables"]], ["T1", "T2", "T3", "T4"])

    def test_day_plan_ingredients_match_ticket(self):
        c = load_contract()
        expected = {
            1: {"bong_sung": 6, "ca_loc": 3},
            2: {"bong_dien_dien": 2, "ca_linh": 6, "ca_loc": 2},
            3: {"bong_dien_dien": 2, "bong_sung": 4, "ca_keo": 4, "ca_loc": 2},
            4: {"bong_dien_dien": 1, "bong_sung": 2, "ca_keo": 1, "ca_linh": 2, "ca_loc": 2, "keo_neo": 1},
            5: {"bong_dien_dien": 2, "ca_keo": 1, "ca_linh": 5, "ca_loc": 1, "keo_neo": 1},
        }
        for day, ingredients in expected.items():
            plan = plan_for_day(c["tuning"], day)
            self.assertEqual(plan["ingredients"], ingredients)
            self.assertEqual(compute_ingredients(c["tuning"]["menu"], plan["dishes"]), ingredients)


class QuanPlanFilter(unittest.TestCase):
    def run_quan(self, workdir, scenario, ticks, seed=1):
        scenario_path = write_json(workdir.path("scenario.json"), {"quan": scenario})
        out = workdir.path("quan.jsonl")
        code, err = run_headless(
            "--mode", "quan", "--seed", str(seed), "--ticks", str(ticks),
            "--scenario", scenario_path, "--snapshot-every", "1", "--out", out,
        )
        self.assertEqual(code, 0, err)
        return read_jsonl(out)

    def test_standalone_quan_can_order_any_of_six(self):
        """Quán độc lập: đủ nguyên liệu lau_mam → có thể gọi lau_mam."""
        with Workdir() as w:
            rows = self.run_quan(w, {
                "stock": {"ca_linh": 4, "ca_keo": 2, "keo_neo": 2, "bong_dien_dien": 2},
                "time_left_ticks": 200,
            }, ticks=120, seed=7)
        arrived = events(rows, "customer_arrived")
        self.assertEqual(len(arrived), 1)
        self.assertIn(arrived[0]["data"]["dish_id"], {
            "lau_ca_linh_dien_dien", "ca_keo_nuong", "lau_mam",
        })

    def test_day_plan_filters_menu_ids(self):
        """Trong day: chỉ món thuộc kế hoạch dù kho đủ món ngoài plan."""
        with Workdir() as w:
            rows = self.run_quan(w, {
                "stock": {
                    "ca_loc": 5, "bong_sung": 5, "ca_linh": 9, "bong_dien_dien": 5,
                    "ca_keo": 5, "keo_neo": 5,
                },
                "day_plan": {"dishes": {"goi_bong_sung": 3}, "ingredients": {"bong_sung": 6}},
                "time_left_ticks": 2000,
            }, ticks=1020, seed=1)
        arrived = events(rows, "customer_arrived")
        self.assertGreaterEqual(len(arrived), 2)
        for e in arrived:
            self.assertEqual(e["data"]["dish_id"], "goi_bong_sung")

    def test_plan_servings_do_not_cap_orders(self):
        """Suất kế hoạch không chặn bán thêm khi còn nguyên liệu."""
        with Workdir() as w:
            rows = self.run_quan(w, {
                "stock": {"bong_sung": 20},
                "day_plan": {"dishes": {"goi_bong_sung": 1}, "ingredients": {"bong_sung": 2}},
                "time_left_ticks": 2000,
            }, ticks=1020, seed=3)
        arrived = events(rows, "customer_arrived")
        # first@120, next@1020 → ít nhất 2 đơn dù plan chỉ 1 suất
        self.assertGreaterEqual(len(arrived), 2)
        self.assertTrue(all(e["data"]["dish_id"] == "goi_bong_sung" for e in arrived))

    def test_two_orders_do_not_double_reserve_stock(self):
        """Hai đơn reserved không tiêu trùng nguyên liệu khả dụng."""
        with Workdir() as w:
            rows = self.run_quan(w, {
                "stock": {"ca_loc": 1},
                "customers": [
                    {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                     "patience_ticks_left": 9999},
                ],
                "time_left_ticks": 200,
            }, ticks=120, seed=1)
        # C1 đã giữ ca_loc×1 → available=0 → spawn tick 120 phải no_dish (còn bàn trống)
        self.assertEqual(events(rows, "customer_arrived"), [])
        self.assertEqual(len(events(rows, "no_dish")), 1)
        snap = snapshots(rows)[0]
        self.assertEqual(snap["customers"][0]["reserved"], {"ca_loc": 1})
        self.assertEqual(snap["stock"], {"ca_loc": 1})

    def test_all_tables_busy_skips_spawn(self):
        with Workdir() as w:
            customers = [
                {"id": f"C{i}", "table_id": f"T{i}", "dish_id": "ca_loc_nuong_trui",
                 "patience_ticks_left": 9999}
                for i in range(1, 5)
            ]
            rows = self.run_quan(w, {
                "stock": {"ca_loc": 10},
                "customers": customers,
                "time_left_ticks": 200,
            }, ticks=120)
        self.assertEqual(events(rows, "customer_arrived"), [])
        self.assertEqual(events(rows, "no_dish"), [])
        self.assertEqual(len(snapshots(rows)[-1]["customers"]), 4)
