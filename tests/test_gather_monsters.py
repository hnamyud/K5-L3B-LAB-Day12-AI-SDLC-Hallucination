import json
import unittest

from helpers import Workdir, events, frames, read_jsonl, run_headless, snapshots, write_json
from chonoi.ids import IdAllocator
from chonoi.rng import Streams
from chonoi.sim.gather import GatherSim


def monster(mid="M1", pos=None, **updates):
    result = {
        "id": mid, "kind": "ca_sau", "pos": pos or [50, 20],
        "waypoints": [[50, 20], [54, 20]],
    }
    result.update(updates)
    return result


class Monsters(unittest.TestCase):
    def run_case(self, scenario, ticks=1):
        with Workdir() as work:
            source = write_json(work.path("scenario.json"), {"gather": scenario})
            output = work.path("result.jsonl")
            inventory = work.path("stock.json")
            code, stderr = run_headless(
                "--mode", "gather", "--seed", "7", "--ticks", str(ticks),
                "--scenario", source, "--out", output, "--snapshot-every", "1",
                "--inventory-out", inventory,
            )
            self.assertEqual(code, 0, stderr)
            rows = read_jsonl(output)
            saved = None
            if rows[-1]["reason"] != "tick_limit":
                with open(inventory, encoding="utf-8") as file:
                    saved = json.load(file)
            return rows, saved

    def test_hit_tie_lifo_and_recoil(self):
        rows, _ = self.run_case({
            "player": {"pos": [50, 20]}, "monsters": [monster("M10"), monster("M2")],
            "hold": [
                {"id": "I1", "kind": "ca_loc", "fresh": 100},
                {"id": "I2", "kind": "bong_sung", "fresh": 100},
                {"id": "I3", "kind": "ca_linh", "fresh": 100},
                {"id": "I4", "kind": "ca_loc", "fresh": 100},
                {"id": "I5", "kind": "bong_sung", "fresh": 100},
            ],
        }, 61)
        hit = events(rows, "monster_hit")
        self.assertEqual(len(hit), 1)
        self.assertEqual(hit[0]["data"]["monster_id"], "M2")
        self.assertEqual([x["kind"] for x in hit[0]["data"]["lost"]], ["bong_sung", "ca_loc"])
        by_tick = {s["tick"]: s for s in snapshots(rows)}
        recoiling = by_tick[1]["monsters"][0]
        self.assertEqual((recoiling["state"], recoiling["state_ticks_left"]), ("recoil", 60))
        self.assertEqual(recoiling["recoil_dir"], [1.0, 0.0])
        self.assertEqual(by_tick[60]["monsters"][0]["state"], "recoil")
        self.assertEqual(by_tick[61]["monsters"][0]["state"], "patrol")
        self.assertAlmostEqual(by_tick[61]["monsters"][0]["pos"][0], 52, places=3)

    def test_monster_faint_loses_remainder_and_saves_empty_stock(self):
        rows, saved = self.run_case({
            "player": {"pos": [50, 20], "hp": 1}, "monsters": [monster()],
            "hold": [
                {"id": "I1", "kind": "ca_loc", "fresh": 100},
                {"id": "I2", "kind": "bong_sung", "fresh": 100},
                {"id": "I3", "kind": "ca_linh", "fresh": 100},
            ],
            "time_left_ticks": 1,
        })
        self.assertEqual([r["name"] for r in rows if r["type"] == "event"],
                         ["monster_hit", "faint", "gather_end"])
        self.assertEqual([x["kind"] for x in events(rows, "monster_hit")[0]["data"]["lost"]], ["ca_linh"])
        faint_data = events(rows, "faint")[0]["data"]
        self.assertEqual((faint_data["cause"], faint_data["hp"]), ("monster", 0))
        self.assertEqual([x["kind"] for x in faint_data["lost"]], ["bong_sung", "ca_loc"])
        self.assertEqual(saved, {"items": []})
        self.assertEqual(rows[-1]["reason"], "fainted")

    def test_choke_ignores_invulnerability_and_keeps_hold(self):
        rows, _ = self.run_case({
            "player": {"pos": [50, 20], "oxygen_ticks": 0,
                       "zero_oxy_ticks": 59, "invuln_ticks": 30},
            "monsters": [monster()],
            "hold": [{"id": "I1", "kind": "ca_loc", "fresh": 100}],
        })
        self.assertEqual(events(rows, "choke")[0]["data"], {"hp": 2})
        self.assertEqual(events(rows, "monster_hit"), [])
        self.assertEqual([x["kind"] for x in snapshots(rows)[-1]["hold"]], ["ca_loc"])

    def test_choke_precedes_hit_in_same_step(self):
        rows, _ = self.run_case({
            "player": {"pos": [50, 20], "oxygen_ticks": 0, "zero_oxy_ticks": 59},
            "monsters": [monster()],
        })
        self.assertEqual([r["name"] for r in rows if r["type"] == "event"],
                         ["choke", "monster_hit"])
        self.assertEqual(snapshots(rows)[-1]["player"]["hp"], 1)

    def test_invulnerability_expires_before_hit(self):
        rows, _ = self.run_case({
            "player": {"pos": [50, 20], "invuln_ticks": 2}, "monsters": [monster()],
        }, 2)
        self.assertEqual(events(rows, "monster_hit")[0]["tick"], 2)

    def test_patrol_arrival_and_chase_exit(self):
        rows, _ = self.run_case({
            "player": {"pos": [2, 0]},
            "monsters": [monster(pos=[53.99, 20])],
        })
        current = snapshots(rows)[-1]["monsters"][0]
        self.assertEqual(current["pos"], [54.0, 20.0])
        self.assertEqual(current["target_idx"], 0)
        rows, _ = self.run_case({
            "player": {"pos": [50, 9.99]},
            "monsters": [monster(state="chase")],
        })
        self.assertEqual(snapshots(rows)[-1]["monsters"][0]["state"], "patrol")
        self.assertEqual(events(rows, "monster_hit"), [])

    def test_recoil_clamps_map_and_depth(self):
        rows, _ = self.run_case({
            "monsters": [monster(pos=[100, 30], state="recoil",
                                 state_ticks_left=1, recoil_dir=[1, 0])],
        })
        self.assertEqual(snapshots(rows)[-1]["monsters"][0]["pos"], [100, 30])

    def test_default_spawns_by_day_and_empty_override(self):
        with open("game.contract.json", encoding="utf-8") as file:
            tuning = json.load(file)["tuning"]
        for day, expected in ((1, ["M1"]), (2, ["M1"]), (3, ["M1", "M2"])):
            sim = GatherSim(tuning, {}, Streams(1), IdAllocator(), day=day)
            self.assertEqual([m["id"] for m in sim.snapshot()["monsters"]], expected)
        sim = GatherSim(tuning, {"monsters": []}, Streams(1), IdAllocator(), day=3)
        self.assertEqual(sim.monsters, [])

    def test_bad_monster_fixtures_exit_2(self):
        bad = [
            monster(target_idx=True), monster(state="recoil", state_ticks_left=0),
            monster(state="recoil", state_ticks_left=2, recoil_dir=[2, 0]),
            monster(pos=[50, 9]), monster(state="chase", recoil_dir=[1, 0]),
            monster(unknown=1), monster(waypoints=[[50, 20]]), monster(kind=[]),
        ]
        with Workdir() as work:
            for fixture in bad:
                source = write_json(work.path("bad.json"), {"gather": {"monsters": [fixture]}})
                code, _ = run_headless(
                    "--mode", "gather", "--seed", "1", "--ticks", "1",
                    "--scenario", source, "--out", work.path("out.jsonl"),
                )
                self.assertEqual(code, 2, fixture)


if __name__ == "__main__":
    unittest.main()
