"""HTTP 服务：静态页面 + 空鼓反演 JSON API（仅依赖标准库）。

环境变量：
  HOST  监听地址，默认 0.0.0.0
  PORT  监听端口，默认 8000
"""

from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from .solver import Rect, solve

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

MIN_SIDE = 4
MAX_SIDE = 5
MIN_RECTS = 3
MAX_RECTS = 12
MAX_BODY = 64 * 1024

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


def _as_int(value: Any) -> Tuple[bool, int]:
    if isinstance(value, bool):
        return False, 0
    if isinstance(value, int):
        return True, value
    return False, 0


def validate_payload(data: Any) -> Tuple[Dict[str, Any] | None, List[str]]:
    """校验并归一化请求载荷。

    检测区域使用 1 基、含端点坐标（r1/c1 为左上角，r2/c2 为右下角）。
    返回 (归一化数据, 错误列表)；存在错误时第一项为 None。
    """

    errors: List[str] = []
    if not isinstance(data, dict):
        return None, ["请求体必须是 JSON 对象"]

    ok_rows, rows = _as_int(data.get("rows"))
    ok_cols, cols = _as_int(data.get("cols"))
    if not ok_rows or not (MIN_SIDE <= rows <= MAX_SIDE):
        errors.append(f"行数必须是 {MIN_SIDE} 至 {MAX_SIDE} 的整数")
    if not ok_cols or not (MIN_SIDE <= cols <= MAX_SIDE):
        errors.append(f"列数必须是 {MIN_SIDE} 至 {MAX_SIDE} 的整数")
    grid_ok = not errors

    raw_rects = data.get("rects")
    rects: List[Dict[str, int]] = []
    if not isinstance(raw_rects, list) or not (
        MIN_RECTS <= len(raw_rects) <= MAX_RECTS
    ):
        errors.append(f"检测区域数量必须为 {MIN_RECTS} 至 {MAX_RECTS} 次")
        raw_rects = []

    for idx, item in enumerate(raw_rects):
        where = f"第 {idx + 1} 条检测记录"
        if not isinstance(item, dict):
            errors.append(f"{where}：格式错误")
            continue
        coords: Dict[str, int] = {}
        all_ints = True
        for key in ("r1", "c1", "r2", "c2", "count"):
            ok, val = _as_int(item.get(key))
            if not ok:
                errors.append(f"{where}：{key} 必须是整数")
                all_ints = False
            coords[key] = val
        if not grid_ok or not all_ints:
            rects.append(coords)
            continue
        r1, c1, r2, c2, count = (
            coords["r1"],
            coords["c1"],
            coords["r2"],
            coords["c2"],
            coords["count"],
        )
        if not (1 <= r1 <= rows and 1 <= r2 <= rows and r1 <= r2):
            errors.append(f"{where}：行范围无效，应在 1..{rows} 且起止合法")
        if not (1 <= c1 <= cols and 1 <= c2 <= cols and c1 <= c2):
            errors.append(f"{where}：列范围无效，应在 1..{cols} 且起止合法")
        area = max(r2 - r1 + 1, 0) * max(c2 - c1 + 1, 0)
        if not (0 <= count <= area):
            errors.append(f"{where}：空鼓计数必须在 0 至区域面积 {area} 之间")
        rects.append(coords)

    if errors:
        return None, errors
    return {"rows": rows, "cols": cols, "rects": rects}, []


def run_solver(data: Dict[str, Any]) -> Dict[str, Any]:
    rows = data["rows"]
    cols = data["cols"]
    rects = [
        Rect(d["r1"] - 1, d["c1"] - 1, d["r2"] - 1, d["c2"] - 1, d["count"])
        for d in data["rects"]
    ]
    result = solve(rows, cols, rects)
    if result is None:
        return {"status": "unsat"}
    return {
        "status": "ok",
        "rows": rows,
        "cols": cols,
        "grid": result.grid,
        "total": result.total,
        "actual_counts": result.actual_counts,
        "consistent": True,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "VoidDrum/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        if os.environ.get("QUIET_LOGS"):
            return
        super().log_message(fmt, *args)

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/":
            path = "/index.html"
        safe = os.path.normpath(path).lstrip(os.sep)
        full = os.path.join(STATIC_DIR, safe)
        if not full.startswith(STATIC_DIR + os.sep) or not os.path.isfile(full):
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "not found"})
            return
        ext = os.path.splitext(full)[1]
        with open(full, "rb") as fh:
            body = fh.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", CONTENT_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/solve":
            self._send_json(HTTPStatus.NOT_FOUND, {"status": "error", "message": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "rejected", "errors": ["请求体为空或超出大小限制"]},
            )
            return
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "rejected", "errors": ["请求体不是合法的 JSON"]},
            )
            return
        normalized, errors = validate_payload(data)
        if normalized is None:
            self._send_json(HTTPStatus.BAD_REQUEST, {"status": "rejected", "errors": errors})
            return
        self._send_json(HTTPStatus.OK, run_solver(normalized))


def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"空鼓反演服务监听 http://{host}:{port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
