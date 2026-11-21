"""Đọc game.contract.json và kiểm dải hợp lệ của tuning P1 (PRD mục 13.2, Test Contract)."""

import json
import math
import os

from .errors import BadInput

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "game.contract.json")


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _between(name, v, lo, hi):
    if not _num(v) or not (lo <= v <= hi):
        raise BadInput(f"tuning.{name} phải trong [{lo}, {hi}], đang là {v!r}")


def load_contract(path=DEFAULT_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được {path}: {e}")
    ver = c.get("contract_version")
    if ver is not None and ver not in ("1.0", "1.1", "1.2", "1.3"):
        raise BadInput(f"contract_version không hỗ trợ: {ver!r}")
    for key in ("bench_cmd", "soak_cmd"):
        if key in c and (not isinstance(c[key], str) or not c[key].strip()):
            raise BadInput(f"{key} phải là chuỗi lệnh khác rỗng")
    validate_tuning(c.get("tuning"))
    # Truyền version tới sim/scenario mà không đổi manifest trên đĩa.
    c["tuning"]["_contract_version"] = ver or "1.1"
    return c


def _int_between(name, v, lo, hi):
    if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
        raise BadInput(f"tuning.{name} phải là số nguyên trong [{lo}, {hi}], đang là {v!r}")


def _pos_in(name, pos, bounds, keys):
    if (not isinstance(pos, list) or len(pos) != 2 or not all(_num(c) for c in pos)):
        raise BadInput(f"tuning.{name} phải là [số, số]")
    for c, k in zip(pos, keys):
        lo, hi = bounds[k]
        if not (lo <= c <= hi):
            raise BadInput(f"tuning.{name} nằm ngoài vùng {k} ∈ [{lo}, {hi}]")


def _bounds(name, b, keys):
    if not isinstance(b, dict) or set(b) != set(keys):
        raise BadInput(f"tuning.{name}.bounds phải có đúng khóa {list(keys)}")
    for k in keys:
        v = b[k]
        if not (isinstance(v, list) and len(v) == 2 and all(_num(c) for c in v) and v[0] == 0 and v[1] > 0):
            raise BadInput(f"tuning.{name}.bounds.{k} phải là [0, số dương]")


def _validate_gather(g):
    """Dải hợp lệ P1 theo PRD mục 13.2."""
    _between("gather.duration_s", g.get("duration_s"), 60, 600)
    _bounds("gather", g.get("bounds"), ("x", "d"))
    b = g["bounds"]
    _between("gather.dock_radius", g.get("dock_radius"), 0.5, 5)
    _between("gather.interact_radius", g.get("interact_radius"), 0.5, 5)
    _between("gather.catch_radius", g.get("catch_radius"), 0.5, 5)
    _between("gather.swim_speed", g.get("swim_speed"), 1, 10)
    _between("gather.catch_cooldown_s", g.get("catch_cooldown_s"), 0, 10)
    _between("gather.oxygen_max_s", g.get("oxygen_max_s"), 10, 120)
    _int_between("gather.ramp_max_ticks", g.get("ramp_max_ticks"), 0, 6)
    _int_between("gather.hold_capacity", g.get("hold_capacity"), 4, 30)
    _int_between("gather.hp_max", g.get("hp_max"), 1, 99)
    _int_between("gather.oxygen_refill_per_tick", g.get("oxygen_refill_per_tick"), 1, 10_000)
    _int_between("gather.choke_interval_ticks", g.get("choke_interval_ticks"), 1, 10_000)
    _int_between("gather.node_yield", g.get("node_yield"), 1, 12)
    _between("gather.regrow_s", g.get("regrow_s"), 0.1, 600)
    _between("gather.surface_depth", g.get("surface_depth"), 0, 5)
    _pos_in("gather.dock_pos", g.get("dock_pos"), b, ("x", "d"))
    _pos_in("gather.start_pos", g.get("start_pos"), b, ("x", "d"))
    if not _num(g.get("start_heading_deg")):
        raise BadInput("tuning.gather.start_heading_deg phải là số")
    fy = g.get("fish_yield")
    if not isinstance(fy, dict) or not {"ca_linh", "ca_loc"} <= set(fy):
        raise BadInput("tuning.gather.fish_yield phải có ca_linh và ca_loc")
    for k, v in fy.items():
        _int_between(f"gather.fish_yield.{k}", v, 1, g["hold_capacity"])
    nodes = g.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise BadInput("tuning.gather.nodes phải là mảng không rỗng")
    seen, kinds = set(), set()
    for n in nodes:
        if not isinstance(n, dict) or not isinstance(n.get("id"), str) or n["id"] in seen:
            raise BadInput("tuning.gather.nodes: mỗi nút cần id duy nhất")
        seen.add(n["id"])
        if n.get("kind") not in ("bong_dien_dien", "bong_sung", "keo_neo"):
            raise BadInput(f"tuning.gather.nodes.{n['id']}: kind phải là bong_dien_dien, bong_sung hoặc keo_neo")
        kinds.add(n["kind"])
        _pos_in(f"gather.nodes.{n['id']}.pos", n.get("pos"), b, ("x", "d"))
        if n["pos"][1] != 0:
            raise BadInput(f"tuning.gather.nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
    if not {"bong_dien_dien", "bong_sung"} <= kinds:
        raise BadInput("tuning.gather.nodes phải có ít nhất một nút mỗi loại (bong_dien_dien, bong_sung)")
    fish = g.get("fish_initial")
    if isinstance(fish, int) and not isinstance(fish, bool):
        if fish < 1:
            raise BadInput("tuning.gather.fish_initial phải >= 1")
    elif isinstance(fish, list) and len(fish) == 6:
        seen = set()
        for f in fish:
            if not isinstance(f, dict) or not isinstance(f.get("id"), str) or f["id"] in seen:
                raise BadInput("tuning.gather.fish_initial: mỗi đàn cần id duy nhất")
            seen.add(f["id"])
            if f.get("kind") not in fy:
                raise BadInput(f"tuning.gather.fish_initial.{f['id']}: kind phải thuộc fish_yield")
            _pos_in(f"gather.fish_initial.{f['id']}.pos", f.get("pos"), b, ("x", "d"))
            if f["pos"][1] <= g["surface_depth"]:
                raise BadInput(f"tuning.gather.fish_initial.{f['id']}: đàn cá phải ở dưới nước")
    else:
        raise BadInput("tuning.gather.fish_initial phải là số nguyên dương hoặc danh sách 6 đàn")


def _validate_freshness(f):
    """Kiểm cấu hình freshness v1.2 (initial, gather_decay_per_s, quan_decay_per_s, spoiled_below)."""
    expected = {"initial", "gather_decay_per_s", "quan_decay_per_s", "spoiled_below"}
    if not isinstance(f, dict) or set(f.keys()) != expected:
        raise BadInput(f"tuning.freshness phải có đúng các khóa {sorted(expected)}")
    for k in expected:
        v = f[k]
        if not _num(v) or not math.isfinite(v):
            raise BadInput(f"tuning.freshness.{k} phải là số hữu hạn, đang là {v!r}")
    if not (0 < f["initial"] <= 100):
        raise BadInput(f"tuning.freshness.initial phải trong (0, 100], đang là {f['initial']!r}")
    if not (0 <= f["spoiled_below"] < f["initial"]):
        raise BadInput(f"tuning.freshness.spoiled_below phải trong [0, initial), đang là {f['spoiled_below']!r}")
    if f["gather_decay_per_s"] <= 0 or f["quan_decay_per_s"] <= 0:
        raise BadInput("tuning.freshness.gather_decay_per_s và quan_decay_per_s phải > 0")


def validate_tuning(t):
    if not isinstance(t, dict):
        raise BadInput("thiếu khối tuning")
    g, q, menu = t.get("gather"), t.get("quan"), t.get("menu")
    if not isinstance(g, dict) or not isinstance(q, dict) or not isinstance(menu, dict):
        raise BadInput("tuning phải có gather, quan, menu")
    _validate_gather(g)
    # Quán: dải hợp lệ P1 (PRD mục 13.2)
    _between("quan.duration_s", q.get("duration_s"), 60, 600)
    _bounds("quan", q.get("bounds"), ("x", "z"))
    _between("quan.patience_s", q.get("patience_s"), 20, 180)
    _between("quan.walk_speed", q.get("walk_speed"), 1, 10)
    _between("quan.interact_radius", q.get("interact_radius"), 0.5, 5)
    _int_between("quan.ramp_max_ticks", q.get("ramp_max_ticks", 6), 0, 6)
    _between("quan.eat_s", q.get("eat_s"), 0.1, 600)
    _between("quan.customer_interval_s", q.get("customer_interval_s"), 0.1, 600)
    _int_between("quan.first_customer_tick", q.get("first_customer_tick"), 1, int(q["duration_s"] * 60) - 1)
    if not (_num(q.get("tip_rate")) and q["tip_rate"] > 0 and _num(q.get("left_reputation_delta"))
            and q["left_reputation_delta"] < 0):
        raise BadInput("tip_rate phải > 0 và left_reputation_delta phải < 0")
    ratio = q.get("tip_min_patience_ratio")
    if not (_num(ratio) and 0 < ratio <= 1):
        raise BadInput("quan.tip_min_patience_ratio phải thuộc (0, 1]")
    if not (_num(q.get("tip_reputation")) and q["tip_reputation"] > 0):
        raise BadInput("quan.tip_reputation phải > 0")
    if q.get("burn_s") is not None:
        raise BadInput("burn_s lõi phải là null (mở rộng burn mới hữu hạn)")
    stoves, tables = q.get("stoves"), q.get("tables")
    if not isinstance(stoves, list) or not stoves or not isinstance(tables, list) or not tables:
        raise BadInput("quan.stoves và quan.tables phải là mảng không rỗng")
    # TODO(nhóm): bổ sung kiểm các khóa còn lại nếu muốn chặt hơn (uy tín, shop, ...).
    for dish_id, d in menu.items():
        price, cook = d.get("price"), d.get("cook_s")
        if isinstance(price, bool) or not isinstance(price, int) or price <= 0 or not _num(cook) or cook <= 0:
            raise BadInput(f"menu.{dish_id}: price (nguyên) và cook_s phải > 0")
        recipe = d.get("recipe")
        if not isinstance(recipe, dict) or not recipe:
            raise BadInput(f"menu.{dish_id}: recipe phải là object không rỗng")
    day_plan = t.get("day_plan")
    if "freshness" in t:
        _validate_freshness(t["freshness"])
    if day_plan is not None:
        if not isinstance(day_plan, list) or len(day_plan) != 5:
            raise BadInput("tuning.day_plan phải là mảng 5 Ngày")
        from .day_plan import compute_ingredients
        from .inventory import validate_items
        for p in day_plan:
            if not isinstance(p, dict) or p.get("day") not in (1, 2, 3, 4, 5):
                raise BadInput("day_plan: mỗi mục cần day ∈ 1..5")
            dishes = p.get("dishes")
            got = compute_ingredients(menu, dishes)
            if "ingredients" in p and validate_items(p["ingredients"]) != got:
                raise BadInput(f"day_plan D{p['day']}: ingredients không khớp dishes × recipe")
