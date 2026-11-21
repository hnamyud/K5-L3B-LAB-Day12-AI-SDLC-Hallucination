"""Nạp và kiểm scenario (Contract D). Trả về dict của đúng khối theo mode.

KHUNG: kiểm cú pháp, id trùng, bộ đếm âm, khoang vượt sức chứa, trường lạ.
TODO(nhóm): bổ sung kiểm mâu thuẫn mức luật mà nhóm cần (khách giữ chỗ quá kho, đơn assigned
phải có đúng một món, khách eating thiếu giá/tip...) — xem PRD-0 mục D và 'Mâu thuẫn -> mã 2'.
"""

import json
import math

from .errors import BadInput
from .freshness import validate_units
from .inventory import KINDS_P2, is_v12, validate_items

GATHER_KEYS = {"player", "hold", "nodes", "fish", "random_fish", "time_left_ticks", "monsters"}
GATHER_PLAYER_KEYS = {"pos", "vel", "heading_deg", "hp", "oxygen_ticks", "zero_oxy_ticks",
                      "invuln_ticks", "catch_cd_ticks"}
NODE_KINDS = ("bong_dien_dien", "bong_sung", "keo_neo")
FISH_KINDS = ("ca_linh", "ca_loc", "ca_keo")
QUAN_PLAYER_KEYS = {"pos", "vel"}
QUAN_KEYS = {"player", "stock", "hand", "stoves", "tables", "customers", "random_customers",
             "reputation", "time_left_ticks", "day_plan"}


def _check_ids(name, arr):
    if not isinstance(arr, list):
        raise BadInput(f"{name} phải là mảng")
    seen = set()
    for e in arr:
        if not isinstance(e, dict) or not isinstance(e.get("id"), str) or not e["id"]:
            raise BadInput(f"{name}: mỗi phần tử cần id (chuỗi khác rỗng)")
        if e["id"] in seen:
            raise BadInput(f"{name}: id trùng {e['id']}")
        seen.add(e["id"])


def load_scenario(path, mode: str, tuning: dict) -> dict:
    if path is None:
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise BadInput(f"không đọc được scenario {path}: {e}")
    allowed_modes = {"day", "gather", "quan"} if mode == "day" else {mode}
    if not isinstance(data, dict) or set(data) - allowed_modes:
        raise BadInput(f"khối scenario không hợp lệ cho mode {mode}")
    if mode == "day":
        day = data.get("day", {})
        if not isinstance(day, dict) or set(day) - {"money", "earned", "reputation", "upgrades", "day_plan"}:
            raise BadInput("khối day không hợp lệ")
        gather = _scenario_block(data.get("gather", {}), "gather", tuning, validate=False)
        quan = _scenario_block(data.get("quan", {}), "quan", tuning)
        if {"stock", "reputation"} & quan.keys():
            raise BadInput("day không nhận quan.stock hoặc quan.reputation")
        return {"day": day, "gather": gather, "quan": quan}
    return _scenario_block(data.get(mode, {}), mode, tuning)


def _scenario_block(block, mode, tuning, *, validate=True):
    if not isinstance(block, dict):
        raise BadInput(f"khối {mode} phải là object")
    allowed = GATHER_KEYS if mode == "gather" else QUAN_KEYS
    extra = set(block) - allowed
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong {mode}: {sorted(extra)}")
    dur = int(round(tuning[mode]["duration_s"] * 60))
    if "time_left_ticks" in block:
        t = block["time_left_ticks"]
        if isinstance(t, bool) or not isinstance(t, int) or not (1 <= t <= dur):
            raise BadInput(f"time_left_ticks phải là số nguyên trong [1, {dur}]")
    if mode == "gather":
        if validate:
            _validate_gather(block, tuning)
    else:
        _validate_quan(block, tuning)
    return block


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _nonneg_int(name, v):
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise BadInput(f"{name} phải là số nguyên không âm")


