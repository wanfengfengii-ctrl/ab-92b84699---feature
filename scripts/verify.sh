#!/usr/bin/env sh
# 验收脚本：代码测试 + 构建（语法）检查 + API/HTTP 冒烟。
# 全部通过则以退出码 0 结束，任一失败立即以非零码退出（供 verify 服务上报）。
#
# 环境变量：
#   BASE_URL  待测服务地址，默认 http://web:8000（Compose 内），
#             本地直跑可设为 http://127.0.0.1:8000

set -eu

BASE_URL="${BASE_URL:-http://web:8000}"
cd "$(dirname "$0")/.."

echo "== [1/3] 构建检查：Python 语法编译 =="
python3 -m py_compile app/*.py tests/*.py scripts/healthcheck.py
echo "语法检查通过"

echo "== [2/3] 代码测试：单元 + 服务内 HTTP 冒烟 =="
python3 -m unittest discover -s tests -v

echo "== [3/3] 对运行中的服务做 API/HTTP 冒烟：${BASE_URL} =="
BASE_URL="$BASE_URL" python3 - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

base = os.environ["BASE_URL"].rstrip("/")


def request(method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def get_text(path):
    with urllib.request.urlopen(base + path, timeout=5) as resp:
        return resp.status, resp.read().decode("utf-8")


status, body = request("GET", "/healthz")
assert status == 200 and body.get("status") == "ok", (status, body)
print("  /healthz OK")

status, html = get_text("/")
assert status == 200 and "空鼓" in html and "app.js" in html
print("  首页 OK")

ok_payload = {
    "rows": 4,
    "cols": 4,
    "rects": [
        {"r1": 1, "c1": 1, "r2": 2, "c2": 2, "count": 1},
        {"r1": 2, "c1": 2, "r2": 3, "c2": 3, "count": 0},
        {"r1": 3, "c1": 3, "r2": 4, "c2": 4, "count": 1},
    ],
}
status, body = request("POST", "/api/solve", ok_payload)
assert status == 200 and body["status"] == "ok", (status, body)
assert body["actual_counts"] == [1, 0, 1], body
flat = [v for row in body["grid"] for v in row]
assert sum(flat) == body["total"], body
print(f"  /api/solve 可行用例 OK（空鼓总数 {body['total']}）")

unsat_payload = {
    "rows": 4,
    "cols": 4,
    "rects": [
        {"r1": 1, "c1": 1, "r2": 4, "c2": 4, "count": 1},
        {"r1": 1, "c1": 1, "r2": 1, "c2": 4, "count": 4},
        {"r1": 1, "c1": 1, "r2": 2, "c2": 2, "count": 1},
    ],
}
status, body = request("POST", "/api/solve", unsat_payload)
assert status == 200 and body["status"] == "unsat", (status, body)
print("  /api/solve 无禁用例正确返回 unsat")

bad_payload = {"rows": 3, "cols": 4, "rects": []}
status, body = request("POST", "/api/solve", bad_payload)
assert status == 400 and body["status"] == "rejected" and body["errors"], (status, body)
print("  /api/solve 非法输入正确拒绝 (400)")


def check_plan(body):
    """校验规划：每片只含空鼓砖、不重叠、并集恰为空鼓集、合计一致。"""
    grid, rows, cols = body["grid"], body["rows"], body["cols"]
    plan = body["plan"]
    pieces = plan["pieces"]
    assert plan["piece_count"] == len(pieces), plan
    seen = set()
    total_perim = 0
    keys = []
    for p in pieces:
        assert 1 <= p["r1"] <= p["r2"] <= rows, p
        assert 1 <= p["c1"] <= p["c2"] <= cols, p
        assert p["cells"] == (p["r2"] - p["r1"] + 1) * (p["c2"] - p["c1"] + 1), p
        assert p["perimeter"] == 2 * ((p["r2"] - p["r1"] + 1) + (p["c2"] - p["c1"] + 1)), p
        total_perim += p["perimeter"]
        keys.append((p["r1"], p["c1"], p["r2"], p["c2"]))
        for r in range(p["r1"], p["r2"] + 1):
            for c in range(p["c1"], p["c2"] + 1):
                assert grid[r - 1][c - 1] == 1, ("修补片覆盖完好砖", p)
                assert (r, c) not in seen, ("修补片重叠", p)
                seen.add((r, c))
    hollows = {
        (r + 1, c + 1)
        for r in range(rows)
        for c in range(cols)
        if grid[r][c] == 1
    }
    assert seen == hollows, ("修补片未恰好覆盖全部空鼓砖", plan)
    assert plan["total_perimeter"] == total_perim, plan
    assert keys == sorted(keys), ("修补片未按坐标升序", plan)


status, body = request("POST", "/api/plan", ok_payload)
assert status == 200 and body["status"] == "ok" and "plan" in body, (status, body)
check_plan(body)
first_plan = body["plan"]
print(
    f"  /api/plan 可行用例 OK（{first_plan['piece_count']} 片，"
    f"切缝合计 {first_plan['total_perimeter']}）"
)

# 同一检测记录重复请求，规划结果必须一致（可重复核对）。
status, body2 = request("POST", "/api/plan", ok_payload)
assert status == 200 and body2["status"] == "ok" and body2["plan"] == first_plan, (
    status,
    body2,
)
print("  /api/plan 重复请求结果一致")

status, body = request("POST", "/api/plan", unsat_payload)
assert status == 200 and body["status"] == "unsat" and "plan" not in body, (status, body)
print("  /api/plan 无禁用例正确返回 unsat")

status, body = request("POST", "/api/plan", bad_payload)
assert status == 400 and body["status"] == "rejected" and body["errors"], (status, body)
print("  /api/plan 非法输入正确拒绝 (400)")

print("  全部 HTTP/API 冒烟通过")
PY

echo ""
echo "✅ 验收全部通过：构建检查、代码测试、API/HTTP 冒烟均成功。"
