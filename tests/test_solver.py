"""求解器测试。

4×4 场景下穷举全部 2^16 种空鼓分布求独立最优解，与求解器结果逐项对照，
严格验证“空鼓总数最少、行主序字典序最小”的联合判定规则。
"""

from __future__ import annotations

import random
import unittest
from typing import List, Optional, Sequence, Tuple

from app.solver import Rect, Solution, solve


def rect_mask(r1: int, c1: int, r2: int, c2: int, rows: int, cols: int) -> int:
    m = 0
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            m |= 1 << (r * cols + c)
    return m


def brute_force_optimum(
    rows: int, cols: int, rects: Sequence[Rect]
) -> Optional[Tuple[int, Tuple[int, ...]]]:
    """穷举返回 (最少空鼓数, 字典序最小的行主序 0/1 序列)。"""
    n = rows * cols
    targets = [(rect_mask(r.r1, r.c1, r.r2, r.c2, rows, cols), r.count) for r in rects]
    best: Optional[Tuple[int, Tuple[int, ...]]] = None
    for mask in range(1 << n):
        if all((mask & m).bit_count() == t for m, t in targets):
            seq = tuple((mask >> i) & 1 for i in range(n))
            cand = (mask.bit_count(), seq)
            if best is None or cand < best:
                best = cand
    return best


def check_constraints(
    sol: Solution, rows: int, cols: int, rects: Sequence[Rect]
) -> None:
    assert sol.actual_counts == [r.count for r in rects]
    assert len(sol.grid) == rows and all(len(row) == cols for row in sol.grid)
    flat = [v for row in sol.grid for v in row]
    assert sum(flat) == sol.total
    for rect, actual in zip(rects, sol.actual_counts):
        got = sum(
            sol.grid[r][c]
            for r in range(rect.r1, rect.r2 + 1)
            for c in range(rect.c1, rect.c2 + 1)
        )
        assert got == actual == rect.count


class SolverBasicTests(unittest.TestCase):
    def test_all_intact_solution(self) -> None:
        rects = [
            Rect(0, 0, 3, 3, 0),
            Rect(0, 0, 1, 1, 0),
            Rect(2, 2, 3, 3, 0),
        ]
        sol = solve(4, 4, rects)
        self.assertIsNotNone(sol)
        check_constraints(sol, 4, 4, rects)
        self.assertEqual(sol.total, 0)
        self.assertEqual(sol.grid, [[0] * 4 for _ in range(4)])

    def test_unsat_directly_contradictory(self) -> None:
        # 整墙只有 1 块空鼓，但顶行 4 块全部空鼓，互不相容。
        rects = [
            Rect(0, 0, 3, 3, 1),
            Rect(0, 0, 0, 3, 4),
            Rect(0, 0, 1, 1, 1),
        ]
        self.assertIsNone(solve(4, 4, rects))

    def test_unsat_count_exceeds_area_is_rejected_by_caller_model(self) -> None:
        # 即便绕过 API 校验构造出超出面积的计数，求解器也必须判无解。
        rects = [Rect(0, 0, 0, 0, 2), Rect(0, 0, 3, 3, 2), Rect(1, 1, 2, 2, 1)]
        self.assertIsNone(solve(4, 4, rects))

    def test_minimum_weight_prefers_single_hollow(self) -> None:
        # 左上角 2×2 恰有 1 块空鼓，其余位置不应出现任何空鼓；
        # 字典序最小意味着越早的位置越优先取 0，故空鼓落在 (2,2)。
        rects = [
            Rect(0, 0, 1, 1, 1),
            Rect(0, 0, 3, 3, 1),
            Rect(2, 0, 3, 3, 0),
        ]
        sol = solve(4, 4, rects)
        self.assertIsNotNone(sol)
        check_constraints(sol, 4, 4, rects)
        self.assertEqual(sol.total, 1)
        self.assertEqual(sol.grid[1][1], 1)
        self.assertEqual(sol.grid[0][0], 0)
        self.assertEqual(sol.grid[0][1], 0)
        self.assertEqual(sol.grid[1][0], 0)

    def test_lexicographic_pushes_hollow_to_later_position(self) -> None:
        # 整墙仅 1 块空鼓且位于第一行前两格之一：序列 0,1,... 比 1,0,... 更小。
        rects = [
            Rect(0, 0, 3, 3, 1),
            Rect(0, 0, 0, 1, 1),
            Rect(0, 2, 3, 3, 0),
        ]
        sol = solve(4, 4, rects)
        self.assertIsNotNone(sol)
        self.assertEqual(sol.total, 1)
        self.assertEqual(sol.grid[0][0], 0)
        self.assertEqual(sol.grid[0][1], 1)

    def test_multiple_hollows_unique_layout(self) -> None:
        # 两条不相交的整行记录与整墙合计共同锁定布局。
        rects = [
            Rect(0, 0, 0, 3, 2),
            Rect(3, 0, 3, 3, 1),
            Rect(1, 0, 2, 3, 0),
            Rect(0, 0, 3, 3, 3),
        ]
        sol = solve(4, 4, rects)
        self.assertIsNotNone(sol)
        check_constraints(sol, 4, 4, rects)
        self.assertEqual(sol.total, 3)
        # 顶行字典序最小：空鼓尽量靠右 -> 第 3、4 列
        self.assertEqual(sol.grid[0], [0, 0, 1, 1])
        self.assertEqual(sol.grid[3], [0, 0, 0, 1])

    def test_5x5_twelve_rectangles_feasible(self) -> None:
        rng = random.Random(20260925)
        rects: List[Rect] = []
        for _ in range(12):
            r1, r2 = sorted(rng.sample(range(5), 2))
            c1, c2 = sorted(rng.sample(range(5), 2))
            area = (r2 - r1 + 1) * (c2 - c1 + 1)
            rects.append(Rect(r1, c1, r2, c2, rng.randint(0, area)))
        sol = solve(5, 5, rects)
        if sol is not None:
            check_constraints(sol, 5, 5, rects)
            self.assertGreaterEqual(sol.total, 0)
        # 随机出的记录可能无解，两种结果都合法；再测一组由已知布局
        # （空鼓位于 (1,1)、(2,4)、(4,2)、(5,5)，0 基）构造的必可行记录。
        feasible_rects = [
            Rect(0, 0, 4, 4, 4),  # 整墙计数锁定总数恰为 4
            Rect(0, 0, 2, 2, 1),  # 左上 3×3 仅含 (1,1)
            Rect(1, 1, 4, 4, 2),  # 含 (2,4)、(5,5)
            Rect(0, 3, 4, 4, 2),  # 最右两列含 (2,4)、(5,5)
            Rect(3, 0, 4, 2, 1),  # 左下 2×3 仅含 (4,2)
            Rect(0, 0, 1, 4, 2),  # 前两行含 (1,1)、(2,4)
        ]
        while len(feasible_rects) < 12:
            feasible_rects.append(feasible_rects[len(feasible_rects) % 6])
        sol2 = solve(5, 5, feasible_rects)
        self.assertIsNotNone(sol2)
        if sol2 is not None:
            check_constraints(sol2, 5, 5, feasible_rects)
            self.assertEqual(sol2.total, 4)


