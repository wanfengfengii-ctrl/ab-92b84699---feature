#!/usr/bin/env python3
"""容器健康检查：访问本实例 /healthz，失败以非零码退出。"""

import os
import sys
import urllib.request

port = os.environ.get("PORT", "8000")
url = f"http://127.0.0.1:{port}/healthz"
try:
    with urllib.request.urlopen(url, timeout=3) as resp:
        if resp.status != 200:
            raise RuntimeError(f"status {resp.status}")
        sys.exit(0)
except Exception as exc:  # noqa: BLE001
    print(f"healthcheck failed: {exc}", file=sys.stderr)
    sys.exit(1)
