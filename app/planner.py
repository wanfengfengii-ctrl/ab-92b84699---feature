"""空鼓砖最小切缝修补规划。

联合反演给出空鼓分布后，需要揭除的空鼓砖被组织为若干轴对齐的矩形
修补片：每片只覆盖空鼓砖，所有空鼓砖恰好归入一片，片与片可共边但
不得重叠。修补方案按以下优先级唯一确定：

1. 修补片数最少；
2. 片数相同时，各片四周切缝长度之和最短（单片切缝长度 = 矩形周长，
   以砖边长为单位）；
3. 仍相同时，各片按 (上行, 左列, 下行, 右列) 升序排列形成的坐标
   序列字典序最小。

实现：网格至多 5×5=25 格，空鼓集合用位掩码表示。best(mask) 记忆化
返回恰好覆盖 mask 的最优 (片数, 切缝和)：每次取 mask 中行主序最小
的空鼓格，枚举以它为左上角且完整落在 mask 内的矩形——覆盖该格的
矩形左上角必然就是该格，因此分支有限。得到最优值后按字典序贪心恢
复具体划分：逐片选取使剩余子问题仍可达整体最优的最小矩形。
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Patch:
    """一片矩形修补区域，行列均为 0 基、含端点。"""

    r1: int
    c1: int
    r2: int
    c2: int

    @property
    def cells(self) -> int:
        """覆盖砖数。"""
        return (self.r2 - self.r1 + 1) * (self.c2 - self.c1 + 1)

    @property
    def perimeter(self) -> int:
        """单片四周切缝长度（矩形周长，以砖边长为单位）。"""
        return 2 * ((self.r2 - self.r1 + 1) + (self.c2 - self.c1 + 1))


@dataclass(frozen=True)
class Plan:
    """最小切缝修补规划。

    patches: 全部修补片，按 (上行, 左列, 下行, 右列) 升序；
    total_perimeter: 各片切缝长度之和。
    """

    patches: Tuple[Patch, ...]
    total_perimeter: int

    @property
    def piece_count(self) -> int:
        return len(self.patches)


def _corner_rects(rows: int, cols: int) -> List[List[Tuple[int, int, int, int]]]:
    """每个格子作为左上角时可形成的全部矩形。

    返回按格子行主序索引的列表；每项为 (掩码, 周长, 下行, 右列)，
    按 (下行, 右列) 字典序排列，供字典序恢复时直接取用。
    """

    rects: List[List[Tuple[int, int, int, int]]] = []
    for r in range(rows):
        for c in range(cols):
            options: List[Tuple[int, int, int, int]] = []
            for r2 in range(r, rows):
                for c2 in range(c, cols):
                    mask = 0
                    for rr in range(r, r2 + 1):
                        for cc in range(c, c2 + 1):
                            mask |= 1 << (rr * cols + cc)
                    perim = 2 * ((r2 - r + 1) + (c2 - c + 1))
                    options.append((mask, perim, r2, c2))
            rects.append(options)
    return rects


def plan_patches(rows: int, cols: int, grid: Sequence[Sequence[int]]) -> Plan:
    """对空鼓分布 grid（1=空鼓）求最小切缝修补规划。"""

    ones = 0
    for r in range(rows):
        for c in range(cols):
            if grid[r][c]:
                ones |= 1 << (r * cols + c)

    corner_rects = _corner_rects(rows, cols)

    @lru_cache(maxsize=None)
    def best(mask: int) -> Tuple[int, int]:
        """恰好覆盖 mask 的最优 (片数, 切缝长度和)。"""
        if mask == 0:
            return (0, 0)
        i = (mask & -mask).bit_length() - 1
        opt: Optional[Tuple[int, int]] = None
        for rmask, perim, _r2, _c2 in corner_rects[i]:
            if rmask & mask == rmask:
                cnt, total = best(mask ^ rmask)
                cand = (cnt + 1, total + perim)
                if opt is None or cand < opt:
                    opt = cand
        assert opt is not None  # 至少可取以该格为内容的 1×1 单片
        return opt

    # 字典序恢复：每片覆盖当前最左上未覆盖空鼓格，其左上角必为该格；
    # 按 (下行, 右列) 升序取首个使剩余子问题仍达整体最优的矩形。
    # 依构造，patches 已按 (上行, 左列, 下行, 右列) 升序。
    patches: List[Patch] = []
    mask = ones
    while mask:
        i = (mask & -mask).bit_length() - 1
        r, c = divmod(i, cols)
        target = best(mask)
        for rmask, perim, r2, c2 in corner_rects[i]:
            if rmask & mask != rmask:
                continue
            cnt, total = best(mask ^ rmask)
            if (cnt + 1, total + perim) == target:
                patches.append(Patch(r, c, r2, c2))
                mask ^= rmask
                break
        else:
            raise AssertionError("不可达：最优划分恢复失败")

    return Plan(
        patches=tuple(patches),
        total_perimeter=sum(p.perimeter for p in patches),
    )