class SolverBruteForceTests(unittest.TestCase):
    """与穷举最优解逐位对照（4×4 = 65536 种分布）。"""

    def _assert_matches_brute_force(
        self, rects: Sequence[Rect], rows: int = 4, cols: int = 4
    ) -> None:
        expected = brute_force_optimum(rows, cols, rects)
        got = solve(rows, cols, rects)
        if expected is None:
            self.assertIsNone(got)
            return
        self.assertIsNotNone(got)
        assert got is not None
        check_constraints(got, rows, cols, rects)
        exp_total, exp_seq = expected
        self.assertEqual(got.total, exp_total)
        got_seq = tuple(v for row in got.grid for v in row)
        self.assertEqual(got_seq, exp_seq)

    def test_bf_case_1_overlapping(self) -> None:
        self._assert_matches_brute_force([
            Rect(0, 0, 2, 2, 2),
            Rect(1, 1, 3, 3, 2),
            Rect(0, 2, 3, 3, 3),
        ])

    def test_bf_case_2_full_grid_partials(self) -> None:
        self._assert_matches_brute_force([
            Rect(0, 0, 3, 3, 3),
            Rect(0, 0, 1, 3, 2),
            Rect(2, 0, 3, 3, 1),
            Rect(0, 0, 3, 1, 2),
        ])

    def test_bf_case_3_unsat(self) -> None:
        self._assert_matches_brute_force([
            Rect(0, 0, 3, 3, 2),
            Rect(0, 0, 0, 3, 3),
            Rect(3, 0, 3, 3, 3),
        ])

    def test_bf_case_4_all_zero_and_zeros(self) -> None:
        self._assert_matches_brute_force([
            Rect(0, 0, 3, 3, 0),
            Rect(1, 1, 2, 2, 0),
            Rect(0, 3, 3, 3, 0),
        ])

    def test_bf_random_cases(self) -> None:
        rng = random.Random(42)
        # 随机生成较“松”的记录，保证有一定概率出现可行解与多解分歧。
        for _ in range(6):
            rects = []
            for _ in range(rng.randint(3, 6)):
                r1, r2 = sorted(rng.sample(range(4), 2))
                c1, c2 = sorted(rng.sample(range(4), 2))
                area = (r2 - r1 + 1) * (c2 - c1 + 1)
                target = rng.randint(0, max(area - 1, 0))
                rects.append(Rect(r1, c1, r2, c2, target))
            self._assert_matches_brute_force(rects)


if __name__ == "__main__":
    unittest.main()