def _pos(name, pos, bounds, axes=("x", "d")):
    if not (isinstance(pos, list) and len(pos) == 2 and all(_num(c) for c in pos)):
        raise BadInput(f"{name} phải là [{axes[0]}, {axes[1]}]")
    for c, axis in zip(pos, axes):
        lo, hi = bounds[axis]
        if not (lo <= c <= hi):
            raise BadInput(f"{name} nằm ngoài vùng nước ({axis} ∈ [{lo}, {hi}])")


def _validate_gather(b, tuning):
    g = tuning["gather"]
    bounds = g["bounds"]
    _validate_monsters(b, g)
    for arr in ("nodes", "fish"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "random_fish" in b and not isinstance(b["random_fish"], bool):
        raise BadInput("random_fish phải là boolean")
    if "hold" in b:
        h = b["hold"]
        if not isinstance(h, list):
            raise BadInput("hold phải là mảng")
        if len(h) > g["hold_capacity"]:
            raise BadInput("hold vượt sức chứa")
        if tuning.get("freshness") and is_v12(tuning.get("_contract_version", "1.2")):
            seen_hold = set()
            for idx, item in enumerate(h):
                if not isinstance(item, dict) or set(item) != {"id", "kind", "fresh"}:
                    raise BadInput(f"hold[{idx}] phải là object {{id, kind, fresh}}")
                iid = item["id"]
                if not isinstance(iid, str) or not iid or iid in seen_hold:
                    raise BadInput(f"hold[{idx}]: id phải là chuỗi khác rỗng và duy nhất")
                seen_hold.add(iid)
                if item["kind"] not in KINDS_P2:
                    raise BadInput(f"hold[{idx}]: kind không hợp lệ {item['kind']!r}")
                fr = item["fresh"]
                if not _num(fr) or not math.isfinite(fr) or not (0 <= fr <= 100):
                    raise BadInput(f"hold[{idx}]: fresh phải hữu hạn trong [0, 100]")
        elif any(k not in KINDS_P2 for k in h):
            raise BadInput("hold phải là mảng id nguyên liệu hợp lệ")
    p = b.get("player", {})
    if not isinstance(p, dict):
        raise BadInput("player phải là object")
    extra = set(p) - GATHER_PLAYER_KEYS
    if extra:
        raise BadInput(f"trường lạ/chưa hỗ trợ trong gather.player: {sorted(extra)}")
    if "pos" in p:
        _pos("player.pos", p["pos"], bounds)
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, d]")
    if "heading_deg" in p and not _num(p["heading_deg"]):
        raise BadInput("player.heading_deg phải là số")
    for key in ("invuln_ticks", "catch_cd_ticks", "zero_oxy_ticks", "oxygen_ticks", "hp"):
        if key in p:
            _nonneg_int(f"player.{key}", p[key])
    omax = int(round(g["oxygen_max_s"] * 60))
    if "oxygen_ticks" in p and p["oxygen_ticks"] > omax:
        raise BadInput("player.oxygen_ticks vượt oxy tối đa")
    if "hp" in p and not (1 <= p["hp"] <= g["hp_max"]):
        raise BadInput("player.hp phải trong [1, hp_max]")
    if "zero_oxy_ticks" in p:
        pos = p.get("pos", g["start_pos"])
        oxy = p.get("oxygen_ticks", omax)
        if p["zero_oxy_ticks"] > 59:
            raise BadInput("player.zero_oxy_ticks phải trong [0, 59]")
        if p["zero_oxy_ticks"] > 0 and not (oxy == 0 and pos[1] > g["surface_depth"]):
            raise BadInput("player.zero_oxy_ticks > 0 chỉ khi oxy = 0 và đang dưới nước")
    for n in b.get("nodes", []):
        if n.get("kind") not in NODE_KINDS:
            raise BadInput(f"nodes.{n['id']}: kind phải là một trong {NODE_KINDS}")
        _pos(f"nodes.{n['id']}.pos", n.get("pos"), bounds)
        if n["pos"][1] != 0:
            raise BadInput(f"nodes.{n['id']}: nút hái nằm ở mặt nước (d = 0)")
        if "regrow_ticks" in n:
            _nonneg_int(f"nodes.{n['id']}.regrow_ticks", n["regrow_ticks"])
    for f in b.get("fish", []):
        if f.get("kind") not in FISH_KINDS:
            raise BadInput(f"fish.{f['id']}: kind phải là một trong {FISH_KINDS}")
        _pos(f"fish.{f['id']}.pos", f.get("pos"), bounds)
        if f["pos"][1] <= g["surface_depth"]:
            raise BadInput(f"fish.{f['id']}: đàn cá phải ở dưới nước")
        if "heading_deg" in f and not _num(f["heading_deg"]):
            raise BadInput(f"fish.{f['id']}.heading_deg phải là số")
        if "age_ticks" in f:
            _nonneg_int(f"fish.{f['id']}.age_ticks", f["age_ticks"])


