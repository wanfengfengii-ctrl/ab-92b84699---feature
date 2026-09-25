# 饰砖空鼓联合反演（VoidDrum）

古建筑墙面饰砖修缮前，检测员对 4–5 行 × 4–5 列的饰砖网格进行有限次
（3–12 次）矩形区域敲击抽检，每次记录区域内听到空鼓砖的**整数数量**。
本服务把所有记录作为一个整体联合求解，为每块砖给出唯一的空鼓/完好判定；
获得结论后还可在同一工作台发起**最小切缝修补规划**，把需要揭除的空鼓砖
组织为轴对齐矩形修补片。

## 判定规则

把每块砖视为 0/1 变量（1=空鼓），每次检测是一条
“区域内空鼓总数恰等于记录值”的等式约束。对所有满足全部记录的分布，
按优先级选出唯一方案：

1. **空鼓总数最少**；
2. 总数相同时，取按“从上到下、从左到右”展开的状态序列
   **字典序最小**者（0=完好，故空鼓尽量靠后）。

不存在任何分布能同时满足全部记录时返回“无解（无法满足全部记录）”。

## 修补规划规则

规划由服务端用当前全部检测记录**重新反演**空鼓结论后计算，不接受客户端
上传网格。空鼓砖被划分为若干轴对齐矩形修补片：

- 每片只覆盖空鼓砖，所有空鼓砖恰好归入一片；
- 修补片可共边但不得重叠（共边在两片各自切缝，分别计入长度）；
- 依次最小化：
  1. **修补片数最少**；
  2. 片数相同时，**各片四周切缝长度之和最短**（每片取矩形周长）；
  3. 再相同时，把各片按左上至右下 `(r1,c1,r2,c2)` 排成坐标序列，
     取**字典序最小**的唯一划分。

原记录无解或输入被拒绝时不生成规划（响应中 `plan` 为 `null`）；
没有空鼓砖时规划为空（0 片）。前端在任一检测资料修改后立即清除既有
结论与规划，须重新提交/发起。

## 技术栈

- 后端：Python 3.11 标准库（`http.server`），**零第三方依赖**；
- 前端：原生 HTML/CSS/JS，无构建步骤；
- 求解器：`app/solver.py`，约束传播 + 回溯，5×5 最坏场景实测为毫秒级；
- 规划器：`app/planner.py`，锚点枚举 + 记忆化精确覆盖搜索，5×5 亚毫秒级；
- 测试：标准库 `unittest`，含对 4×4 全空间 2^16 穷举的等价性对照，
  以及修补划分在 3×3/4×4 上的全枚举等价性对照。

## 目录结构

```
app/
  server.py          # HTTP 服务：静态页 + POST /api/solve + POST /api/plan + GET /healthz
  solver.py          # 联合反演求解器
  planner.py         # 最小切缝修补规划器
  static/            # 前端页面
tests/               # 单元测试与服务内 HTTP 冒烟
scripts/
  healthcheck.py     # 容器健康检查
  verify.sh          # 验收：构建检查 + 代码测试 + 对运行服务的 API/HTTP 冒烟
Dockerfile           # 含 HEALTHCHECK
docker-compose.yml   # web 常驻 + verify 一次性验收（退出码即结论）
```

## 本地运行（无需 Docker）

```bash
python3 -m app.server            # 默认 0.0.0.0:8000，可用 PORT 覆盖
python3 -m unittest discover -s tests -v
BASE_URL=http://127.0.0.1:8000 scripts/verify.sh
```

## Docker 运行

```bash
# 宿主机端口默认 8080，可通过 HOST_PORT 配置：
HOST_PORT=9090 docker compose up -d web
# 浏览器访问 http://localhost:9090

# 运行一次性验收服务：完成后 web 一并停止，命令退出码等于 verify 的验收结论码
docker compose up --build --abort-on-container-exit --exit-code-from verify verify
# 0 = 构建检查 + 代码测试 + API/HTTP 冒烟全部通过；非 0 表示存在失败项
docker compose logs verify       # 查看验收明细（容器已退出，日志保留）
```

`web` 服务配置了容器 `HEALTHCHECK`（探测 `/healthz`），`verify` 服务
通过 `depends_on: condition: service_healthy` 等待其健康后才开始冒烟，
随后以验收结论作为退出码退出（`restart: "no"`，不会重启）。

## HTTP API

`POST /api/solve`

```json
{
  "rows": 4,
  "cols": 4,
  "rects": [
    {"r1": 1, "c1": 1, "r2": 2, "c2": 2, "count": 1}
  ]
}
```

坐标为 1 基、含端点（左上 `r1,c1`，右下 `r2,c2`）。响应：

- `200 {"status":"ok", "grid":[[0,1,...]], "total":N, "actual_counts":[...], ...}`
  —— 获选方案，`actual_counts` 为每次区域在该方案下的实际计数；
- `200 {"status":"unsat"}` —— 记录互不相容，无法满足全部记录；
- `400 {"status":"rejected", "errors":[...]}` —— 输入不合法被服务端拒绝。

`POST /api/plan` —— 最小切缝修补规划，请求体与 `/api/solve` 相同
（**只接受原始检测记录**；若额外携带 `grid` 字段一律 400 拒绝）。
服务端先重新反演空鼓结论，再在 `ok` 响应中追加 `plan`：

```json
{
  "status": "ok",
  "grid": [[0,1,...]],
  "plan": {
    "pieces": [
      {"r1": 1, "c1": 2, "r2": 1, "c2": 2, "cells": 1, "cut_length": 4}
    ],
    "piece_count": 1,
    "total_cut_length": 4
  }
}
```

`pieces` 按左上至右下排序，含每片坐标、覆盖砖数与单片切缝长度；
无解时返回 `200 {"status":"unsat","plan":null,"message":"..."}`，
输入不合法返回 400 rejected。规划结果可直接与响应中的 `grid` 逐项核对
（每片格位均为 1、并集恰为全部空鼓砖）。

前端行为：任何输入修改都会立即让旧结论与既有修补规划失效（显示“已失效”
提示并清除划片），无解或被拒绝时明确展示“无法满足全部记录/无法生成规划”，
且不保留旧结果。
