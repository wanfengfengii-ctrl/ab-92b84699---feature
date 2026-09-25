"""API 与 HTTP 冒烟测试：在临时端口启动真实服务进程内实例。"""

from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from typing import Any, Dict, Tuple

from app.server import Handler


class ServerHarness:
    def __init__(self) -> None:
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self) -> "ServerHarness":
        self.thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def get(self, path: str) -> Tuple[int, bytes, str]:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read(), resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers.get("Content-Type", "")

    def post(self, path: str, payload: Any) -> Tuple[int, Dict[str, Any]]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))


class HttpSmokeTests(unittest.TestCase):
    def test_healthz(self) -> None:
        with ServerHarness() as srv:
            status, body, ctype = srv.get("/healthz")
            self.assertEqual(status, 200)
            self.assertIn("application/json", ctype)
            self.assertEqual(json.loads(body), {"status": "ok"})

    def test_index_and_assets_served(self) -> None:
        with ServerHarness() as srv:
            for path, needle in (
                ("/", "空鼓"),
                ("/", "plan-btn"),
                ("/index.html", "app.js"),
                ("/app.js", "api/solve"),
                ("/app.js", "api/plan"),
                ("/style.css", ".brick"),
                ("/style.css", ".patch-badge"),
            ):
                status, body, _ = srv.get(path)
                self.assertEqual(status, 200, path)
                self.assertIn(needle, body.decode("utf-8"))

    def test_unknown_path_404(self) -> None:
        with ServerHarness() as srv:
            status, _, _ = srv.get("/nope")
            self.assertEqual(status, 404)
            # 简单的路径穿越防护
            status2, _, _ = srv.get("/../server.py")
            self.assertIn(status2, (404, 400))

    def test_solve_ok_roundtrip(self) -> None:
        with ServerHarness() as srv:
            payload = {
                "rows": 4,
                "cols": 4,
                "rects": [
                    {"r1": 1, "c1": 1, "r2": 2, "c2": 2, "count": 1},
                    {"r1": 2, "c1": 2, "r2": 3, "c2": 3, "count": 0},
                    {"r1": 3, "c1": 3, "r2": 4, "c2": 4, "count": 1},
                ],
            }
            status, data = srv.post("/api/solve", payload)
            self.assertEqual(status, 200)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["actual_counts"], [1, 0, 1])
            self.assertEqual(len(data["grid"]), 4)
            self.assertEqual(data["total"], sum(sum(r) for r in data["grid"]))

    def test_solve_unsat(self) -> None:
        with ServerHarness() as srv:
            payload = {
                "rows": 4,
                "cols": 4,
                "rects": [
                    {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 1},
                    {"r1": 1, "c1": 1, "r2": 1, "c2": 4, "count": 4},
                    {"r1": 1, "c1": 1, "r2": 2, "c2": 2, "count": 1},
                ],
            }
            status, data = srv.post("/api/solve", payload)
            self.assertEqual(status, 200)
            self.assertEqual(data["status"], "unsat")

    def test_reject_invalid_payloads(self) -> None:
        with ServerHarness() as srv:
            bad_cases = [
                {},  # 缺字段
                {"rows": 3, "cols": 4, "rects": []},  # 行数越界
                {"rows": 4, "cols": 4, "rects": [
                    {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 0},
                    {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 0},
                ]},  # 只有 2 条
                {"rows": 4, "cols": 4, "rects": [
                    {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 0},
                    {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 0},
                    {"r1": 3, "c1": 1, "r2": 1, "c2": 4, "count": 0},
                ]},  # 起止颠倒
                {"rows": 5, "cols": 5, "rects": [
                    {"r1": 1, "c1": 1, "r2": 5, "c2": 5, "count": 26},
                    {"r1": 1, "c1": 1, "r2": 5, "c2": 5, "count": 0},
                    {"r1": 1, "c1": 1, "r2": 5, "c2": 5, "count": 0},
                ]},  # 计数超出面积
            ]
            for payload in bad_cases:
                status, data = srv.post("/api/solve", payload)
                self.assertEqual(status, 400, payload)
                self.assertEqual(data["status"], "rejected")
                self.assertTrue(data["errors"])

    def test_reject_malformed_json(self) -> None:
        import http.client

        # 直接构造畸形请求体验证服务端返回 400 rejected。
        with ServerHarness() as srv:
            conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=5)
            conn.request(
                "POST",
                "/api/solve",
                body="{not json",
                headers={"Content-Type": "application/json"},
            )
            resp = conn.getresponse()
            self.assertEqual(resp.status, 400)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "rejected")


def assert_plan_matches_grid(testcase: unittest.TestCase, data: dict) -> None:
    """校验规划：每片只含空鼓砖、不重叠、并集恰为空鼓集、合计一致。"""
    grid = data["grid"]
    rows, cols = data["rows"], data["cols"]
    plan = data["plan"]
    pieces = plan["pieces"]
    testcase.assertEqual(plan["piece_count"], len(pieces))
    seen = set()
    total_perim = 0
    keys = []
    for p in pieces:
        testcase.assertTrue(1 <= p["r1"] <= p["r2"] <= rows)
        testcase.assertTrue(1 <= p["c1"] <= p["c2"] <= cols)
        area = (p["r2"] - p["r1"] + 1) * (p["c2"] - p["c1"] + 1)
        perim = 2 * ((p["r2"] - p["r1"] + 1) + (p["c2"] - p["c1"] + 1))
        testcase.assertEqual(p["cells"], area)
        testcase.assertEqual(p["perimeter"], perim)
        total_perim += perim
        keys.append((p["r1"], p["c1"], p["r2"], p["c2"]))
        for r in range(p["r1"], p["r2"] + 1):
            for c in range(p["c1"], p["c2"] + 1):
                testcase.assertEqual(grid[r - 1][c - 1], 1, (r, c, "覆盖完好砖"))
                testcase.assertNotIn((r, c), seen, (r, c, "修补片重叠"))
                seen.add((r, c))
    hollows = {
        (r + 1, c + 1)
        for r in range(rows)
        for c in range(cols)
        if grid[r][c] == 1
    }
    testcase.assertEqual(seen, hollows)
    testcase.assertEqual(plan["total_perimeter"], total_perim)
    testcase.assertEqual(keys, sorted(keys), "修补片应按坐标升序")


