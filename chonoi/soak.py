"""Soak test headless nhiều ngày (TV2 · Phase 4):

    python3 -m chonoi.soak --seed <int> --days <N> --out <soak.json>

Chạy N Ngày liên tiếp trong một tiến trình bằng bot tất định (lặp kế hoạch D1–D5 cho Ngày > 5),
giữ liên tục tiền, earned, uy tín, nâng cấp và ID cá thể.
"""

import argparse
import json
import math
import os
import sys
import time

from .contract import load_contract
from .errors import BadInput
from .inputs import InputState
from .rng import Streams
from .sim.day import DaySim


def _move_toward(pos, target):
    dx = target[0] - pos[0]
    dy = target[1] - pos[1]
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return (0.0, 0.0)
    return (dx / dist, dy / dist)


def _bot_gather(sim, tick):
    g = sim.shift
    if len(g.hold) >= g.t["hold_capacity"] - 1 or g.time_left_ticks <= 900:
        move = _move_toward(g.pos, g.t["dock_pos"])
        if g._in_dock() and tick % 2 == 0:
            return InputState(move, {"interact": True}, {"interact"})
        return InputState(move, {}, set())

    if g.oxygen_ticks < g.oxygen_max * 0.35:
        return InputState((0.0, -1.0), {}, set())

    # Ưu tiên bắt cá nếu ở dưới nước hoặc săn cá gần nhất, sau đó hái nút ready
    ready_nodes = [n for n in g.nodes if n["regrow_ticks"] == 0]
    if g.fish:
        target_fish = min(g.fish, key=lambda f: math.dist(g.pos, f["pos"]))
        move = _move_toward(g.pos, target_fish["pos"])
        if not g._at_surface() and g.catch_cd_ticks == 0 and math.dist(g.pos, target_fish["pos"]) <= g.t["catch_radius"]:
            if tick % 2 == 0:
                return InputState(move, {"catch": True}, {"catch"})
        return InputState(move, {}, set())

    if ready_nodes:
        target_node = min(ready_nodes, key=lambda n: math.dist(g.pos, n["pos"]))
        move = _move_toward(g.pos, target_node["pos"])
        if g._at_surface() and not g._in_dock() and math.dist(g.pos, target_node["pos"]) <= g.t["interact_radius"]:
            if tick % 2 == 0:
                return InputState(move, {"interact": True}, {"interact"})
        return InputState(move, {}, set())

    move = _move_toward(g.pos, g.t["dock_pos"])
    if g._in_dock() and tick % 2 == 0:
        return InputState(move, {"interact": True}, {"interact"})
    return InputState(move, {}, set())


def _bot_quan(sim, tick):
    q = sim.shift
    r = q.t["interact_radius"]
    target_pos = None

    if q.hand is not None:
        oid = q.hand["order_id"]
        cust = next((c for c in q.customers if c["id"] == oid), None)
        if cust is not None:
            tbl = next((t for t in q.tables if t["id"] == cust["table_id"]), None)
            if tbl is not None:
                target_pos = tbl["pos"]
    else:
        ready_stoves = [s for s in q.stoves if s["state"] == "ready"]
        if ready_stoves:
            target_pos = min(ready_stoves, key=lambda s: math.dist(q.pos, s["pos"]))["pos"]
        elif any(c["order_status"] == "reserved" for c in q.customers):
            idle_stoves = [s for s in q.stoves if s["state"] == "idle"]
            if idle_stoves:
                target_pos = min(idle_stoves, key=lambda s: math.dist(q.pos, s["pos"]))["pos"]

    if target_pos is None:
        return InputState((0.0, 0.0), {}, set())

    move = _move_toward(q.pos, target_pos)
    if math.dist(q.pos, target_pos) <= r and tick % 2 == 0:
        return InputState(move, {"interact": True}, {"interact"})
    return InputState(move, {}, set())


def _bot_shop(sim, tick):
    for kind in ("oxygen", "hp"):
        levels = sim.shop["upgrades"][kind]
        cur = sim.upgrades.get(kind, 0)
        if cur < len(levels) and sim.money >= levels[cur]["price"]:
            return InputState((0.0, 0.0), {}, set(), buy=kind)
    if tick % 2 == 0:
        return InputState((0.0, 0.0), {"shop_done": True}, {"shop_done"})
    return InputState((0.0, 0.0), {}, set())


def _bot_input(sim, tick):
    if sim.phase == "gather":
        return _bot_gather(sim, tick)
    if sim.phase == "quan":
        return _bot_quan(sim, tick)
    return _bot_shop(sim, tick)


def run_soak(seed: int, days: int, tuning=None) -> dict:
    if days < 1:
        raise BadInput("--days phải >= 1")
    if tuning is None:
        tuning = load_contract()["tuning"]
    t0 = time.perf_counter()
    sim = DaySim(tuning, {}, Streams(seed), days)
    mult = tuning["score"]["reputation_multiplier"]
    results = []
    crashes = 0
    tick = 0
    day_ticks = sum(round(tuning[phase]["duration_s"] * tuning["tick_hz"])
                    for phase in ("gather", "quan")) + tuning["shop"]["max_ticks"]
    max_ticks = days * day_ticks

    try:
        while not sim.done and tick < max_ticks:
            prev_completed = sim.days_completed
            completed_day = sim.day
            inp = _bot_input(sim, tick)
            sim.step(inp)
            tick += 1
            if sim.days_completed > prev_completed:
                score = sim.earned + mult * math.floor(sim.reputation)
                results.append({
                    "day": completed_day,
                    "earned": sim.earned,
                    "reputation": round(sim.reputation, 6),
                    "score": score,
                })
    except Exception as error:
        crashes += 1
        sys.stderr.write(f"soak dừng ở Ngày {sim.day}, tick {tick}: {error}\n")

    duration_s = round(time.perf_counter() - t0, 4)
    return {
        "days": days,
        "days_completed": sim.days_completed,
        "crashes": crashes,
        "results": results,
        "duration_s": duration_s,
    }


def _int(name):
    def conv(s):
        try:
            return int(s)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{name} phải là số nguyên")
    return conv


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="chonoi.soak")
    p.add_argument("--seed", required=True, type=_int("seed"))
    p.add_argument("--days", type=_int("days"), default=10)
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)
    try:
        report = run_soak(args.seed, args.days)
    except BadInput as e:
        sys.stderr.write(f"lỗi: {e}\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"lỗi thực thi: {e}\n")
        return 1

    try:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(out_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except OSError as error:
        sys.stderr.write(f"lỗi ghi báo cáo soak: {error}\n")
        return 1
    if report["crashes"] or report["days_completed"] != report["days"]:
        sys.stderr.write("soak thất bại: có crash hoặc chưa hoàn tất đủ Ngày\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
