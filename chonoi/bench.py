"""Benchmark có render — Test Contract v1.3 / TV3 Phase 4.

    python3 -m chonoi.bench --seed 42 --duration 30 --out bench.json

Dựng ca sáng gather (độ tươi, cá bơi, Cá Sấu, Út Sen đứng yên ở bến) qua
`chonoi.live` + Chrome 1280×720, warm-up 3 s rồi đo `requestAnimationFrame`.

Xuất đúng 5 trường: avg_fps, p1_low_fps, frames, measured_s, load_ms.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import urlparse

from .contract import load_contract
from .errors import BadInput
from .live import WEB_DIR, LiveGame

BENCH_FIELDS = ("avg_fps", "p1_low_fps", "frames", "measured_s", "load_ms")
WARMUP_S = 3.0
VIEW_W, VIEW_H = 1280, 720
MAX_BODY = 65536

# Cảnh sáng lõi: giỏ có độ tươi + đủ thời gian để đo (không cập bến / hết giờ).
BENCH_SCENARIO = {
    "player": {"pos": [2.0, 0.0], "heading_deg": 0.0},
    "hold": [
        {"id": "B1", "kind": "ca_linh", "fresh": 92.0},
        {"id": "B2", "kind": "ca_loc", "fresh": 78.5},
        {"id": "B3", "kind": "bong_sung", "fresh": 55.0},
    ],
    "time_left_ticks": 60 * 60 * 15,  # 15 phút sim
}


def p1_low_fps(frame_dts_ms: list[float]) -> float:
    """FPS trung bình của max(1, ceil(0.01 * frames)) khung chậm nhất."""
    frames = len(frame_dts_ms)
    if frames == 0:
        return 0.0
    n = max(1, math.ceil(0.01 * frames))
    slowest = sorted(frame_dts_ms, reverse=True)[:n]
    total_ms = sum(slowest)
    if total_ms <= 0:
        return 0.0
    return (n * 1000.0) / total_ms


def summarize(frame_dts_ms: list[float], measured_s: float, load_ms: float) -> dict:
    frames = len(frame_dts_ms)
    measured_s = float(measured_s)
    avg = (frames / measured_s) if measured_s > 0 else 0.0
    return {
        "avg_fps": avg,
        "p1_low_fps": p1_low_fps(frame_dts_ms),
        "frames": frames,
        "measured_s": measured_s,
        "load_ms": float(load_ms),
    }


def find_chrome() -> Optional[str]:
    env = os.environ.get("CHONOI_BROWSER") or os.environ.get("CHROME_PATH")
    if env and os.path.isfile(env) and os.access(env, os.X_OK):
        return env
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if os.path.isfile(mac):
        return mac
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        path = shutil.which(name)
        if path:
            return path
    return None


_BENCH_JS = r"""
<script>
(function () {
  const q = new URLSearchParams(location.search);
  if (q.get("bench") !== "1") return;
  const WARM = Math.max(0, +(q.get("warmup") || 3));
  const DUR = Math.max(0.5, +(q.get("duration") || 30));
  const t0 = performance.now();
  let load_ms = null;
  let phase = "load";
  let warmAt = null;
  let measAt = null;
  let stateReady = false;
  const dts = [];
  let sent = false;

  function pollState() {
    fetch("/state").then(function (r) { return r.json(); }).then(function (j) {
      if (j && j.player && Array.isArray(j.fish)) stateReady = true;
      else setTimeout(pollState, 40);
    }).catch(function () { setTimeout(pollState, 80); });
  }
  pollState();

  function finish(measured_s) {
    if (sent) return;
    sent = true;
    const frames = dts.length;
    const avg_fps = measured_s > 0 ? frames / measured_s : 0;
    const n = Math.max(1, Math.ceil(0.01 * frames));
    const slowest = dts.slice().sort(function (a, b) { return b - a; }).slice(0, n);
    const sum = slowest.reduce(function (a, b) { return a + b; }, 0);
    const p1_low_fps = sum > 0 ? (n * 1000) / sum : 0;
    const body = JSON.stringify({
      avg_fps: avg_fps,
      p1_low_fps: p1_low_fps,
      frames: frames,
      measured_s: measured_s,
      load_ms: load_ms == null ? (performance.now() - t0) : load_ms,
      _dts: dts
    });
    fetch("/bench-report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body,
      keepalive: true
    }).catch(function () {});
  }

  function hook() {
    const perf = window.__perf;
    if (!perf || !perf.samples || typeof perf.samples.push !== "function") {
      requestAnimationFrame(hook);
      return;
    }
    const _push = perf.samples.push.bind(perf.samples);
    perf.samples.push = function (dt) {
      const r = _push(dt);
      const now = performance.now();
      if (load_ms == null && stateReady && perf.frames >= 2 && dt < 250) {
        load_ms = now - t0;
        phase = "warm";
        warmAt = now;
      }
      if (phase === "warm" && now - warmAt >= WARM * 1000) {
        phase = "measure";
        measAt = now;
        dts.length = 0;
      }
      if (phase === "measure") {
        dts.push(dt);
        if (now - measAt >= DUR * 1000) {
          phase = "done";
          finish((now - measAt) / 1000);
        }
      }
      return r;
    };
  }
  hook();
  // Phòng khi rAF không chạy: hết hạn thì vẫn báo lỗi phía server.
})();
</script>
"""


def _inject_bench(html: bytes) -> bytes:
    marker = b"</body>"
    snippet = _BENCH_JS.encode("utf-8")
    idx = html.lower().rfind(marker)
    if idx < 0:
        return html + snippet
    return html[:idx] + snippet + html[idx:]


class BenchServer:
    """Live gather + HTTP: phục vụ index đã inject harness và nhận /bench-report."""

    def __init__(self, game: LiveGame, host="127.0.0.1", port=0):
        self.game = game
        self.report: Optional[dict] = None
        self._report_event = threading.Event()
        with open(os.path.join(WEB_DIR, "index.html"), "rb") as f:
            self._html = _inject_bench(f.read())
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):
                pass

            def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/state":
                    self._send(200, outer.game.state_json())
                elif path in ("/", "/index.html"):
                    self._send(200, outer._html, "text/html; charset=utf-8")
                else:
                    self._send(404, b'{"error":"khong co"}')

            def do_POST(self):
                path = urlparse(self.path).path
                try:
                    n = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    n = -1
                if n < 0 or n > MAX_BODY:
                    self._send(400, b'{"error":"body sai"}')
                    return
                raw = self.rfile.read(n) if n else b""
                if path == "/bench-report":
                    try:
                        data = json.loads(raw.decode("utf-8") or "{}")
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        self._send(400, b'{"error":"json sai"}')
                        return
                    if not isinstance(data, dict):
                        self._send(400, b'{"error":"body phai la object"}')
                        return
                    outer.report = data
                    outer._report_event.set()
                    self._send(200, b'{"ok":true}')
                    return
                # Ủy quyền input tối thiểu (client có thể POST /input khi poll).
                try:
                    if path == "/input":
                        body = json.loads(raw.decode("utf-8") or "{}")
                        if not isinstance(body, dict):
                            raise ValueError("body phải là object")
                        # Giữ Út Sen đứng yên: bỏ qua move khác [0,0]
                        move = body.get("move")
                        if move is not None:
                            body = dict(body)
                            body["move"] = [0, 0]
                        outer.game.set_input(body)
                    elif path == "/restart":
                        outer.game.restart()
                    elif path == "/start":
                        outer.game.begin()
                    elif path == "/menu":
                        outer.game.to_menu()
                    else:
                        self._send(404, b'{"error":"khong co"}')
                        return
                except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as e:
                    self._send(400, json.dumps({"error": str(e)}).encode("utf-8"))
                    return
                self._send(200, b'{"ok":true}')

        self.httpd = ThreadingHTTPServer((host, port), Handler)
        self.httpd.daemon_threads = True
        self.host = host
        self.port = self.httpd.server_address[1]
        self._thread = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/"

    def start(self):
        self.game.start()
        self._thread = threading.Thread(target=self.httpd.serve_forever, name="chonoi-bench-http", daemon=True)
        self._thread.start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self.game.stop()

    def wait_report(self, timeout: float) -> Optional[dict]:
        self._report_event.wait(timeout)
        return self.report


def run_bench(*, seed: int, duration: float, warmup: float, out_path: str,
              chrome: Optional[str] = None, host: str = "127.0.0.1") -> dict:
    chrome = chrome or find_chrome()
    if not chrome:
        raise BadInput(
            "không tìm thấy Chrome/Chromium. Cài Chrome hoặc đặt CHONOI_BROWSER=/đường/dẫn/chrome"
        )

    contract = load_contract()
    tuning = copy.deepcopy(contract["tuning"])
    # Bật độ tươi trên snapshot để HUD vẽ thanh tươi (không đụng game.contract.json — TV1).
    tuning["_contract_version"] = "1.2"
    if "freshness" not in tuning:
        raise BadInput("thiếu tuning.freshness trong game.contract.json")

    scenario = copy.deepcopy(BENCH_SCENARIO)
    # Đảm bảo còn giờ suốt warm-up + đo + buffer.
    need_ticks = int(math.ceil((warmup + duration + 15) * 60))
    scenario["time_left_ticks"] = max(scenario["time_left_ticks"], need_ticks)

    game = LiveGame("gather", tuning, scenario, seed)
    server = BenchServer(game, host=host, port=0)
    server.start()

    bench_url = (
        f"{server.url}?bench=1&warmup={warmup:g}&duration={duration:g}"
        f"&seed={seed}"
    )
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        f"--window-size={VIEW_W},{VIEW_H}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--autoplay-policy=no-user-gesture-required",
        bench_url,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        timeout = warmup + duration + 45.0
        raw = server.wait_report(timeout)
        if not raw:
            raise BadInput(
                f"hết hạn chờ bench-report ({timeout:.0f}s). "
                "Kiểm tra Chrome headless / cổng local."
            )
        dts = raw.pop("_dts", None)
        if dts is not None:
            result = summarize(list(dts), raw.get("measured_s", duration), raw.get("load_ms", 0))
        else:
            result = {k: raw[k] for k in BENCH_FIELDS}
            for k in BENCH_FIELDS:
                if k not in raw:
                    raise BadInput(f"bench-report thiếu trường {k}")
        # Kiểu số ổn định.
        result = {
            "avg_fps": float(result["avg_fps"]),
            "p1_low_fps": float(result["p1_low_fps"]),
            "frames": int(result["frames"]),
            "measured_s": float(result["measured_s"]),
            "load_ms": float(result["load_ms"]),
        }
        parent = os.path.dirname(os.path.abspath(out_path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return result
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        server.stop()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="chonoi.bench",
        description="Benchmark render ca sáng 1280×720 (TV3 Phase 4).",
    )
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--duration", type=float, default=30.0, help="thời gian đo (giây), mặc định 30")
    p.add_argument("--warmup", type=float, default=WARMUP_S, help="làm nóng trước khi đo (giây), mặc định 3")
    p.add_argument("--out", required=True, help="đường dẫn file JSON kết quả")
    p.add_argument("--chrome", help="đường dẫn Chrome (hoặc CHONOI_BROWSER)")
    a = p.parse_args(argv)
    try:
        if a.duration <= 0:
            raise BadInput("--duration phải > 0")
        if a.warmup < 0:
            raise BadInput("--warmup phải >= 0")
        t0 = time.perf_counter()
        result = run_bench(
            seed=a.seed,
            duration=a.duration,
            warmup=a.warmup,
            out_path=a.out,
            chrome=a.chrome,
        )
        wall = time.perf_counter() - t0
        print(
            f"bench seed={a.seed} avg_fps={result['avg_fps']:.2f} "
            f"p1_low_fps={result['p1_low_fps']:.2f} frames={result['frames']} "
            f"measured_s={result['measured_s']:.3f} load_ms={result['load_ms']:.1f} "
            f"(wall {wall:.1f}s) -> {a.out}",
            flush=True,
        )
        # Mốc báo cáo (không fail CLI nếu máy chậm — ghi chú trên stderr).
        notes = []
        if result["avg_fps"] < 60:
            notes.append(f"avg_fps {result['avg_fps']:.1f} < 60")
        if result["p1_low_fps"] < 30:
            notes.append(f"p1_low_fps {result['p1_low_fps']:.1f} < 30")
        if result["load_ms"] > 10000:
            notes.append(f"load_ms {result['load_ms']:.0f} > 10000")
        if notes:
            sys.stderr.write("mốc báo cáo chưa đạt: " + "; ".join(notes) + "\n")
        return 0
    except BadInput as e:
        sys.stderr.write(f"đầu vào sai: {e}\n")
        return 2
    except OSError as e:
        sys.stderr.write(f"lỗi hệ thống: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