class PlanApiTests(unittest.TestCase):
    # 空鼓被锁定在 (1,1) 与 (4,4)（1 基）：两条单格记录 + 整墙合计。
    TWO_HOLLOW_PAYLOAD = {
        "rows": 4,
        "cols": 4,
        "rects": [
            {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 2},
            {"r1": 1, "c1": 1, "r2": 1, "c2": 1, "count": 1},
            {"r1": 4, "c1": 4, "r2": 4, "c2": 4, "count": 1},
        ],
    }

    def test_plan_ok_two_single_patches(self) -> None:
        with ServerHarness() as srv:
            status, data = srv.post("/api/plan", self.TWO_HOLLOW_PAYLOAD)
            self.assertEqual(status, 200)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["total"], 2)
            plan = data["plan"]
            self.assertEqual(plan["piece_count"], 2)
            self.assertEqual(plan["total_perimeter"], 8)
            self.assertEqual(
                [(p["r1"], p["c1"], p["r2"], p["c2"]) for p in plan["pieces"]],
                [(1, 1, 1, 1), (4, 4, 4, 4)],
            )
            for p in plan["pieces"]:
                self.assertEqual(p["cells"], 1)
                self.assertEqual(p["perimeter"], 4)
            assert_plan_matches_grid(self, data)

    def test_plan_merges_into_single_rectangle(self) -> None:
        # 空鼓锁定为 (1,1)、(1,2)（1 基）相邻两块：应合并为一片 1×2。
        payload = {
            "rows": 4,
            "cols": 4,
            "rects": [
                {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 2},
                {"r1": 1, "c1": 1, "r2": 1, "c2": 2, "count": 2},
                {"r1": 1, "c1": 1, "r2": 1, "c2": 1, "count": 1},
            ],
        }
        with ServerHarness() as srv:
            status, data = srv.post("/api/plan", payload)
            self.assertEqual(status, 200)
            self.assertEqual(data["status"], "ok")
            plan = data["plan"]
            self.assertEqual(plan["piece_count"], 1)
            self.assertEqual(plan["total_perimeter"], 6)
            self.assertEqual(
                [(p["r1"], p["c1"], p["r2"], p["c2"]) for p in plan["pieces"]],
                [(1, 1, 1, 2)],
            )
            assert_plan_matches_grid(self, data)

    def test_plan_ignores_client_supplied_grid(self) -> None:
        # 规划必须基于服务端重新反演：客户端夹带的网格不得被采用。
        payload = dict(self.TWO_HOLLOW_PAYLOAD)
        payload["grid"] = [[0] * 4 for _ in range(4)]  # 谎称无空鼓
        with ServerHarness() as srv:
            status, data = srv.post("/api/plan", payload)
            self.assertEqual(status, 200)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["total"], 2)
            self.assertEqual(data["plan"]["piece_count"], 2)
            assert_plan_matches_grid(self, data)

    def test_plan_is_deterministic_across_requests(self) -> None:
        with ServerHarness() as srv:
            status1, data1 = srv.post("/api/plan", self.TWO_HOLLOW_PAYLOAD)
            status2, data2 = srv.post("/api/plan", self.TWO_HOLLOW_PAYLOAD)
            self.assertEqual(status1, status2)
            self.assertEqual(data1, data2)

    def test_plan_unsat(self) -> None:
        payload = {
            "rows": 4,
            "cols": 4,
            "rects": [
                {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 1},
                {"r1": 1, "c1": 1, "r2": 1, "c2": 4, "count": 4},
                {"r1": 1, "c1": 1, "r2": 2, "c2": 2, "count": 1},
            ],
        }
        with ServerHarness() as srv:
            status, data = srv.post("/api/plan", payload)
            self.assertEqual(status, 200)
            self.assertEqual(data["status"], "unsat")
            self.assertNotIn("plan", data)

    def test_plan_rejected_invalid_payloads(self) -> None:
        with ServerHarness() as srv:
            for payload in (
                {},
                {"rows": 6, "cols": 4, "rects": []},
                {"rows": 4, "cols": 4, "rects": [
                    {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 0},
                ]},
            ):
                status, data = srv.post("/api/plan", payload)
                self.assertEqual(status, 400, payload)
                self.assertEqual(data["status"], "rejected")
                self.assertTrue(data["errors"])

    def test_plan_no_hollow_zero_pieces(self) -> None:
        payload = {
            "rows": 4,
            "cols": 4,
            "rects": [
                {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 0},
                {"r1": 1, "c1": 1, "r2": 2, "c2": 2, "count": 0},
                {"r1": 3, "c1": 3, "r2": 4, "c2": 4, "count": 0},
            ],
        }
        with ServerHarness() as srv:
            status, data = srv.post("/api/plan", payload)
            self.assertEqual(status, 200)
            self.assertEqual(data["status"], "ok")
            self.assertEqual(data["total"], 0)
            self.assertEqual(data["plan"]["piece_count"], 0)
            self.assertEqual(data["plan"]["total_perimeter"], 0)
            self.assertEqual(data["plan"]["pieces"], [])
            assert_plan_matches_grid(self, data)


if __name__ == "__main__":
    unittest.main()
