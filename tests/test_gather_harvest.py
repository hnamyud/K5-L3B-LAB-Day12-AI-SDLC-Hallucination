"""Unit & headless tests cho Lát 2 (TV2): Thu hoạch nút, bắt cá, cập bến và xuất kho."""

import json
import os
import unittest

from helpers import Workdir, events, frames, read_jsonl, run_headless, snapshots, write_json


def tuning_gather():
    with open("game.contract.json", encoding="utf-8") as f:
        return json.load(f)["tuning"]["gather"]


class GatherHarvestTests(unittest.TestCase):
    def test_harvest_node_at_surface_and_edge_radius(self):
        """Hái nút ở mặt nước đúng mép interact_radius -> vào giỏ, đặt regrow_ticks, phát gather."""
        g = tuning_gather()
        r = g["interact_radius"]
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [20.0, 0.0]},
                    "nodes": [{"id": "N1", "kind": "bong_dien_dien", "pos": [20.0 + r, 0.0]}],
                    "fish": [],
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}, {"tick": 1, "interact": False}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "2", "--scenario", sc,
                                     "--inputs", inp, "--snapshot-every", "1", "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            evs = events(rows)
            self.assertEqual([(e["tick"], e["name"], e["data"]) for e in evs], [
                (1, "gather", {"node_id": "N1", "kind": "bong_dien_dien", "amount": g["node_yield"]}),
            ])
            s1 = snapshots(rows)[1]
            self.assertEqual([x["kind"] for x in s1["hold"]], ["bong_dien_dien"])
            self.assertEqual(s1["nodes"][0]["regrow_ticks"], int(round(g["regrow_s"] * 60)))
            self.assertFalse(s1["nodes"][0]["ready"])

    def test_harvest_requires_surface(self):
        """Đang dưới nước (d > surface_depth) không hái được nút dù trong interact_radius."""
        g = tuning_gather()
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [20.0, g["surface_depth"] + 0.1]},
                    "nodes": [{"id": "N1", "kind": "bong_sung", "pos": [20.0, 0.0]}],
                    "fish": [],
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows), [])
            self.assertEqual(snapshots(rows)[-1]["hold"], [])

    def test_harvest_tie_break_by_id_and_regrow_immediate(self):
        """Hòa khoảng cách chọn N2 trước N10; nút vừa regrow từ 1 -> 0 hái được ngay trong bước."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [20.0, 0.0]},
                    "nodes": [
                        {"id": "N10", "kind": "bong_sung", "pos": [21.0, 0.0], "regrow_ticks": 1},
                        {"id": "N2", "kind": "bong_dien_dien", "pos": [19.0, 0.0], "regrow_ticks": 1},
                    ],
                    "fish": [],
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            evs = events(read_jsonl(w.path("o.jsonl")))
            self.assertEqual([(e["name"], e["data"]) for e in evs], [
                ("node_regrown", {"node_id": "N2"}),
                ("node_regrown", {"node_id": "N10"}),
                ("gather", {"node_id": "N2", "kind": "bong_dien_dien", "amount": 1}),
            ])

    def test_harvest_hold_full_keeps_node_ready(self):
        """Giỏ đầy khi hái phát hold_full và giữ nguyên nút ready."""
        cap = tuning_gather()["hold_capacity"]
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [20.0, 0.0]},
                    "hold": [{"id": f"I{i + 1}", "kind": "ca_loc", "fresh": 100} for i in range(cap)],
                    "nodes": [{"id": "N1", "kind": "bong_sung", "pos": [20.5, 0.0]}],
                    "fish": [],
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            evs = events(rows)
            self.assertEqual(len(evs), 1)
            self.assertEqual(evs[0]["name"], "hold_full")
            self.assertEqual(evs[0]["data"], {"action": "gather", "node_id": "N1", "required": 1, "free": 0})
            self.assertTrue(snapshots(rows)[-1]["nodes"][0]["ready"])

    def test_dock_priority_over_harvest(self):
        """Ở trong vùng bến và gần nút: interact ưu tiên cập bến (docked), không hái nút."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [2.0, 0.0]},
                    "hold": [{"id": "I1", "kind": "ca_loc", "fresh": 100}],
                    "nodes": [{"id": "N1", "kind": "bong_sung", "pos": [2.5, 0.0]}],
                    "fish": [],
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"), "--inventory-out", w.path("inv.json"))
            self.assertEqual(code, 0, err)
            evs = events(read_jsonl(w.path("o.jsonl")))
            self.assertEqual([e["name"] for e in evs], ["gather_end"])
            self.assertEqual(evs[0]["data"]["reason"], "docked")
            self.assertEqual([x["kind"] for x in evs[0]["data"]["inventory"]["items"]], ["ca_loc"])

    def test_catch_fish_underwater_cooldown_and_tie_break(self):
        """Bắt cá dưới nước đúng mép, hòa theo ID (F2 trước F10), đặt cooldown dùng lại ở t+L."""
        g = tuning_gather()
        r = g["catch_radius"]
        cd = int(round(g["catch_cooldown_s"] * 60))
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [30.0, 10.0]},
                    "nodes": [],
                    "random_fish": False,
                    "fish": [
                        {"id": "F10", "kind": "ca_loc", "pos": [30.0 + r, 10.0]},
                        {"id": "F2", "kind": "ca_linh", "pos": [30.0 - r, 10.0]},
                    ],
                }
            })
            inp = write_json(w.path("in.json"), frames(
                {"tick": 0, "catch": True},
                {"tick": 1, "catch": False},
                {"tick": 2, "catch": True},       # đang cooldown -> bỏ qua
                {"tick": 3, "catch": False},
                {"tick": cd, "catch": True},     # đúng t + L -> bắt được F10
            ))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", str(cd + 1), "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            evs = events(rows)
            self.assertEqual([(e["tick"], e["name"], e["data"]) for e in evs], [
                (1, "fish_caught", {"fish_id": "F2", "kind": "ca_linh", "yield": 3}),
                (cd + 1, "fish_caught", {"fish_id": "F10", "kind": "ca_loc", "yield": 1}),
            ])
            s_end = snapshots(rows)[-1]
            self.assertEqual([x["kind"] for x in s_end["hold"]], ["ca_linh", "ca_linh", "ca_linh", "ca_loc"])
            self.assertEqual(s_end["fish"], [])

    def test_catch_hold_full_keeps_fish_and_cooldown_and_no_fallback(self):
        """Giỏ thiếu chỗ giữ nguyên đàn cá, giữ cooldown=0, không thử đàn khác."""
        cap = tuning_gather()["hold_capacity"]
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [30.0, 10.0]},
                    "hold": [{"id": f"I{i + 1}", "kind": "bong_sung", "fresh": 100} for i in range(cap - 2)],  # còn 2 chỗ, không đủ cho ca_linh (cần 3)
                    "nodes": [],
                    "fish": [
                        {"id": "F1", "kind": "ca_linh", "pos": [30.5, 10.0]},
                        {"id": "F2", "kind": "ca_loc", "pos": [31.0, 10.0]},  # xa hơn, cần 1 chỗ nhưng không được thử
                    ],
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "catch": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            evs = events(rows)
            self.assertEqual([(e["name"], e["data"]) for e in evs], [
                ("hold_full", {"action": "catch", "fish_id": "F1", "required": 3, "free": 2}),
            ])
            s = snapshots(rows)[-1]
            self.assertEqual(len(s["fish"]), 2)
            self.assertEqual(s["player"]["catch_cd_ticks"], 0)

    def test_catch_no_fish_in_range_and_not_at_surface(self):
        """Không có cá trong tầm -> không event, không cooldown; ở mặt nước -> không bắt được."""
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [30.0, 0.2]},
                    "nodes": [],
                    "fish": [{"id": "F1", "kind": "ca_loc", "pos": [30.0, 0.6]}],
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "catch": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "1", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(events(rows), [])
            self.assertEqual(snapshots(rows)[-1]["player"]["catch_cd_ticks"], 0)

    def test_last_tick_harvest_and_dock_edge_and_tick_limit_inventory(self):
        """Hái ở bước cuối vẫn vào kho; cập bến đúng mép ở bước cuối cho docked; tick_limit giữ nguyên file kho."""
        g = tuning_gather()
        # 1) Hái ở bước cuối (time_left_ticks=1) -> vẫn vào kho khi reason="time"
        with Workdir() as w:
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [12.0, 0.0]},
                    "nodes": [{"id": "N1", "kind": "bong_dien_dien", "pos": [12.0, 0.0]}],
                    "fish": [],
                    "time_left_ticks": 1,
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            inv = w.path("inv.json")
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"), "--inventory-out", inv)
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            evs = events(rows)
            self.assertEqual([e["name"] for e in evs], ["gather", "gather_end"])
            self.assertEqual(evs[-1]["data"]["reason"], "time")
            self.assertEqual([x["kind"] for x in evs[-1]["data"]["inventory"]["items"]], ["bong_dien_dien"])
            with open(inv, encoding="utf-8") as f:
                self.assertEqual([x["kind"] for x in json.load(f)["items"]], ["bong_dien_dien"])

        # 2) Cập bến đúng mép dock_radius ở bước cuối -> docked
        with Workdir() as w:
            dx, dd = g["dock_pos"]
            sc = write_json(w.path("sc.json"), {
                "gather": {
                    "player": {"pos": [dx + g["dock_radius"], dd]},
                    "hold": [{"id": "I1", "kind": "ca_loc", "fresh": 100}],
                    "nodes": [],
                    "fish": [],
                    "time_left_ticks": 1,
                }
            })
            inp = write_json(w.path("in.json"), frames({"tick": 0, "interact": True}))
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "5", "--scenario", sc,
                                     "--inputs", inp, "--out", w.path("o.jsonl"))
            self.assertEqual(code, 0, err)
            rows = read_jsonl(w.path("o.jsonl"))
            self.assertEqual(rows[-1]["reason"], "docked")
            self.assertEqual([x["kind"] for x in events(rows)[-1]["data"]["inventory"]["items"]], ["ca_loc"])

        # 3) Chạm tick_limit sớm -> giữ nguyên file kho đã có
        with Workdir() as w:
            inv = w.path("inv.json")
            sentinel = {"items": {"ca_loc": 5}}
            write_json(inv, sentinel)
            code, err = run_headless("--mode", "gather", "--seed", "1", "--ticks", "3",
                                     "--out", w.path("o.jsonl"), "--inventory-out", inv)
            self.assertEqual(code, 0, err)
            with open(inv, encoding="utf-8") as f:
                self.assertEqual(json.load(f), sentinel)
