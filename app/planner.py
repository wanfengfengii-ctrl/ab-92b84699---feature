"""最小切缝修补规划：把空鼓砖划分为互不重叠的轴对齐矩形修补片。

输入联合反演得到的 0/1 网格（1=空鼓），输出一组矩形修补片，满足：

- 每片只覆盖空鼓砖（片内不得混入完好砖）；
- 所有空鼓砖恰好归入一片（片间可共边但不得重叠）；
- 依次最小化：
  1. 修补片数量；
  2. 各片四周切缝长度之和（每片周长，共边在两片各计一次）；
  3. 把各片按“左上至右下”（``(r1,c1,r2,c2)`` 升序）排成坐标序列后，
     取字典序最小的唯一划分。

算法：精确覆盖搜索。取行主序第一块尚未覆盖的空鼓砖作为锚点，任何合法
划分中覆盖它的修补片左上角只能是该锚点本身（更靠前的空鼓砖均已被其他
片覆盖，共边不允许重叠），故只需枚举以锚点为左上角、片内全为空鼓砖的
轴对齐矩形。每个覆盖状态的最优“后缀”与到达路径无关，做记忆化即可。
网格至多 5×5，规模很小。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Patch:
    """一片轴对齐矩形修补片，坐标为 1 基、含端点。

    cells: 覆盖空鼓砖数；cut_length: 该片四周切缝长度（矩形周长）。
    """

    r1: int
    c1: int
    r2: int
    c2: int
    cells: int
    cut_length: int

    @property
    def key(self) -> Tuple[int, int, int, int]:
        return (self.r1, self.c1, self.r2, self.c2)


@dataclass(frozen=True)
class RepairPlan:
    """修补规划：pieces 已按左上至右下排序。"""

    pieces: Tuple[Patch, ...]
    piece_count: int
    total_cut_length: int


# 记忆化搜索中的候选片：(覆盖位掩码, 坐标键, 周长, 面积)。
Candidate = Tuple[int, Tuple[int, int, int, int], int, int]
# 某覆盖状态的最优后缀：(追加片数, 追加切缝长度, 追加坐标键序列)。
Suffix = Tuple[int, int, Tuple[Tuple[int, int, int, int], ...]]


def _enumerate_candidates(
    grid: Sequence[Sequence[int]], rows: int, cols: int
) -> Tuple[int, Dict[int, List[Candidate]]]:
    """枚举所有“片内全为空鼓砖”的矩形，按左上角锚点归类。"""

    hollow_mask = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                hollow_mask |= 1 << (r * cols + c)

    by_anchor: Dict[int, List[Candidate]] = {}
    for r1 in range(rows):
        for c1 in range(cols):
            if grid[r1][c1] != 1:
                continue
            anchor = r1 * cols + c1
            candidates: List[Candidate] = []
            reach = cols - 1
            for r2 in range(r1, rows):
                # 维护自 c1 起、r1..r2 各行连续空鼓的公共最远列。
                c = c1
                while c <= reach and grid[r2][c] == 1:
                    c += 1
                reach = c - 1
                if reach < c1:
                    break
                for c2 in range(c1, reach + 1):
                    mask = 0
                    for rr in range(r1, r2 + 1):
                        base = rr * cols
                        for cc in range(c1, c2 + 1):
                            mask |= 1 << (base + cc)
                    h = r2 - r1 + 1
                    w = c2 - c1 + 1
                    key = (r1 + 1, c1 + 1, r2 + 1, c2 + 1)
                    candidates.append((mask, key, 2 * (h + w), h * w))
            # 先试大片：更早逼近最少片数；面积相同时坐标键小者优先。
            candidates.sort(key=lambda cand: (-cand[3], cand[1]))
            by_anchor[anchor] = candidates
    return hollow_mask, by_anchor


def plan_repairs(grid: Sequence[Sequence[int]]) -> RepairPlan:
    """根据空鼓网格求唯一最优修补规划；无空鼓砖时规划为空。"""

    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    if rows == 0 or cols == 0:
        return RepairPlan((), 0, 0)

    hollow_mask, by_anchor = _enumerate_candidates(grid, rows, cols)
    if hollow_mask == 0:
        return RepairPlan((), 0, 0)

    memo: Dict[int, Optional[Suffix]] = {}

    def best_suffix(covered: int) -> Optional[Suffix]:
        if covered == hollow_mask:
            return (0, 0, ())
        if covered in memo:
            return memo[covered]

        remaining = hollow_mask & ~covered
        # 行主序第一块未覆盖空鼓砖（最低置位）。
        anchor_bit = remaining & -remaining
        anchor = anchor_bit.bit_length() - 1

        best: Optional[Suffix] = None
        for mask, key, perimeter, _area in by_anchor[anchor]:
            if mask & covered:
                continue  # 与已选片重叠，不合法
            sub = best_suffix(covered | mask)
            if sub is None:
                continue
            candidate: Suffix = (
                sub[0] + 1,
                sub[1] + perimeter,
                (key,) + sub[2],
            )
            if best is None or candidate < best:
                best = candidate

        memo[covered] = best
        return best

    suffix = best_suffix(0)
    # 单片候选始终包含 1×1 空鼓砖，任何非空空鼓集合都存在精确覆盖。
    assert suffix is not None
    piece_count, total_cut, keys = suffix

    pieces = tuple(
        Patch(
            r1=r1,
            c1=c1,
            r2=r2,
            c2=c2,
            cells=(r2 - r1 + 1) * (c2 - c1 + 1),
            cut_length=2 * ((r2 - r1 + 1) + (c2 - c1 + 1)),
        )
        for r1, c1, r2, c2 in keys
    )
    return RepairPlan(
        pieces=pieces,
        piece_count=piece_count,
        total_cut_length=total_cut,
    )
