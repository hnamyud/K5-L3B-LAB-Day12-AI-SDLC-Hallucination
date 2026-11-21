import copy
from fractions import Fraction
import json
import math
import os
import subprocess
import sys
import unittest

from chonoi.contract import load_contract, validate_tuning
from chonoi.errors import BadInput
from chonoi.ids import IdAllocator
from chonoi.inventory import (
    count_by_kind,
    decay_items,
    export_items,
    is_spoiled,
    is_v12,
    make_item,
    parse_fresh,
    price_for_items,
    read_inventory,
    read_inventory_v12,
    select_freshest,
    sort_cook_items,
    tip_for_price,
    validate_item_list,
    write_inventory,
    write_inventory_v12,
)
from helpers import ROOT, Workdir, write_json


class InventoryV12Tests(unittest.TestCase):
    def test_adjacent_floats_preserve_spoilage_and_price_branches(self):
        below = math.nextafter(30.0, 0.0)
        above = math.nextafter(30.0, 100.0)
        self.assertTrue(is_spoiled(below))
        self.assertFalse(is_spoiled(above))
        self.assertEqual(
            price_for_items(100, [{"id": "I1", "kind": "ca_loc",
                                   "fresh": math.nextafter(100.0, 0.0)}]),
            99,
        )
        with Workdir() as work:
            path = work.path("threshold.json")
            write_inventory_v12(path, [{"id": "I1", "kind": "ca_loc", "fresh": below}])
            self.assertEqual(read_inventory_v12(path)[0]["fresh"], below)

    def test_contract_version_selects_gather_schema_with_freshness_config_present(self):
        from chonoi.inputs import InputState
        from chonoi.rng import Streams
        from chonoi.scenario import _validate_gather
        from chonoi.sim.gather import GatherSim

        contract = load_contract()
        legacy = {"hold": ["ca_loc"], "monsters": [], "random_fish": False}
        individuals = {"hold": [{"id": "I1", "kind": "ca_loc", "fresh": 30}],
                       "monsters": [], "random_fish": False}
        with Workdir() as work:
            for version, fixture in (("1.1", legacy), ("1.2", individuals)):
                contract["contract_version"] = version
                path = write_json(work.path("contract.json"), contract)
                tuning = load_contract(path)["tuning"]
                _validate_gather(fixture, tuning)
                with self.assertRaises(BadInput):
                    _validate_gather(individuals if version == "1.1" else legacy, tuning)
                sim = GatherSim(tuning, fixture, Streams(1), IdAllocator())
                emitted = sim.step(InputState((0, 0), {}, set()))
                self.assertEqual(any(name == "spoiled" for name, _ in emitted), version == "1.2")

    def test_contract_has_freshness_and_validates_bounds(self):
        contract = load_contract()
        self.assertEqual(
            contract["tuning"]["freshness"],
            {"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 30},
        )
        self.assertFalse(is_v12("1.1"))
        self.assertTrue(is_v12("1.2"))

        bad_cases = [
            {"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25},  # thiếu khóa
            {"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 30, "extra": 1},
            {"initial": True, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 30},
            {"initial": 100, "gather_decay_per_s": 0, "quan_decay_per_s": 0.25, "spoiled_below": 30},
            {"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": -0.1, "spoiled_below": 30},
            {"initial": 100, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 100},
            {"initial": 101, "gather_decay_per_s": 0.5, "quan_decay_per_s": 0.25, "spoiled_below": 30},
            {"initial": 100, "gather_decay_per_s": float("nan"), "quan_decay_per_s": 0.25, "spoiled_below": 30},
        ]
        for bad_fresh in bad_cases:
            t = copy.deepcopy(contract["tuning"])
            t["freshness"] = bad_fresh
            with self.assertRaises(BadInput):
                validate_tuning(t)

        with Workdir() as w:
            bad_contract = copy.deepcopy(contract)
            bad_contract["contract_version"] = "9.9"
            p = write_json(w.path("contract.json"), bad_contract)
            with self.assertRaises(BadInput):
                load_contract(p)

            v13_contract = copy.deepcopy(contract)
            v13_contract["contract_version"] = "1.3"
            v13_contract["bench_cmd"] = "python3 -m chonoi.bench"
            v13_contract["soak_cmd"] = "python3 -m chonoi.soak"
            p13 = write_json(w.path("contract_v13.json"), v13_contract)
            self.assertEqual(load_contract(p13)["contract_version"], "1.3")

            for bad_cmd_key in ("bench_cmd", "soak_cmd"):
                bad_v13 = copy.deepcopy(v13_contract)
                bad_v13[bad_cmd_key] = "   "
                pb = write_json(w.path(f"bad_{bad_cmd_key}.json"), bad_v13)
                with self.assertRaises(BadInput):
                    load_contract(pb)

    def test_v12_roundtrip_id_sort_and_atomic_write(self):
        with Workdir() as w:
            path = w.path("inv.json")
            # Thứ tự hold (LIFO): I10 trước I2
            items = [
                {"id": "I10", "kind": "ca_loc", "fresh": 97.5},
                {"id": "I2", "kind": "ca_linh", "fresh": 100},
            ]
            write_inventory_v12(path, items)
            with open(path, encoding="utf-8") as f:
                raw = f.read()
            self.assertEqual(
                json.loads(raw),
                {"items": [{"id": "I2", "kind": "ca_linh", "fresh": 100}, {"id": "I10", "kind": "ca_loc", "fresh": 97.5}]},
            )
            # Chỉ còn đúng 1 file inv.json, không sót file .tmp
            self.assertEqual(os.listdir(os.path.dirname(path)), ["inv.json"])
            loaded = read_inventory(path, contract_version="1.2")
            self.assertEqual([x["id"] for x in loaded], ["I2", "I10"])

            # Kho rỗng hợp lệ
            empty_path = w.path("empty.json")
            write_inventory_v12(empty_path, [])
            self.assertEqual(read_inventory_v12(empty_path), [])
            with open(empty_path, encoding="utf-8") as f:
                self.assertEqual(f.read(), '{"items":[]}\n')

            # Nếu ghi lỗi kiểu dữ liệu, không đè hỏng file cũ
            with self.assertRaises(BadInput):
                write_inventory_v12(path, {"ca_loc": 1})
            self.assertEqual([x["id"] for x in read_inventory_v12(path)], ["I2", "I10"])

    def test_v12_rejects_invalid_schemas_and_keeps_v11_compatibility(self):
        with Workdir() as w:
            # v1.1 kho đếm vẫn hoạt động khi contract_version="1.1"
            p_v11 = write_json(w.path("v11.json"), {"items": {"ca_loc": 2, "bong_sung": 1}})
            self.assertEqual(read_inventory(p_v11, contract_version="1.1"), {"ca_loc": 2, "bong_sung": 1})
            out_v11 = w.path("out_v11.json")
            write_inventory(out_v11, {"ca_loc": 2, "bong_sung": 0})
            self.assertEqual(read_inventory(out_v11, contract_version="1.1"), {"ca_loc": 2})

            # Ở v1.2, kho đếm bị từ chối bằng BadInput
            with self.assertRaises(BadInput):
                read_inventory(p_v11, contract_version="1.2")

            bad_payloads = [
                {"items": [], "extra": 1},
                {"wrong": []},
                {"items": [{"id": "I1", "kind": "ca_linh", "fresh": 100}, {"id": "I1", "kind": "ca_loc", "fresh": 90}]},
                {"items": [{"id": "", "kind": "ca_linh", "fresh": 100}]},
                {"items": [{"id": 123, "kind": "ca_linh", "fresh": 100}]},
                {"items": [{"id": "I1", "kind": "tom_hum", "fresh": 100}]},
                {"items": [{"id": "I1", "kind": "ca_linh", "fresh": True}]},
                {"items": [{"id": "I1", "kind": "ca_linh", "fresh": -0.1}]},
                {"items": [{"id": "I1", "kind": "ca_linh", "fresh": 100.1}]},
                {"items": [{"id": "I1", "kind": "ca_linh"}]},
                {"items": [{"id": "I1", "kind": "ca_linh", "fresh": 100, "x": 1}]},
            ]
            for idx, payload in enumerate(bad_payloads):
                bp = write_json(w.path(f"bad_{idx}.json"), payload)
                with self.assertRaises(BadInput, msg=f"payload #{idx} phải bị từ chối"):
                    read_inventory_v12(bp)

            # NaN / Infinity thô trong JSON cũng phải bị từ chối
            for raw_bad in ('{"items":[{"id":"I1","kind":"ca_linh","fresh":NaN}]}',
                            '{"items":[{"id":"I1","kind":"ca_linh","fresh":Infinity}]}',
                            '{"items":[{"id":"I1","kind":"ca_linh","fresh":-Infinity}]}'):
                rp = w.path("raw_bad.json")
                with open(rp, "w", encoding="utf-8") as f:
                    f.write(raw_bad)
                with self.assertRaises(BadInput):
                    read_inventory_v12(rp)

    def test_v12_sample_fixture_is_valid(self):
        sample = os.path.join(ROOT, "docs", "contracts", "inventory.v12.sample.json")
        loaded = read_inventory_v12(sample)
        self.assertEqual(
            loaded,
            [{"id": "I1", "kind": "ca_linh", "fresh": 100}, {"id": "I2", "kind": "ca_loc", "fresh": 97.5}],
        )

    def test_freshness_decay_threshold_30_and_roundtrip_precision(self):
        # Đúng fresh=30: ươn ngay ở bước gather đầu tiên, chỉ phát 1 lần
        hold = [{"id": "I1", "kind": "ca_linh", "fresh": 30}]
        s1 = decay_items(hold, decay_per_s=0.5)
        self.assertEqual([x["id"] for x in s1], ["I1"])
        self.assertTrue(is_spoiled(hold[0]["fresh"]))
        s2 = decay_items(hold, decay_per_s=0.5)
        self.assertEqual(s2, [])

        # Gather từ fresh=100: đúng tick 8400 là 30.0 (chưa ươn), tick 8401 mới ươn
        g_items = [{"id": "I1", "kind": "ca_loc", "fresh": 100}]
        for _ in range(8400):
            self.assertEqual(decay_items(g_items, decay_per_s=0.5), [])
        self.assertEqual(g_items[0]["fresh"], 30)
        self.assertFalse(is_spoiled(g_items[0]["fresh"]))
        self.assertEqual([x["id"] for x in decay_items(g_items, decay_per_s=0.5)], ["I1"])

        # Quán từ fresh=100: đúng tick 16800 là 30.0 (chưa ươn), tick 16801 mới ươn
        q_items = [{"id": "I1", "kind": "ca_loc", "fresh": 100}]
        for _ in range(16800):
            self.assertEqual(decay_items(q_items, decay_per_s=0.25), [])
        self.assertEqual(q_items[0]["fresh"], 30)
        self.assertEqual([x["id"] for x in decay_items(q_items, decay_per_s=0.25)], ["I1"])

        # Kẹp đáy 0
        zero_items = [{"id": "I1", "kind": "ca_loc", "fresh": 0}]
        self.assertEqual(decay_items(zero_items, decay_per_s=0.5), [])
        self.assertEqual(zero_items[0]["fresh"], 0)

        # Kiểm tra bảo toàn lưới 1/240 xuyên gather -> file JSON -> quan
        with Workdir() as w:
            inv_path = w.path("handover.json")
            # 1 tick gather -> 100 - 2/240 = 23998/240 = 99.99166666666666
            handover = [{"id": "I1", "kind": "ca_loc", "fresh": 100}]
            decay_items(handover, decay_per_s=0.5)
            write_inventory_v12(inv_path, handover)
            reloaded = read_inventory_v12(inv_path)
            self.assertEqual(parse_fresh(reloaded[0]["fresh"]), Fraction(23998, 240))
            # Còn 23998 - 7200 = 16798 đơn vị trên ngưỡng 30 -> đúng 16798 tick ở quán là 30.0, tick 16799 mới ươn
            for _ in range(16798):
                self.assertEqual(decay_items(reloaded, decay_per_s=0.25), [])
            self.assertEqual(reloaded[0]["fresh"], 30)
            self.assertEqual([x["id"] for x in decay_items(reloaded, decay_per_s=0.25)], ["I1"])

        # Số thập phân tùy ý sát ngưỡng 30 không bị làm tròn sai nhánh
        self.assertFalse(is_spoiled(30.0001))
        self.assertTrue(is_spoiled(29.9999))
        near = [{"id": "I1", "kind": "ca_linh", "fresh": 30.0001}]
        self.assertEqual([x["id"] for x in decay_items(near, decay_per_s=0.5)], ["I1"])

    def test_decay_preserves_lifo_order_and_sorts_spoiled_by_id_key(self):
        # Giữ nguyên thứ tự hold [I10, I2] cho LIFO, nhưng event spoiled trả [I2, I10]
        hold = [
            {"id": "I10", "kind": "ca_loc", "fresh": 30},
            {"id": "I2", "kind": "ca_linh", "fresh": 30},
        ]
        spoiled = decay_items(hold, decay_per_s=0.5)
        self.assertEqual([x["id"] for x in spoiled], ["I2", "I10"])
        self.assertEqual([x["id"] for x in hold], ["I10", "I2"])
        self.assertEqual([x["id"] for x in export_items(hold)], ["I2", "I10"])

    def test_id_allocator_and_make_item_continue_after_deletion(self):
        ids = IdAllocator()
        ids.reserve_all([{"id": "I2"}, {"id": "I10"}])
        i11 = make_item(ids, "ca_linh")
        self.assertEqual(i11, {"id": "I11", "kind": "ca_linh", "fresh": 100})
        # Kể cả khi bỏ I11, lần cấp kế vẫn là I12
        i12 = make_item(ids, "bong_sung", fresh=95.5)
        self.assertEqual(i12, {"id": "I12", "kind": "bong_sung", "fresh": 95.5})

    def test_selection_pricing_tip_and_cook_order(self):
        stock = [
            {"id": "I1", "kind": "bong_sung", "fresh": 29.5},   # ươn -> bỏ qua
            {"id": "I10", "kind": "bong_sung", "fresh": 90},
            {"id": "I2", "kind": "bong_sung", "fresh": 90},    # hòa fresh -> I2 trước I10
            {"id": "I3", "kind": "bong_sung", "fresh": 95},    # tươi nhất
            {"id": "I4", "kind": "ca_loc", "fresh": 80},
        ]
        self.assertEqual(count_by_kind(stock), {"bong_sung": 4, "ca_loc": 1})
        picked = select_freshest(stock, "bong_sung", 2)
        self.assertEqual([x["id"] for x in picked], ["I3", "I2"])
        # Loại trừ I3
        picked_excl = select_freshest(stock, "bong_sung", 2, exclude_ids={"I3"})
        self.assertEqual([x["id"] for x in picked_excl], ["I2", "I10"])
        # Không đủ do I1 bị ươn
        self.assertIsNone(select_freshest(stock, "bong_sung", 4))

        # Giá: floor(listed * avg_fresh / 100)
        # Ví dụ: niêm yết 40, dùng I3(95) và I2(90) -> avg = 92.5 -> 40 * 92.5 / 100 = 37
        base = price_for_items(40, picked)
        self.assertEqual(base, 37)
        # Boa: floor(37 * 0.2) = 7
        self.assertEqual(tip_for_price(base, 0.2), 7)

        # Kiểm biên floor chính xác với Fraction (tránh lỗi 0.9999999999999999)
        # 3 món có fresh = 100 - 2/240, 100 - 2/240, 100 - 2/240 -> avg < 100 -> floor(60 * avg / 100) = 59
        almost = [
            {"id": "I1", "kind": "ca_loc", "fresh": float(Fraction(23998, 240))},
        ]
        self.assertEqual(price_for_items(60, almost), 59)

        # cook_started.items sắp theo (kind, id_key)
        cook_items = sort_cook_items([
            {"id": "I10", "kind": "ca_linh", "fresh": 90},
            {"id": "I2", "kind": "ca_linh", "fresh": 95},
            {"id": "I5", "kind": "bong_dien_dien", "fresh": 80},
        ])
        self.assertEqual([(x["kind"], x["id"]) for x in cook_items], [
            ("bong_dien_dien", "I5"),
            ("ca_linh", "I2"),
            ("ca_linh", "I10"),
        ])

        # Kiểm cross-container seen_ids
        with self.assertRaises(BadInput):
            seen = set()
            validate_item_list([{"id": "I1", "kind": "ca_loc", "fresh": 100}], seen_ids=seen)
            validate_item_list([{"id": "I1", "kind": "ca_linh", "fresh": 100}], seen_ids=seen)

    def test_headless_cli_v11_inventory_still_works(self):
        ver = load_contract().get("contract_version", "1.1")
        with Workdir() as w:
            inv = write_json(w.path("inv.json"), {"items": {"ca_loc": 1}})
            out = w.path("quan.jsonl")
            r = subprocess.run(
                [sys.executable, "-m", "chonoi.headless", "--mode", "quan", "--seed", "1",
                 "--ticks", "1", "--inventory", inv, "--out", out],
                cwd=ROOT, capture_output=True, text=True,
            )
            if is_v12(ver):
                self.assertEqual(r.returncode, 2, r.stderr)
            else:
                self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
