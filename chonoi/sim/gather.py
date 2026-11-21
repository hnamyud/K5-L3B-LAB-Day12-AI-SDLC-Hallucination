"""Buổi sáng — Lặn & Hái (`gather`).

Mặt cắt dòng sông nhìn NGANG: vị trí `[x, d]` (x sang phải, `d` độ sâu hướng xuống, d = 0 là mặt nước).
`move = [x, d]`: thành phần thứ hai DƯƠNG = bơi xuống. Hướng mặt là góc từ +x, dương = xuống.

Nhóm viết tiếp theo thứ tự một bước trong Test Contract, mục F (Gather):
  TODO(nhóm, lát 2): hái + bắt cá + cập bến + kho
      - hái nút ở mặt nước (gather, hold_full), nút mọc lại (node_regrown đã có phần đếm ngược)
      - bắt đàn cá bằng `catch` (fish_caught, hold_full, hồi chiêu catch_cd_ticks, chỉ khi dưới nước)
      - cập bến xét TRƯỚC hái (đã có); ghi kho đúng một lần do runner lo
Các tính năng của phase sau chưa nằm trong khung này.
"""

import math

from ..ids import id_key, sort_by_id
from ..inventory import hold_to_items, is_v12
from .ramp import ramp_velocity

TICK = 60.0
AXES = ("x", "d")


