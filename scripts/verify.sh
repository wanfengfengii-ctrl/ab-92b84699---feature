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

# ---- 最小切缝修补规划：必须由服务端按原始记录重新反演 ----
status, body = request("POST", "/api/plan", ok_payload)
assert status == 200 and body["status"] == "ok" and body.get("plan"), (status, body)
plan = body["plan"]
hollow_cells = [
    (r, c)
    for r, row in enumerate(body["grid"])
    for c, v in enumerate(row)
    if v == 1
]
assert plan["piece_count"] == len(plan["pieces"]) == len(hollow_cells) >= 1, plan
covered = []
for p in plan["pieces"]:
    assert p["cells"] == (p["r2"] - p["r1"] + 1) * (p["c2"] - p["c1"] + 1), p
    assert p["cut_length"] == 2 * (
        (p["r2"] - p["r1"] + 1) + (p["c2"] - p["c1"] + 1)
    ), p
    for r in range(p["r1"] - 1, p["r2"]):
        for c in range(p["c1"] - 1, p["c2"]):
            assert body["grid"][r][c] == 1, "修补片混入完好砖"
            covered.append((r, c))
assert sorted(covered) == sorted(hollow_cells), "空鼓砖未被恰好归入一片"
assert sum(p["cells"] for p in plan["pieces"]) == body["total"]
assert plan["total_cut_length"] == sum(p["cut_length"] for p in plan["pieces"])
print(
    f"  /api/plan 可行用例 OK（{plan['piece_count']} 片，切缝合计 {plan['total_cut_length']}）"
)

# 原记录无解：不得返回规划，须明确说明无法生成。
status, body = request("POST", "/api/plan", unsat_payload)
assert status == 200 and body["status"] == "unsat", (status, body)
assert body.get("plan") is None and body.get("message"), body
print("  /api/plan 无禁用例返回 unsat 且明确无法生成")

# 拒绝客户端上传网格；非法记录同样 400。
forged = dict(ok_payload, grid=[[1] * 4 for _ in range(4)])
status, body = request("POST", "/api/plan", forged)
assert status == 400 and body["status"] == "rejected" and body["errors"], (status, body)
status, body = request("POST", "/api/plan", bad_payload)
assert status == 400 and body["status"] == "rejected", (status, body)
print("  /api/plan 拒绝客户端网格与非法输入 (400)")

print("  全部 HTTP/API 冒烟通过")
PY

echo ""
echo "✅ 验收全部通过：构建检查、代码测试、API/HTTP 冒烟均成功。"
