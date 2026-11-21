"""Tests Phase 2 cho Lát 2 (TV2): 8 đàn cá ban đầu, cá bơi/phản xạ/đổi hướng, sinh theo lịch, N5/N6 và 6 nguyên liệu."""

import json
import math
import unittest

from helpers import Workdir, events, frames, read_jsonl, run_headless, snapshots, write_json


def tuning_gather():
    with open("game.contract.json", encoding="utf-8") as f:
        return json.load(f)["tuning"]["gather"]


class GatherFishPhase2Tests(unittest.TestCase):
    def test_initial_8_fish_distinct_positions_and_valid_grid(self):
        """Đầu ca có 8 đàn cá ở 8 vị trí hình học khác nhau trên lưới sinh chuẩn."""
        g = tuning_gather()
        with Workdir() as w:
            code, err = run_headless("--mode", "gather", "--seed", "7", "--ticks", "0", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            s0 = snapshots(read_jsonl(w.path("o.jsonl")))[0]
            fish = s0["fish"]
            self.assertEqual(len(fish), 8)
            positions = {tuple(f["pos"]) for f in fish}
            self.assertEqual(len(positions), 8)
            for f in fish:
                self.assertIn(f["pos"][0], g["fish_spawn_x"])
                self.assertIn(f["pos"][1], g["fish_spawn_depths"][f["kind"]])
                self.assertEqual(f["age_ticks"], 0)

    def test_fish_turn_at_tick_120_and_catch_before_swim(self):
        """Đổi hướng ở bước bơi thứ 120; bắt cá theo vị trí đầu bước trước khi cá bơi."""
        g = tuning_gather()
        with Workdir() as w:
            # 1) Bắt cá ở mép catch_radius khi cá đang bơi ra xa -> vẫn bắt được ở tick 0
            sc = write_json(w.path("sc1.json"), {
                "gather": {
                    "player": {"pos": [30.0, 10.0]},
                    "nodes": [],
                    "fish": [{"id": "F1", "kind": "ca_keo", "pos": [30.0 + g["catch_radius"], 10.0], "heading_deg": 0}],
                }
            })
            inp = write_json(w.path("in1.json"), frames({"tick": 0, "catch": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o1.jsonl"))
            self.assertEqual(code, 0, err)
            evs = events(read_jsonl(w.path("o1.jsonl")))
            self.assertEqual([(e["name"], e["data"]) for e in evs], [
                ("fish_caught", {"fish_id": "F1", "kind": "ca_keo", "yield": 2}),
            ])

            # 2) Cá bơi 120 bước: bước 119 giữ nguyên hướng 0°, bước 120 đổi hướng theo seed
            sc2 = write_json(w.path("sc2.json"), {
                "gather": {
                    "player": {"pos": [2.0, 0.0]},
                    "nodes": [],
                    "fish": [{"id": "F1", "kind": "ca_linh", "pos": [20.0, 6.0], "heading_deg": 0}],
                }
            })
            code, err = run_headless("--mode", "gather", "--seed", "42", "--ticks", "120", "--scenario", sc2,
                                     "--snapshot-every", "1", "--out", w.path("o2.jsonl"))
            self.assertEqual(code, 0, err)
            snaps = {r["tick"]: r for r in snapshots(read_jsonl(w.path("o2.jsonl")))}
            self.assertEqual(snaps[119]["fish"][0]["heading_deg"], 0.0)
            self.assertEqual(snaps[119]["fish"][0]["age_ticks"], 119)
            self.assertNotEqual(snaps[120]["fish"][0]["heading_deg"], 0.0)
            self.assertEqual(snaps[120]["fish"][0]["age_ticks"], 120)

    def test_fish_reflection_x_d_and_corner(self):
        """Cá phản xạ mép x, mép d và góc: giữ phần quãng đường dư và đảo thành phần hướng vuông góc."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [2.0, 0.0]},
                    "nodes": [],
                    "fish": [
                        {"id": "F1", "kind": "ca_linh", "pos": [95.99, 6.0], "heading_deg": 0},
                        {"id": "F2", "kind": "ca_linh", "pos": [50.0, 11.99], "heading_deg": 90},
                        {"id": "F3", "kind": "ca_linh", "pos": [95.99, 11.99], "heading_deg": 45},
                    ],
                }
            })
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            f = {x["id"]: x for x in snapshots(read_jsonl(w.path("o.jsonl")))[-1]["fish"]}
            self.assertLessEqual(f["F1"]["pos"][0], 96.0)
            self.assertAlmostEqual(f["F1"]["heading_deg"], 180.0, places=2)
            self.assertLessEqual(f["F2"]["pos"][1], 12.0)
            self.assertAlmostEqual(f["F2"]["heading_deg"], 270.0, places=2)
            self.assertLessEqual(f["F3"]["pos"][0], 96.0)
            self.assertLessEqual(f["F3"]["pos"][1], 12.0)
            self.assertAlmostEqual(f["F3"]["heading_deg"], 225.0, places=2)

    def test_fish_spawn_at_360_and_cap_12_and_random_false(self):
        """Sinh cá ở phase_tick=360, tôn trọng trần 12 đàn; random_fish=false tắt bơi và sinh."""
        # 1) Sinh tại tick 360
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [2.0, 0.0]},
                    "nodes": [],
                    "fish": [{"id": "F1", "kind": "ca_linh", "pos": [15.0, 5.0], "heading_deg": 0}],
                }
            })
            code, err = run_headless("--mode", "gather", "--seed", "5", "--ticks", "360", "--scenario", sc,
                                     "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            spawned = [e for e in events(rows) if e["name"] == "fish_spawned"]
            self.assertEqual(len(spawned), 1)
            self.assertEqual(spawned[0]["tick"], 360)
            self.assertEqual(spawned[0]["data"]["id"], "F2")
            self.assertEqual(len(snapshots(rows)[-1]["fish"]), 2)

        # 2) Trần 12 đàn -> không sinh thêm ở tick 360
        with Workdir() as w:
            fish_12 = [{"id": f"F{i}", "kind": "ca_loc", "pos": [10.0 + i * 5, 10.0], "heading_deg": 0}
                       for i in range(1, 13)]
            sc = write_json(w.path("sc.json"), {"gather": {"nodes": [], "fish": fish_12}})
            code, err = run_headless("--mode", "gather", "--seed", "5", "--ticks", "360", "--scenario", sc,
                                     "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual([e for e in events(rows) if e["name"] == "fish_spawned"], [])
            self.assertEqual(len(snapshots(rows)[-1]["fish"]), 12)

        # 3) random_fish=false -> cá đứng yên và không sinh thêm
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "nodes": [],
                    "random_fish": False,
                    "fish": [{"id": "F1", "kind": "ca_keo", "pos": [30.0, 25.0], "heading_deg": 0}],
                }
            })
            code, err = run_headless("--mode", "gather", "--seed", "5", "--ticks", "360", "--scenario", sc,
                                     "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual([e for e in events(rows) if e["name"] == "fish_spawned"], [])
            f1 = snapshots(rows)[-1]["fish"][0]
            self.assertEqual(f1["pos"], [30.0, 25.0])
            self.assertEqual(f1["age_ticks"], 0)

    def test_keo_neo_and_ca_keo_integration_to_quan(self):
        """Hái keo_neo (N5) + mang ca_keo -> cập bến xuất kho -> quán đọc đủ 6 loại nguyên liệu."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [76.0, 0.0]},
                    "hold": [
                        {"id": "I1", "kind": "ca_keo", "fresh": 100},
                        {"id": "I2", "kind": "ca_keo", "fresh": 100},
                    ],
                    "random_fish": False,
                }
            })
            # Tick 0: hái N5 (keo_neo); sau đó đặt scenario cập bến với hold có keo_neo + ca_keo
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("g1.jsonl"))
            self.assertEqual(code, 0, err)
            self.assertEqual(
                [x["kind"] for x in snapshots(read_jsonl(w.path("g1.jsonl")))[-1]["hold"]],
                ["ca_keo", "ca_keo", "keo_neo"],
            )

            sc_dock = write_json(w.path("dock.json"), {
                "gather": {"hold": [
                    {"id": "I1", "kind": "ca_keo", "fresh": 100},
                    {"id": "I2", "kind": "ca_keo", "fresh": 100},
                    {"id": "I3", "kind": "keo_neo", "fresh": 100},
                ], "random_fish": False}
            })
            inv = w.path("inv.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc_dock,
                                     "--inputs", inp, "--out", w.path("g2.jsonl"), "--inventory-out", inv)
            self.assertEqual(code, 0, err)
            code, err = run_headless("--mode", "quan", "--seed", "1", "--inventory", inv, "--ticks", "0",
                                     "--out", w.path("q.jsonl"))
            self.assertEqual(code, 0, err)
            q0 = snapshots(read_jsonl(w.path("q.jsonl")))[0]
            self.assertEqual(
                [(x["id"], x["kind"]) for x in q0["stock"]],
                [("I1", "ca_keo"), ("I2", "ca_keo"), ("I3", "keo_neo")],
            )
