"""空鼓位置联合反演求解器。

每块砖是一个 0/1 变量（1 表示空鼓），每次矩形敲击检测给出一个
“区域内空鼓总数恰等于记录值”的线性等式约束。求解目标按优先级为：

1. 空鼓总数最少；
2. 在空鼓总数相同的方案中，把状态按从上到下、从左到右展开成
   0/1 序列，取字典序最小者（0=完好，0 在 1 之前）。

实现方式：约束传播 + 回溯判定可行性；先二分最小空鼓数，再逐个
位置贪心固定为“完好(0)”。网格至多 5×5=25 个变量，规模很小。

传播除了每条等式自身的上下界，还利用“区域内必再出现 rem 个空鼓”
与全局空鼓总数区间 [lo, hi] 的交互：区域外未定砖的空鼓配额被唯一
限定，由此可直接定值或提前判矛盾。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Rect:
    """一次矩形检测区域，行列均为 0 基、含端点。"""

    r1: int
    c1: int
    r2: int
    c2: int
    count: int

    def cells(self, cols: int) -> Tuple[int, ...]:
        return tuple(
            r * cols + c
            for r in range(self.r1, self.r2 + 1)
            for c in range(self.c1, self.c2 + 1)
        )


@dataclass(frozen=True)
class Solution:
    """反演结果。

    grid: 与网格同形的 0/1 列表；
    total: 空鼓总数；
    actual_counts: 与输入检测一一对应的区域实际空鼓计数。
    """

    grid: List[List[int]]
    total: int
    actual_counts: List[int]


def _feasible(
    n: int,
    constraints: Sequence[Tuple[Tuple[int, ...], int]],
    initial: Sequence[int],
    total_lo: int,
    total_hi: int,
) -> bool:
    """判定在给定前缀/取值下是否存在可行方案。

    values 中 -1 表示未定。total_lo/total_hi 限定空鼓总数区间。
    """

    values = list(initial)
    # 同一传播状态的失败记忆，避免重复搜索。
    dead: set = set()

    def propagate() -> bool:
        """传播到不动点；发现矛盾返回 False。"""
        changed = True
        while changed:
            changed = False
            ones = 0
            free: List[int] = []
            for i, v in enumerate(values):
                if v == 1:
                    ones += 1
                elif v < 0:
                    free.append(i)
            nfree = len(free)

            # 由每条等式反推“最终全局空鼓总数”的可达区间并取交：
            # 区域内未定格恰再贡献 rem 个，区域外自由格贡献 [0, n_out]。
            eff_lo = total_lo
            eff_hi = total_hi
            parsed = []
            for indices, target in constraints:
                s = 0
                inside_free: List[int] = []
                for i in indices:
                    v = values[i]
                    if v == 1:
                        s += 1
                    elif v < 0:
                        inside_free.append(i)
                rem = target - s
                n_in = len(inside_free)
                if rem < 0 or rem > n_in:
                    return False
                n_out = nfree - n_in
                eff_lo = max(eff_lo, ones + rem)
                eff_hi = min(eff_hi, ones + rem + n_out)
                parsed.append((inside_free, rem, n_in, n_out))
            if eff_lo > eff_hi or ones > eff_hi or ones + nfree < eff_lo:
                return False

            # 有效总数区间端点直接定值。
            if nfree:
                if ones == eff_hi:
                    for i in free:
                        values[i] = 0
                    changed = True
                    continue
                if ones + nfree == eff_lo:
                    for i in free:
                        values[i] = 1
                    changed = True
                    continue

            for inside_free, rem, n_in, n_out in parsed:
                if not inside_free:
                    continue
                if rem == 0:
                    for i in inside_free:
                        values[i] = 0
                    changed = True
                    break
                if rem == n_in:
                    for i in inside_free:
                        values[i] = 1
                    changed = True
                    break

                # 与有效总数区间的交互：区域外未定砖的空鼓数落在
                # [eff_lo-ones-rem, eff_hi-ones-rem]。
                if n_out:
                    out_hi = eff_hi - ones - rem
                    out_lo = eff_lo - ones - rem
                    if out_hi < 0 or out_lo > n_out:
                        return False
                    if out_hi == 0:
                        inside_set = set(inside_free)
                        for i in free:
                            if i not in inside_set:
                                values[i] = 0
                        changed = True
                        break
                    if out_lo == n_out:
                        inside_set = set(inside_free)
                        for i in free:
                            if i not in inside_set:
                                values[i] = 1
                        changed = True
                        break
        return True

    def search() -> bool:
        if not propagate():
            return False

        if all(v >= 0 for v in values):
            return True

        key = tuple(values)
        if key in dead:
            return False

        # 每个自由变量的紧迫度取其所属约束中最紧者；最紧的先分支，
        # 紧迫度相同时取行主序最早的变量。
        pressure = [0.0] * n
        for indices, target in constraints:
            s = 0
            nf = 0
            for i in indices:
                v = values[i]
                if v == 1:
                    s += 1
                elif v < 0:
                    nf += 1
            if nf:
                rem = target - s
                tight = max(rem, nf - rem) / nf  # 越接近 1 越紧
                for i in indices:
                    if values[i] < 0 and tight > pressure[i]:
                        pressure[i] = tight
        pivot = min(
            (i for i in range(n) if values[i] < 0),
            key=lambda i: (-pressure[i], i),
        )

        # 先试 0（完好），对可行性与最小化都有利。
        saved = values.copy()
        for bit in (0, 1):
            values[:] = saved
            values[pivot] = bit
            if search():
                return True
        values[:] = saved
        dead.add(key)
        return False

    return search()


def solve(rows: int, cols: int, rects: Sequence[Rect]) -> Optional[Solution]:
    """联合反演；无解返回 None。rects 需由上层完成范围校验。"""

    n = rows * cols
    constraints = [(r.cells(cols), r.count) for r in rects]
    initial = [-1] * n

    if not _feasible(n, constraints, initial, 0, n):
        return None

    # 第一步：二分最小空鼓总数（可行性关于上界单调）。
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if _feasible(n, constraints, initial, 0, mid):
            hi = mid
        else:
            lo = mid + 1
    minimum = lo

    # 第二步：行主序逐位贪心，能放 0（完好）就不放 1（空鼓），
    # 同时要求空鼓总数恰为 minimum，由此得到字典序最小方案。
    values: List[int] = [-1] * n
    for i in range(n):
        trial = values.copy()
        trial[i] = 0
        if _feasible(n, constraints, trial, minimum, minimum):
            values = trial
        else:
            values[i] = 1

    grid = [
        values[r * cols : (r + 1) * cols]
        for r in range(rows)
    ]
    actual_counts = [
        sum(values[i] for i in indices) for indices, _ in constraints
    ]
    return Solution(grid=grid, total=minimum, actual_counts=actual_counts)
