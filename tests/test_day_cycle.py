"""Bằng chứng TV4 Phase 2 qua CLI, fixture và JSONL."""
import os
import unittest

from helpers import Workdir, events, frames, read_jsonl, run_headless, snapshots, write_json


class DayCycle(unittest.TestCase):
    def play(self, scenario, inputs=(), *, ticks=605, days=None, mode="day", bad=False, extra=()):
        with Workdir() as w:
            sc = write_json(w.path("scenario.json"), scenario)
            keys = write_json(w.path("inputs.json"), frames(*inputs))
            out = w.path("day.jsonl")
            args = ["--mode", mode, "--seed", "42", "--ticks", str(ticks), "--out", out,
                    "--scenario", sc, "--inputs", keys, *extra]
            if days is not None:
                args += ["--days", str(days)]
            code, err = run_headless(*args)
            if bad:
                self.assertEqual(code, 2, err)
                self.assertFalse(os.path.exists(out))
                return
            self.assertEqual(code, 0, err)
            return read_jsonl(out)

    def test_one_day_default_waits_for_shop_timeout(self):
        scenario = {"gather": {"hold": [
            {"id": "I1", "kind": "ca_loc", "fresh": 100},
            {"id": "I2", "kind": "ca_keo", "fresh": 100},
            {"id": "I3", "kind": "keo_neo", "fresh": 100},
        ]}, "quan": {"time_left_ticks": 1}}
        inputs = [{"tick": 0, "interact": True}]
        rows = self.play(scenario, inputs, ticks=2)
        states = snapshots(rows)
        self.assertEqual([(s["phase"], s["phase_tick"]) for s in states],
                         [("gather", 0), ("quan", 0), ("shop", 0)])
        self.assertEqual(states[1]["stock"], events(rows, "gather_end")[0]["data"]["inventory"]["items"])
        self.assertEqual(
            [(x["id"], x["kind"]) for x in states[2]["stock"]],
            [(x["id"], x["kind"]) for x in states[1]["stock"]],
        )
        self.assertEqual(rows[-1]["days_completed"], 0)
        rows = self.play(scenario, inputs)
        self.assertEqual([(r["tick"], r["phase"], r["name"]) for r in events(rows)], [
            (0, "gather", "day_start"), (0, "gather", "day_plan"), (0, "gather", "phase_start"),
            (1, "gather", "gather_end"), (1, "quan", "phase_start"),
            (2, "quan", "quan_end"), (2, "shop", "phase_start"), (602, "shop", "shop_end")])
        self.assertEqual(events(rows, "shop_end")[0]["data"], {"reason": "time"})
        self.assertEqual((rows[-1]["reason"], rows[-1]["days_completed"]), ("days_complete", 1))

    def test_two_days_exact_price_last_tick_and_upgrade_takes_effect_next_day(self):
        scenario = {"day": {"money": 200, "earned": 200}, "quan": {"time_left_ticks": 1}}
        inputs = [
            {"tick": 0, "interact": True}, {"tick": 2, "interact": False},
            {"tick": 601, "buy": "oxygen", "shop_done": True},
            {"tick": 602, "interact": True}, {"tick": 605, "shop_done": False},
            {"tick": 606, "shop_done": True},
        ]
        rows = self.play(scenario, inputs, ticks=610, days=2)
        self.assertEqual(rows, self.play(scenario, inputs, ticks=610, days=2))
        last_shop = [(r["phase"], r["day"], r["name"]) for r in events(rows) if r["tick"] == 602]
        self.assertEqual(last_shop, [("shop", 1, "bought"), ("shop", 1, "shop_end"),
                                     ("gather", 2, "day_start"), ("gather", 2, "day_plan"),
                                     ("gather", 2, "phase_start")])
        self.assertEqual(events(rows, "bought")[0]["data"],
                         {"upgrade": "oxygen", "level": 1, "price": 200, "money": 0})
        self.assertEqual(events(rows, "shop_end")[0]["data"], {"reason": "done"})
        new_day = next(s for s in snapshots(rows) if s["tick"] == 602)
        self.assertEqual(new_day["active_upgrades"], {"oxygen": 1})
        self.assertEqual(new_day["player"]["oxygen_max_ticks"], 2700)
        self.assertEqual(new_day["player"]["oxygen_ticks"], 2700)
        self.assertEqual((rows[-1]["money"], rows[-1]["earned"], rows[-1]["score"]), (0, 200, 500))
        self.assertEqual(rows[-1]["days_completed"], 2)

    def test_pause_updates_edges_and_discards_buy(self):
        scenario = {"gather": {"time_left_ticks": 1}, "quan": {"time_left_ticks": 1}}
        inputs = [
            {"tick": 2, "pause": True, "shop_done": True}, {"tick": 3, "pause": False, "buy": "hp"},
            {"tick": 10, "pause": True, "shop_done": True}, {"tick": 11, "buy": "oxygen"},
            {"tick": 12, "shop_done": False}, {"tick": 13, "shop_done": True},
        ]
        rows = self.play(scenario, inputs, ticks=20)
        paused = next(s for s in snapshots(rows) if s["tick"] == 10)
        self.assertEqual((paused["state"], paused["sim_tick"], paused["phase_tick"], paused["time_left_ticks"]),
                         ("paused", 2, 0, 600))
        self.assertEqual([(r["tick"], r["name"]) for r in events(rows) if r["phase"] == "shop"],
                         [(2, "phase_start"), (3, "paused"), (11, "resumed"),
                          (12, "buy_failed"), (14, "shop_end")])
        self.assertEqual(events(rows, "buy_failed")[0]["data"], {"action": "oxygen", "reason": "funds"})

    def test_hp_upgrade_levels_and_income_carry(self):
        scenario = {"day": {"money": 678, "earned": 678}, "gather": {"time_left_ticks": 1},
                    "quan": {"time_left_ticks": 1, "customers": [
                        {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui", "state": "eating",
                         "order_status": "served", "eat_ticks_left": 1, "base_price": 60, "tip": 12}]}}
        rows = self.play(scenario, days=2, ticks=20, inputs=[
            {"tick": 2, "buy": "hp"}, {"tick": 3, "buy": "hp"}, {"tick": 4, "buy": "hp"},
            {"tick": 5, "buy": "unknown", "shop_done": True},
            {"tick": 7, "shop_done": False}, {"tick": 8, "shop_done": True},
        ])
        self.assertEqual([r["data"]["money"] for r in events(rows, "bought")], [500, 0])
        self.assertEqual([r["data"]["reason"] for r in events(rows, "buy_failed")], ["max_level", "unknown"])
        state = next(s for s in snapshots(rows) if s["day"] == 2 and s["phase"] == "gather")
        self.assertEqual((state["money"], state["earned"], state["reputation"]), (0, 750, 3.2))
        self.assertEqual((state["player"]["hp"], state["player"]["hp_max"]), (5, 5))
        self.assertEqual((rows[-1]["money"], rows[-1]["earned"], rows[-1]["reputation"]), (72, 822, 3.4))

    def test_pause_on_both_standalone_modes(self):
        for mode in ("gather", "quan"):
            with self.subTest(mode=mode):
                rows = self.play({mode: {"time_left_ticks": 1}},
                                 [{"tick": 0, "pause": True}, {"tick": 1, "pause": False},
                                  {"tick": 5, "pause": True}], ticks=10, mode=mode)
                self.assertEqual(rows[-1]["ticks"], 6)
                self.assertEqual(rows[-1]["sim_tick"], 1)
                self.assertEqual([r["name"] for r in events(rows)], ["paused", "resumed", mode + "_end"])

    def test_plan_override_faint_and_dish_filter(self):
        plan = {"day": 1, "dishes": {"lau_mam": 1}}
        scenario = {"day": {"day_plan": [plan]}, "gather": {
            "player": {"pos": [15, 5], "oxygen_ticks": 0, "zero_oxy_ticks": 59, "hp": 1},
            "hold": [{"id": "I1", "kind": "ca_loc", "fresh": 100}]}}
        rows = self.play(scenario, ticks=4)
        self.assertEqual(events(rows, "gather_end")[0]["data"]["reason"], "fainted")
        self.assertEqual(snapshots(rows)[1]["stock"], [])
        plan_event = events(rows, "day_plan")[0]["data"]
        self.assertEqual(plan_event["ingredients"], {"ca_linh": 2, "ca_keo": 1, "keo_neo": 1, "bong_dien_dien": 1})
        scenario["gather"] = {"hold": [{"id": "I1", "kind": "ca_loc", "fresh": 100}], "time_left_ticks": 1}
        rows = self.play(scenario, ticks=121)
        self.assertEqual(len(events(rows, "no_dish")), 1)
        self.assertEqual(events(rows, "customer_arrived"), [])

    def test_invalid_day_data_and_inconsistent_real_stock(self):
        for scenario in (
            {"day": {"money": 200}}, {"day": {"money": 3, "earned": 2}},
            {"day": {"day_plan": [{"day": 1, "dishes": {}}]}},
            {"day": {"upgrades": {"oxygen": 3}}}, {"quan": {"stock": {}}}, {"quan": {"reputation": 3}},
            {"day": {"day_plan": [{"day": 1, "dishes": {"ca_keo_nuong": 1}, "ingredients": {"ca_keo": 3}}]}},
            {"gather": {"time_left_ticks": 1}, "quan": {"customers": [
                {"id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui"}]}},
        ):
            with self.subTest(scenario=scenario):
                self.play(scenario, ticks=2, bad=True)
        self.play({}, inputs=[{"tick": 0, "buy": ""}], ticks=2, bad=True)
        self.play({}, days=0, ticks=0, bad=True)
        self.play({}, days=6, ticks=0, bad=True)
        self.play({}, days=1, ticks=0, mode="quan", bad=True)
        self.play({}, extra=("--inventory-out", "unused.json"), ticks=0, bad=True)
