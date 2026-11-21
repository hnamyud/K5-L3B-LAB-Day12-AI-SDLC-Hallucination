import unittest
import math
from chonoi.contract import load_contract
from chonoi.inventory import is_v12
from chonoi.runner import Session
from chonoi.inputs import LiveInputs

# Phase 3 (Test Contract v1.2+): giỏ là mảng cá thể {id,kind,fresh}. Test giữ nguyên ý kiểm P1 cho cả hai
# phiên bản: fixture dựng theo version đang bật, so sánh theo loại nguyên liệu.
V12 = is_v12(load_contract()["contract_version"])


def hold_fixture(*kinds):
    return [{"id": f"I{i + 1}", "kind": k, "fresh": 100} for i, k in enumerate(kinds)] if V12 else list(kinds)


def kinds_of(hold):
    return [h if isinstance(h, str) else h["kind"] for h in hold]


class Phase1GameplayTests(unittest.TestCase):
    def setUp(self):
        self.tuning = load_contract()["tuning"]

    def test_gather_dive_surface_and_oxygen(self):
        # Bắt đầu tại mặt nước d=0
        scenario = {"player": {"pos": [20, 0], "oxygen_ticks": 60, "hp": 3}}
        sess = Session("gather", self.tuning, scenario, seed=1)
        li = LiveInputs()

        # Bơi xuống nước cho tới khi d > 0.5 (cần khoảng 20 ticks do ramp)
        li.set(move=[0, 1])
        dive_found = False
        for _ in range(25):
            events = sess.step(li.advance())
            if any(e["name"] == "dive" for e in events):
                dive_found = True
                break
        self.assertTrue(dive_found)
        self.assertFalse(sess.sim._at_surface())

    def test_gather_choke_and_faint(self):
        # Bắt đầu dưới nước với oxy = 1, máu = 1, giữ 1 cá lóc
        scenario = {
            "player": {"pos": [20, 5], "oxygen_ticks": 1, "hp": 1, "zero_oxy_ticks": 0},
            "hold": hold_fixture("ca_loc"),
        }
        sess = Session("gather", self.tuning, scenario, seed=1)
        li = LiveInputs()

        # Tick 1: oxy về 0, phát oxygen_empty
        events = sess.step(li.advance())
        self.assertTrue(any(e["name"] == "oxygen_empty" for e in events))
        self.assertEqual(sess.sim.oxygen_ticks, 0)

        # 59 tick tiếp theo dưới nước -> tick thứ 60 ngạt (choke) -> máu về 0 -> faint
        faint_found = False
        for _ in range(59):
            evs = sess.step(li.advance())
            if any(e["name"] == "faint" for e in evs):
                faint_found = True
                break
        self.assertTrue(faint_found)
        self.assertTrue(sess.done)
        self.assertEqual(sess.sim.reason, "fainted")
        self.assertEqual(sess.sim.hold, [])

    def test_gather_interact_flower(self):
        # N1 tại [12, 0] là bong_dien_dien
        scenario = {
            "player": {"pos": [12, 0]},
            "nodes": [{"id": "N1", "kind": "bong_dien_dien", "pos": [12, 0], "regrow_ticks": 0}],
            "hold": []
        }
        sess = Session("gather", self.tuning, scenario, seed=1)
        li = LiveInputs()
        li.set(interact=True)
        events = sess.step(li.advance())
        self.assertTrue(any(e["name"] == "gather" for e in events))
        self.assertEqual(kinds_of(sess.sim.hold), ["bong_dien_dien"])
        if V12:  # hàng mới fresh = 100, chưa hao trong bước nhận
            self.assertEqual(float(sess.sim.hold[0]["fresh"]), 100.0)

    def test_gather_catch_fish(self):
        # F1 tại [15, 5] là ca_linh (yield=3)
        scenario = {
            "player": {"pos": [15, 5]},
            "fish": [{"id": "F1", "kind": "ca_linh", "pos": [15, 5], "heading_deg": 0}],
            "hold": []
        }
        sess = Session("gather", self.tuning, scenario, seed=1)
        li = LiveInputs()
        li.set(catch=True)
        events = sess.step(li.advance())
        self.assertTrue(any(e["name"] == "fish_caught" for e in events))
        self.assertEqual(len(sess.sim.hold), 3)
        self.assertEqual(kinds_of(sess.sim.hold), ["ca_linh", "ca_linh", "ca_linh"])

    def test_quan_cook_serve_and_pay(self):
        # Bếp B1 tại [2, 8], bàn T1 tại [9, 2]
        # Khách C1 tại T1 đặt ca_loc_nuong_trui
        scenario = {
            "stock": {"ca_loc": 1},
            "player": {"pos": [2, 8]},
            "customers": [{
                "id": "C1", "table_id": "T1", "dish_id": "ca_loc_nuong_trui",
                "order_tick": 0, "state": "waiting", "patience_ticks_left": 3600,
                "order_status": "reserved", "reserved": {"ca_loc": 1}
            }]
        }
        sess = Session("quan", self.tuning, scenario, seed=1)
        li = LiveInputs()

        # 1. Tại bếp B1, nhấn interact để bắt đầu nấu
        li.set(interact=True)
        events = sess.step(li.advance())
        self.assertTrue(any(e["name"] == "cook_started" for e in events))
        self.assertEqual(sess.sim.stock.get("ca_loc", 0), 0)

        # 2. Đợi nấu chín (cook_s = 6s = 360 ticks)
        li.set(interact=False)
        ready_found = False
        for _ in range(360):
            evs = sess.step(li.advance())
            if any(e["name"] == "dish_ready" for e in evs):
                ready_found = True
        self.assertTrue(ready_found)

        # 3. Lấy món vào tay
        li.set(interact=True)
        events = sess.step(li.advance())
        self.assertTrue(any(e["name"] == "dish_picked" for e in events))
        self.assertIsNotNone(sess.sim.hand)

        # Nhả nút interact trước khi bấm lại
        li.set(interact=False)
        sess.step(li.advance())

        # 4. Di chuyển tới bàn T1 [9, 2]
        sess.sim.pos = [9, 2]
        li.set(interact=True)
        events = sess.step(li.advance())
        self.assertTrue(any(e["name"] == "served" for e in events))
        self.assertIsNone(sess.sim.hand)

        # 5. Khách ăn xong (eat_s = 10s = 600 ticks) -> trả tiền
        li.set(interact=False)
        paid_found = False
        for _ in range(600):
            evs = sess.step(li.advance())
            if any(e["name"] == "paid" for e in evs):
                paid_found = True
                break
        self.assertTrue(paid_found)
        self.assertGreater(sess.sim.money, 0)


if __name__ == "__main__":
    unittest.main()
