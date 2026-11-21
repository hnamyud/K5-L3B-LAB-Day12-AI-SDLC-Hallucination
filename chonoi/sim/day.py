"""Vòng ngày. Các ca giữ luật chơi riêng và dùng chung tiền, uy tín."""

from copy import deepcopy

from ..day_plan import compute_ingredients
from ..errors import BadInput
from ..ids import IdAllocator, sort_by_id
from ..inventory import is_v12
from ..scenario import _validate_gather
from .gather import GatherSim
from .quan import QuanSim


def load_day_plans(tuning, overrides):
    menu = tuning["menu"]
    plans = {plan["day"]: plan for plan in tuning["day_plan"]}
    seen = set()
    if not isinstance(overrides, list):
        raise BadInput("day.day_plan phải là mảng")
    for plan in overrides:
        if not isinstance(plan, dict) or set(plan) - {"day", "dishes", "ingredients"}:
            raise BadInput("mục day_plan không hợp lệ")
        day = plan.get("day")
        if type(day) is not int or day not in plans or day in seen:
            raise BadInput("day_plan có Ngày trùng hoặc ngoài danh sách")
        seen.add(day)
        plans[day] = plan

    output = {}
    for day, plan in plans.items():
        dishes = plan.get("dishes")
        ingredients = compute_ingredients(menu, dishes)
        if "ingredients" in plan:
            supplied = plan["ingredients"]
            if (not isinstance(supplied, dict) or any(type(n) is not int for n in supplied.values())
                    or supplied != ingredients):
                raise BadInput(f"ingredients không khớp công thức ở Ngày {day}")
        output[day] = {"dishes": dict(sorted(dishes.items())), "ingredients": dict(sorted(ingredients.items()))}
    return output


class DaySim:
    mode = "day"

    def __init__(self, tuning, scenario, streams, days):
        self.tuning = tuning
        self.scenario = deepcopy(scenario)
        self.streams = streams
        self.ids = IdAllocator()
        self.days = days
        self.day = 1
        self.days_completed = 0
        self.done = False
        self.reason = None
        state = self.scenario.get("day", {})
        self.money = state.get("money", 0)
        self.earned = state.get("earned", 0)
        if (("money" in state) != ("earned" in state) or type(self.money) is not int
                or type(self.earned) is not int or not 0 <= self.money <= self.earned):
            raise BadInput("day cần cả money và earned, với 0 <= money <= earned")
        quan = tuning["quan"]
        self.reputation = state.get("reputation", quan["reputation_initial"])
        if (type(self.reputation) not in (int, float)
                or not quan["reputation_min"] <= self.reputation <= quan["reputation_max"]):
            raise BadInput("day.reputation ngoài miền")
        self.shop = tuning["shop"]
        self.upgrades = state.get("upgrades", {})
        if not isinstance(self.upgrades, dict) or any(
            kind not in self.shop["upgrades"] or type(level) is not int
            or not 0 <= level <= len(self.shop["upgrades"][kind])
            for kind, level in self.upgrades.items()
        ):
            raise BadInput("day.upgrades có cấp không hợp lệ")
        self.plans = load_day_plans(tuning, state.get("day_plan", []))
        self.start_gather()

    def start_gather(self):
        self.phase = "gather"
        self.active_upgrades = dict(self.upgrades)
        gather = dict(self.tuning["gather"])
        for kind, field in (("oxygen", "oxygen_max_s"), ("hp", "hp_max")):
            level = self.active_upgrades.get(kind, 0)
            if level:
                gather[field] = self.shop["upgrades"][kind][level - 1][field]
        tuning = dict(self.tuning, gather=gather)
        fixture = deepcopy(self.scenario.get("gather", {}))
        _validate_gather(fixture, tuning)
        self.fixture_item_ids = {}
        if (self.day > 1 and tuning.get("freshness")
                and is_v12(tuning.get("_contract_version", "1.2"))):
            for item in fixture.get("hold", []):
                new_id = self.ids.new("I")
                self.fixture_item_ids[item["id"]] = new_id
                item["id"] = new_id
        self.shift = GatherSim(tuning, fixture, self.streams, self.ids, day=self.day)
        self.shift.reputation = self.reputation

    def _plan(self):
        return self.plans.get(self.day) or self.plans[(self.day - 1) % len(self.plans) + 1]

    def start_quan(self):
        fixture = deepcopy(self.scenario.get("quan", {}))
        for customer in fixture.get("customers", []):
            reserved = customer.get("reserved")
            if isinstance(reserved, list):
                if any(not isinstance(iid, str) or not iid for iid in reserved):
                    raise BadInput("quan.customers[].reserved cần id cá thể khác rỗng")
                customer["reserved"] = [self.fixture_item_ids.get(iid, iid) for iid in reserved]
        dishes = self._plan()["dishes"]
        menu = {dish: self.tuning["menu"][dish] for dish in dishes}
        tuning = dict(self.tuning, menu=menu)
        self.shift = QuanSim(tuning, fixture, self.streams, self.ids,
                             inventory=self.shift.inventory_items())
        self.shift.money = self.money
        self.shift.earned = self.earned
        self.shift.reputation = self.reputation
        self.phase = "quan"

    @property
    def time_left_ticks(self):
        return self.shop_ticks if self.phase == "shop" else self.shift.time_left_ticks

    def snapshot(self):
        if self.phase == "shop":
            stock = self.shift.stock
            if isinstance(stock, list):
                result = {"stock": [dict(item) for item in sort_by_id(stock)]}
            else:
                result = {"stock": {k: v for k, v in sorted(stock.items()) if v > 0}}
        else:
            result = self.shift.snapshot()
        return dict(result, day=self.day, day_plan=self._plan(),
                    upgrades=dict(self.upgrades), active_upgrades=dict(self.active_upgrades))

    def day_start_events(self):
        return [("day_start", {}), ("day_plan", self._plan()), ("phase_start", {})]

    def step(self, inp):
        if self.phase == "shop":
            return self._step_shop(inp)
        events = self.shift.step(inp)
        if self.phase == "quan":
            self.money = self.shift.money
            self.earned = self.shift.earned
        self.reputation = self.shift.reputation
        if self.shift.done:
            if self.phase == "gather":
                self.start_quan()
            else:
                self.phase = "shop"
                self.shop_ticks = self.shop["max_ticks"]
        return events

    def _step_shop(self, inp):
        self.shop_ticks -= 1
        events = []
        if inp.buy is not None:
            events.append(self._buy(inp.buy))
        close = inp.pressed("shop_done")
        if close or self.shop_ticks == 0:
            events.append(("shop_end", {"reason": "done" if close else "time"}))
            self.days_completed += 1
            if self.days_completed == self.days:
                self.done = True
                self.reason = "days_complete"
            else:
                self.day += 1
                self.start_gather()
        return events

    def _buy(self, action):
        levels = self.shop["upgrades"].get(action)
        level = self.upgrades.get(action, 0)
        if levels is None:
            return "buy_failed", {"action": action, "reason": "unknown"}
        if level == len(levels):
            return "buy_failed", {"action": action, "reason": "max_level"}
        upgrade = levels[level]
        price = upgrade["price"]
        if self.money < price:
            return "buy_failed", {"action": action, "reason": "funds"}
        self.money -= price
        self.upgrades[action] = upgrade["level"]
        return "bought", {"upgrade": action, "level": upgrade["level"], "price": price, "money": self.money}