def _validate_monsters(block, gather):
    if "monsters" not in block:
        return
    config = gather.get("monsters")
    if not config:
        raise BadInput("monsters cần cấu hình loài trong tuning")
    _check_ids("monsters", block["monsters"])
    allowed = {"id", "kind", "pos", "waypoints", "target_idx", "state",
               "state_ticks_left", "recoil_dir"}
    for monster in block["monsters"]:
        if (set(monster) - allowed or not isinstance(monster.get("kind"), str)
                or monster["kind"] not in config["species"]):
            raise BadInput("monsters: trường hoặc loài không hợp lệ")
        species = config["species"][monster["kind"]]
        bounds = {"x": gather["bounds"]["x"], "d": species["depths"]}
        _pos("monster.pos", monster.get("pos"), bounds)
        waypoints = monster.get("waypoints")
        if not isinstance(waypoints, list) or len(waypoints) != 2:
            raise BadInput("monster.waypoints cần đúng hai điểm")
        for point in waypoints:
            _pos("monster.waypoints", point, bounds)
        target = monster.get("target_idx", 1)
        if type(target) is not int or target not in (0, 1):
            raise BadInput("monster.target_idx phải là 0 hoặc 1")
        state = monster.get("state", "patrol")
        if state not in ("patrol", "chase", "recoil"):
            raise BadInput("monster.state chưa được hỗ trợ")
        timer = monster.get("state_ticks_left", 0)
        _nonneg_int("monster.state_ticks_left", timer)
        direction = monster.get("recoil_dir")
        if state == "recoil":
            if timer == 0 or not (
                isinstance(direction, list) and len(direction) == 2
                and all(_num(value) and math.isfinite(value) for value in direction)
                and math.isclose(math.hypot(*direction), 1.0, abs_tol=1e-9)
            ):
                raise BadInput("monster recoil cần timer dương và vector đơn vị")
        elif timer != 0 or direction is not None:
            raise BadInput("monster ngoài recoil cần timer 0 và recoil_dir null")


def _validate_quan(b, tuning):
    for arr in ("stoves", "tables", "customers"):
        if arr in b:
            _check_ids(arr, b[arr])
    if "stock" in b:
        if isinstance(b["stock"], list):
            validate_units(b["stock"])
        else:
            validate_items(b["stock"])
    p = b.get("player", {})
    if not isinstance(p, dict) or set(p) - QUAN_PLAYER_KEYS:
        raise BadInput("quan.player chỉ có pos và vel")
    qb = tuning["quan"]["bounds"]
    if "pos" in p:
        _pos("player.pos", p["pos"], qb, axes=("x", "z"))
    if "vel" in p and not (isinstance(p["vel"], list) and len(p["vel"]) == 2 and all(_num(c) for c in p["vel"])):
        raise BadInput("player.vel phải là [x, z]")
    table_ids = [c.get("table_id") for c in b.get("customers", [])]
    known = {t["id"] for t in tuning["quan"]["tables"]} | {t.get("id") for t in b.get("tables", [])}
    for c in b.get("customers", []):
        if not isinstance(c.get("table_id"), str) or c["table_id"] not in known:
            raise BadInput(f"customers.{c['id']}: table_id phải là bàn có thật")
    if len(table_ids) != len(set(table_ids)):
        raise BadInput("hai khách cùng bàn")