class GatherSim:
    mode = "gather"
    phase = "gather"

    def __init__(self, tuning, scenario, streams, ids, day=1):
        self.day = day
        t = tuning["gather"]
        self.t = t
        self.rng = streams
        self.ids = ids
        p = scenario.get("player", {})
        self.pos = [float(c) for c in p.get("pos", t["start_pos"])]
        self.vel = [float(c) for c in p.get("vel", [0.0, 0.0])]
        self._tgt = None
        self._ramp_left = 0
        self.heading = float(p.get("heading_deg", t["start_heading_deg"]))
        self.oxygen_max = int(round(t["oxygen_max_s"] * TICK))
        self.oxygen_ticks = p.get("oxygen_ticks", self.oxygen_max)
        self.hp = p.get("hp", t["hp_max"])
        self.zero_oxy_ticks = p.get("zero_oxy_ticks", 0)
        self.invuln_ticks = p.get("invuln_ticks", 0)
        self.catch_cd_ticks = p.get("catch_cd_ticks", 0)
        self.freshness = tuning.get("freshness") if is_v12(tuning.get("_contract_version", "1.2")) else None
        self._fresh_units = {}
        self.hold = self._init_hold(scenario.get("hold", []), ids)
        self.monster_tuning = t.get("monsters")
        self.monsters = []
        if self.monster_tuning:
            spawns = scenario.get("monsters", [
                m for m in self.monster_tuning["spawns"] if m["from_day"] <= day
            ])
            for monster in spawns:
                self.monsters.append({
                    "id": monster["id"], "kind": monster["kind"],
                    "pos": list(monster["pos"]),
                    "waypoints": [list(point) for point in monster["waypoints"]],
                    "target_idx": monster.get("target_idx", 1),
                    "state": monster.get("state", "patrol"),
                    "state_ticks_left": monster.get("state_ticks_left", 0),
                    "recoil_dir": monster.get("recoil_dir"),
                })
                ids.reserve(monster["id"])
        self.time_left_ticks = scenario.get("time_left_ticks", int(round(t["duration_s"] * TICK)))
        self.phase_tick = 0
        self.random_fish = bool(scenario.get("random_fish", True))
        # nút và đàn cá: scenario THAY THẾ danh sách mặc định; random_fish=false tắt cá mặc định
        src_nodes = scenario["nodes"] if "nodes" in scenario else t["nodes"]
        self.nodes = [{"id": n["id"], "kind": n["kind"], "pos": [float(c) for c in n["pos"]],
                       "regrow_ticks": n.get("regrow_ticks", 0)} for n in src_nodes]
        for n in self.nodes:
            ids.reserve(n["id"])
        self.fish = self._init_fish(scenario, t, ids)
        self.money = 0
        self.earned = 0
        self.reputation = tuning["quan"]["reputation_initial"]
        self.done = False
        self.reason = None

    # --- giao diện cho runner -------------------------------------------------
    def inventory_items(self):
        if self.freshness:
            return [dict(item) for item in sort_by_id(self.hold)]
        return hold_to_items(self.hold)

    def snapshot(self) -> dict:
        hold_out = [dict(item) for item in self.hold] if self.freshness else list(self.hold)
        return {
            "player": {"pos": self.pos, "vel": self.vel, "heading_deg": self.heading,
                       "oxygen_ticks": self.oxygen_ticks, "oxygen_max_ticks": self.oxygen_max,
                       "hp": self.hp, "hp_max": self.t["hp_max"], "zero_oxy_ticks": self.zero_oxy_ticks,
                       "invuln_ticks": self.invuln_ticks, "catch_cd_ticks": self.catch_cd_ticks,
                       "at_surface": self._at_surface()},
            "hold": hold_out, "hold_count": len(self.hold),
            "hold_capacity": self.t["hold_capacity"],
            "monsters": [dict(m, pos=m["pos"].copy()) for m in sort_by_id(self.monsters)],
            "nodes": [{"id": n["id"], "pos": n["pos"], "kind": n["kind"],
                       "ready": n["regrow_ticks"] == 0, "regrow_ticks": n["regrow_ticks"]}
                      for n in sort_by_id(self.nodes)],
            "fish": [{"id": f["id"], "pos": f["pos"], "kind": f["kind"],
                      "heading_deg": f["heading_deg"], "age_ticks": f["age_ticks"]}
                     for f in sort_by_id(self.fish)],
        }

    # --- một bước ---------------------------------------------------------------
    def step(self, inp):
        events = []
        # 1. đồng hồ và hàng có sẵn: giảm bộ đếm, nút mọc lại
        self.phase_tick += 1
        self.time_left_ticks = max(0, self.time_left_ticks - 1)
        self.invuln_ticks = max(0, self.invuln_ticks - 1)
        self.catch_cd_ticks = max(0, self.catch_cd_ticks - 1)
        for n in sort_by_id(self.nodes):
            if n["regrow_ticks"] > 0:
                n["regrow_ticks"] -= 1
                if n["regrow_ticks"] == 0:
                    events.append(("node_regrown", {"node_id": n["id"]}))
        self._decay_hold(events)
        # 2. Bơi, chặn mép và tính oxy theo vị trí cuối bước.
        was_at_surface = self._at_surface()
        self._move(inp)
        self._update_survival(was_at_surface, events)
        if self.done:
            return events
        self._update_monsters(events)
        if self.done:
            return events
        # 3. interact: bến trước, rồi hái
        if inp.pressed("interact"):
            if self._in_dock():
                self._finish("docked", events)
                return events
            self._harvest(events)
        # 4. bắt cá
        if inp.pressed("catch"):
            self._catch(events)
        # 5. hết giờ
        if self.time_left_ticks <= 0:
            self._finish("time", events)
            return events
        # 6. cá bơi và sinh thêm theo lịch (chỉ khi còn giờ và random_fish=True)
        if self.random_fish:
            self._move_fish()
            self._spawn_fish(events)
        return events

    # --- tiện ích ---------------------------------------------------------------
    @staticmethod
    def _to_units(fresh: float) -> float:
        u = float(fresh) * 240.0
        r = round(u)
        return float(r) if abs(u - r) < 1e-9 else u

    def _init_hold(self, raw_hold, ids):
        if not self.freshness:
            return list(raw_hold)
        hold = []
        for item in raw_hold:
            ids.reserve(item["id"])
            u = self._to_units(item["fresh"])
            self._fresh_units[item["id"]] = u
            hold.append({"id": item["id"], "kind": item["kind"], "fresh": float(item["fresh"])})
        return hold

    def _decay_hold(self, events):
        if not self.freshness or not self.hold:
            return
        decay_u = float(self.freshness["gather_decay_per_s"]) * 240.0 / TICK
        spoiled_u = float(self.freshness["spoiled_below"]) * 240.0
        for item in sort_by_id(self.hold):
            iid = item["id"]
            old_u = self._fresh_units[iid]
            new_u = max(0.0, old_u - decay_u)
            self._fresh_units[iid] = new_u
            item["fresh"] = new_u / 240.0
            if old_u >= spoiled_u and new_u < spoiled_u:
                events.append(("spoiled", {"item_id": iid, "kind": item["kind"], "location": "hold"}))

    def _add_hold(self, kind: str, amount: int):
        if not self.freshness:
            self.hold.extend([kind] * amount)
            return
        initial = float(self.freshness["initial"])
        initial_u = self._to_units(initial)
        for _ in range(amount):
            iid = self.ids.new("I")
            self._fresh_units[iid] = initial_u
            self.hold.append({"id": iid, "kind": kind, "fresh": initial})

    def _init_fish(self, scenario, t, ids):
        if "fish" in scenario:
            fish = [{"id": f["id"], "kind": f["kind"], "pos": [float(c) for c in f["pos"]],
                     "heading_deg": float(f.get("heading_deg", 0)), "age_ticks": int(f.get("age_ticks", 0))}
                    for f in scenario["fish"]]
            for f in fish:
                ids.reserve(f["id"])
            return fish
        if not self.random_fish:
            return []
        initial = t["fish_initial"]
        if isinstance(initial, list):
            fish = [{"id": f["id"], "kind": f["kind"], "pos": [float(c) for c in f["pos"]],
                     "heading_deg": float(f.get("heading_deg", 0)), "age_ticks": 0}
                    for f in initial]
            for f in fish:
                ids.reserve(f["id"])
            return fish
        fish = []
        occupied = set()
        for _ in range(int(initial)):
            picked = self._pick_spawn(t, lambda pt: (pt[0], pt[1]) not in occupied)
            if picked is None:
                break
            kind, pt, heading = picked
            occupied.add((pt[0], pt[1]))
            fish.append({"id": ids.new("F"), "kind": kind, "pos": pt, "heading_deg": heading, "age_ticks": 0})
        return fish

    def _pick_spawn(self, t, is_valid):
        weights_map = t.get("fish_weights", {"ca_linh": 0.4, "ca_loc": 0.3, "ca_keo": 0.3})
        spawn_x = t.get("fish_spawn_x", [15, 30, 45, 60, 75, 90])
        spawn_depths = t.get("fish_spawn_depths", {"ca_linh": [5, 10], "ca_loc": [10, 16], "ca_keo": [24, 27]})
        valid_by_kind = {}
        for kind in ("ca_linh", "ca_loc", "ca_keo"):
            if kind not in weights_map:
                continue
            pts = [[float(x), float(d)] for x in spawn_x for d in spawn_depths.get(kind, [])]
            pts = [pt for pt in pts if is_valid(pt)]
            if pts:
                valid_by_kind[kind] = pts
        if not valid_by_kind:
            return None
        rng = self.rng.get("fish_spawn")
        avail_kinds = list(valid_by_kind)
        weights = [float(weights_map[k]) for k in avail_kinds]
        kind = rng.choices(avail_kinds, weights=weights, k=1)[0]
        pt = list(rng.choice(valid_by_kind[kind]))
        heading = rng.uniform(0.0, 360.0)
        return kind, pt, heading

    @staticmethod
    def _reflect(val: float, vel: float, lo: float, hi: float):
        while val < lo or val > hi:
            if val < lo:
                val = lo + (lo - val)
                vel = -vel
            elif val > hi:
                val = hi - (val - hi)
                vel = -vel
        return val, vel

    def _move_fish(self):
        speed = float(self.t.get("fish_speed", 1.5)) / TICK
        turn_ticks = int(self.t.get("fish_turn_ticks", 120))
        x_lo, x_hi = self.t.get("fish_x", [4, 96])
        depths_map = self.t.get("fish_depths", {"ca_linh": [3, 12], "ca_loc": [8, 20], "ca_keo": [22, 28]})
        rng = self.rng.get("fish_move")
        for f in sort_by_id(self.fish):
            f["age_ticks"] += 1
            if turn_ticks > 0 and f["age_ticks"] % turn_ticks == 0:
                f["heading_deg"] = rng.uniform(0.0, 360.0)
            rad = math.radians(f["heading_deg"])
            vx = math.cos(rad) * speed
            vd = math.sin(rad) * speed
            d_lo, d_hi = depths_map[f["kind"]]
            nx, vx = self._reflect(f["pos"][0] + vx, vx, float(x_lo), float(x_hi))
            nd, vd = self._reflect(f["pos"][1] + vd, vd, float(d_lo), float(d_hi))
            f["pos"] = [nx, nd]
            f["heading_deg"] = math.degrees(math.atan2(vd, vx)) % 360.0

    def _spawn_fish(self, events):
        spawn_ticks = int(self.t.get("fish_spawn_ticks", 360))
        fish_max = int(self.t.get("fish_max", 12))
        if spawn_ticks <= 0 or self.phase_tick % spawn_ticks != 0 or len(self.fish) >= fish_max:
            return
        clearance = float(self.t.get("fish_spawn_clearance", 1.0))
        picked = self._pick_spawn(
            self.t, lambda pt: all(math.dist(pt, f["pos"]) > clearance for f in self.fish)
        )
        if picked is None:
            return
        kind, pt, heading = picked
        fid = self.ids.new("F")
        self.fish.append({"id": fid, "kind": kind, "pos": pt, "heading_deg": heading, "age_ticks": 0})
        events.append(("fish_spawned", {"id": fid, "kind": kind, "pos": list(pt)}))

    def _nearest_in_radius(self, items, radius: float):
        """Trả thực thể gần nhất trong bán kính (tính cả mép), hòa theo id_key."""
        candidates = []
        for item in items:
            dist = math.dist(self.pos, item["pos"])
            if dist <= radius:
                candidates.append((dist, id_key(item["id"]), item))
        if not candidates:
            return None
        return min(candidates, key=lambda x: (x[0], x[1]))[2]

    def _harvest(self, events):
        """Hái nút ready gần nhất khi ở mặt nước."""
        if not self._at_surface():
            return
        ready_nodes = (n for n in self.nodes if n["regrow_ticks"] == 0)
        node = self._nearest_in_radius(ready_nodes, float(self.t["interact_radius"]))
        if node is None:
            return
        amount = int(self.t["node_yield"])
        free = int(self.t["hold_capacity"]) - len(self.hold)
        if free < amount:
            events.append(("hold_full", {
                "action": "gather", "node_id": node["id"], "required": amount, "free": free,
            }))
            return
        self._add_hold(node["kind"], amount)
        node["regrow_ticks"] = int(round(self.t["regrow_s"] * TICK))
        events.append(("gather", {"node_id": node["id"], "kind": node["kind"], "amount": amount}))

    def _catch(self, events):
        """Bắt đàn cá gần nhất khi hết hồi chiêu và đang dưới nước."""
        if self.catch_cd_ticks > 0 or self._at_surface():
            return
        fish = self._nearest_in_radius(self.fish, float(self.t["catch_radius"]))
        if fish is None:
            return
        yld = int(self.t["fish_yield"][fish["kind"]])
        free = int(self.t["hold_capacity"]) - len(self.hold)
        if free < yld:
            events.append(("hold_full", {
                "action": "catch", "fish_id": fish["id"], "required": yld, "free": free,
            }))
            return
        self._add_hold(fish["kind"], yld)
        self.fish.remove(fish)
        self.catch_cd_ticks = int(round(self.t["catch_cooldown_s"] * TICK))
        events.append(("fish_caught", {"fish_id": fish["id"], "kind": fish["kind"], "yield": yld}))
    def _at_surface(self) -> bool:
        return self.pos[1] <= self.t["surface_depth"]

    def _update_survival(self, was_at_surface, events):
        at_surface = self._at_surface()
        if at_surface != was_at_surface:
            events.append(("surface" if at_surface else "dive", {"pos": self.pos.copy()}))

        if at_surface:
            self.oxygen_ticks = min(self.oxygen_max, self.oxygen_ticks + self.t["oxygen_refill_per_tick"])
            self.zero_oxy_ticks = 0
            return

        if self.oxygen_ticks > 0:
            self.oxygen_ticks -= 1
            if self.oxygen_ticks > 0:
                self.zero_oxy_ticks = 0
                return
            events.append(("oxygen_empty", {"oxygen_ticks": 0}))

        # Bước vừa cạn oxy cũng tính là bước đầu tiên bị ngạt.
        self.zero_oxy_ticks += 1
        if self.zero_oxy_ticks < self.t["choke_interval_ticks"]:
            return

        self.zero_oxy_ticks = 0
        self.hp -= 1
        events.append(("choke", {"hp": self.hp}))
        if self.hp == 0:
            self._faint("choke", events)

    def _faint(self, cause, events):
        lost = list(reversed(self.hold))
        self.hold.clear()
        events.append(("faint", {"cause": cause, "lost": lost, "hp": 0}))
        self._finish("fainted", events)

    def _move_monster(self, monster, target, speed, depths):
        distance = math.dist(monster["pos"], target)
        step = min(distance, speed / TICK)
        if distance:
            monster["pos"] = [
                value + (goal - value) * step / distance
                for value, goal in zip(monster["pos"], target)
            ]
        bounds = self.t["bounds"]
        monster["pos"][0] = max(bounds["x"][0], min(bounds["x"][1], monster["pos"][0]))
        monster["pos"][1] = max(depths[0], min(depths[1], monster["pos"][1]))

    def _update_monsters(self, events):
        if not self.monster_tuning:
            return
        candidates = []
        for monster in sort_by_id(self.monsters):
            species = self.monster_tuning["species"][monster["kind"]]
            if monster["state"] == "recoil":
                target = [p + d for p, d in zip(monster["pos"], monster["recoil_dir"])]
                self._move_monster(
                    monster, target, species["recoil_dist"] * TICK / species["recoil_ticks"],
                    species["depths"],
                )
                monster["state_ticks_left"] -= 1
                if monster["state_ticks_left"] == 0:
                    monster["state"] = "patrol"
                    monster["recoil_dir"] = None
                # Bước cuối recoil vẫn không phát hiện hoặc gây hit.
                continue

            distance = math.dist(monster["pos"], self.pos)
            deep = self.pos[1] >= species["depths"][0]
            if monster["state"] == "chase":
                if not deep or distance > species["exit_radius"]:
                    monster["state"] = "patrol"
            elif deep and distance <= species["detect_radius"]:
                monster["state"] = "chase"

            if monster["state"] == "chase":
                self._move_monster(monster, self.pos, species["chase_speed"], species["depths"])
            else:
                target = monster["waypoints"][monster["target_idx"]]
                self._move_monster(monster, target, species["patrol_speed"], species["depths"])
                if math.dist(monster["pos"], target) <= 1e-9:
                    monster["target_idx"] = 1 - monster["target_idx"]

            distance = math.dist(monster["pos"], self.pos)
            if deep and distance <= species["hit_radius"]:
                candidates.append((distance, id_key(monster["id"]), monster))

        if self.invuln_ticks or not candidates:
            return
        monster = min(candidates, key=lambda candidate: candidate[:2])[2]
        species = self.monster_tuning["species"][monster["kind"]]
        loss_count = math.floor(len(self.hold) * self.monster_tuning["loss_ratio"])
        lost = [self.hold.pop() for _ in range(loss_count)]
        self.hp -= 1
        self.invuln_ticks = self.monster_tuning["invuln_ticks"]
        events.append(("monster_hit", {
            "monster_id": monster["id"], "hp": self.hp, "lost": lost, "pos": self.pos.copy(),
        }))
        distance = math.dist(monster["pos"], self.pos)
        monster["recoil_dir"] = (
            [(m - p) / distance for m, p in zip(monster["pos"], self.pos)]
            if distance else [1.0, 0.0]
        )
        monster["state"] = "recoil"
        monster["state_ticks_left"] = species["recoil_ticks"]
        if self.hp == 0:
            self._faint("monster", events)

    def _in_dock(self) -> bool:
        return math.dist(self.pos, self.t["dock_pos"]) <= self.t["dock_radius"]

    def _finish(self, reason, events):
        self.done = True
        self.reason = reason
        events.append(("gather_end", {"reason": reason, "inventory": {"items": self.inventory_items()}}))

    def _move(self, inp):
        speed = self.t["swim_speed"]
        mx, md = inp.move
        self.vel = ramp_velocity(self, (mx * speed, md * speed), int(self.t["ramp_max_ticks"]))
        if (mx, md) != (0.0, 0.0):
            self.heading = math.degrees(math.atan2(md, mx)) % 360
        b = self.t["bounds"]
        for i, axis in enumerate(AXES):
            self.pos[i] += self.vel[i] / TICK
            lo, hi = b[axis]
            if self.pos[i] <= lo:
                self.pos[i] = lo
                self.vel[i] = max(0.0, self.vel[i])
            elif self.pos[i] >= hi:
                self.pos[i] = hi
                self.vel[i] = min(0.0, self.vel[i])
