import json
import unittest

from helpers import Workdir, events, frames, read_jsonl, run_headless, snapshots, write_json


class GatherSurvival(unittest.TestCase):
    def run_gather(self, workdir, scenario, inputs, ticks):
        scenario_path = write_json(workdir.path("scenario.json"), {"gather": scenario})
        inputs_path = write_json(workdir.path("inputs.json"), inputs)
        output = workdir.path("gather.jsonl")
        inventory = workdir.path("inventory.json")
        code, stderr = run_headless(
            "--mode", "gather", "--seed", "1", "--ticks", str(ticks),
            "--scenario", scenario_path, "--inputs", inputs_path,
            "--snapshot-every", "1", "--out", output, "--inventory-out", inventory,
        )
        self.assertEqual(code, 0, stderr)
        return read_jsonl(output), inventory

    def test_diving_to_zero_oxygen_counts_as_first_choke_tick(self):
        with Workdir() as workdir:
            rows, _ = self.run_gather(
                workdir, {"player": {"pos": [20, 0.5], "oxygen_ticks": 1}},
                frames({"tick": 0, "move": [0, 1]}), 61,
            )
        self.assertEqual(
            [(row["tick"], row["name"]) for row in rows if row["type"] == "event"],
            [(1, "dive"), (1, "oxygen_empty"), (60, "choke")],
        )
        self.assertEqual(events(rows, "choke")[0]["data"], {"hp": 2})

    def test_surfacing_on_choke_tick_refills_and_clears_counter(self):
        with Workdir() as workdir:
            rows, _ = self.run_gather(
                workdir, {"player": {"pos": [20, 0.51], "oxygen_ticks": 0, "zero_oxy_ticks": 59}},
                frames({"tick": 0, "move": [0, -1]}), 1,
            )
        player = snapshots(rows)[-1]["player"]
        self.assertEqual(len(events(rows, "surface")), 1)
        self.assertEqual(events(rows, "choke"), [])
        self.assertEqual((player["oxygen_ticks"], player["zero_oxy_ticks"], player["hp"]), (6, 0, 3))

    def test_fainting_preempts_docking_and_timeout_and_exports_empty_inventory(self):
        with Workdir() as workdir:
            rows, inventory = self.run_gather(
                workdir,
                {"player": {"pos": [2, 1], "hp": 1, "oxygen_ticks": 0, "zero_oxy_ticks": 59},
                 "hold": [
                     {"id": "I1", "kind": "ca_loc", "fresh": 100},
                     {"id": "I2", "kind": "bong_sung", "fresh": 100},
                     {"id": "I3", "kind": "ca_linh", "fresh": 100},
                 ],
                 "time_left_ticks": 1},
                frames({"tick": 0, "interact": True}), 2,
            )
            with open(inventory, encoding="utf-8") as saved:
                self.assertEqual(json.load(saved), {"items": []})
        self.assertEqual(
            [row["name"] for row in rows if row["type"] == "event"],
            ["choke", "faint", "gather_end"],
        )
        faint_data = events(rows, "faint")[0]["data"]
        self.assertEqual(faint_data["cause"], "choke")
        self.assertEqual(faint_data["hp"], 0)
        self.assertEqual([x["kind"] for x in faint_data["lost"]], ["ca_linh", "bong_sung", "ca_loc"])
        self.assertEqual(events(rows, "gather_end")[0]["data"], {
            "reason": "fainted", "inventory": {"items": []},
        })
        self.assertEqual(snapshots(rows)[-1]["hold"], [])
        self.assertEqual((rows[-1]["ticks"], rows[-1]["reason"]), (1, "fainted"))
