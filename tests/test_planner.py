"""最小切缝修补规划测试。

除针对性用例外，还在小规模网格上穷举全部“只含空鼓砖的轴对齐矩形划分”，
独立按（片数、切缝总长、坐标序列字典序）求最优，与规划器逐项对照。
"""

from __future__ import annotations

import random
import unittest
from typing import Dict, List, Optional, Set, Tuple

from app.planner import Patch, RepairPlan, plan_repairs

Key = Tuple[int, int, int, int]


def hollow_set(grid: List[List[int]]) -> Set[Tuple[int, int]]:
    return {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == 1}


def check_plan_invariants(plan: RepairPlan, grid: List[List[int]]) -> None:
    rows, cols = len(grid), len(grid[0])
    hollows = hollow_set(grid)
    covered: Set[Tuple[int, int]] = set()
    assert plan.piece_count == len(plan.pieces)
    total_cut = 0
    keys = [p.key for p in plan.pieces]
    assert keys == sorted(keys), "修补片必须按左上至右下排序"
    for p in plan.pieces:
        assert 1 <= p.r1 <= p.r2 <= rows
        assert 1 <= p.c1 <= p.c2 <= cols
        cells = {
            (r, c)
            for r in range(p.r1 - 1, p.r2)
            for c in range(p.c1 - 1, p.c2)
        }
        assert cells, "修补片不能为空"
        assert cells <= hollows, "修补片只能覆盖空鼓砖"
        assert not (covered & cells), "修补片不得重叠"
        covered |= cells
        assert p.cells == len(cells)
        perimeter = 2 * ((p.r2 - p.r1 + 1) + (p.c2 - p.c1 + 1))
        assert p.cut_length == perimeter
        total_cut += perimeter
    assert covered == hollows, "所有空鼓砖必须恰好归入一片"
    assert plan.total_cut_length == total_cut


def brute_force_plan(grid: List[List[int]]) -> Optional[Tuple[int, int, Tuple[Key, ...]]]:
    """穷举全部合法矩形划分，返回 (片数, 切缝总长, 排序后的坐标键序列) 的最优者。"""
    rows, cols = len(grid), len(grid[0])
    hollows = hollow_set(grid)
    if not hollows:
        return (0, 0, ())

    candidates: List[Tuple[Key, frozenset]] = []
    for r1 in range(rows):
        for c1 in range(cols):
            for r2 in range(r1, rows):
                for c2 in range(c1, cols):
                    cells = frozenset(
                        (r, c)
                        for r in range(r1, r2 + 1)
                        for c in range(c1, c2 + 1)
                    )
                    if cells <= hollows:
                        candidates.append(((r1 + 1, c1 + 1, r2 + 1, c2 + 1), cells))

    by_anchor: Dict[Tuple[int, int], List[Tuple[Key, frozenset]]] = {}
    for key, cells in candidates:
        anchor = min(cells)
        by_anchor.setdefault(anchor, []).append((key, cells))

    best: Optional[Tuple[int, int, Tuple[Key, ...]]] = None

    def search(covered: frozenset, chosen: List[Key], cut: int) -> None:
        nonlocal best
        remaining = hollows - covered
        if not remaining:
            signature = (len(chosen), cut, tuple(sorted(chosen)))
            if best is None or signature < best:
                best = signature
            return
        if best is not None and len(chosen) + 1 > best[0]:
            return  # 片数已不可能更优
        anchor = min(remaining)
        for key, cells in by_anchor[anchor]:
            if not (cells & covered):
                h, w = key[2] - key[0] + 1, key[3] - key[1] + 1
                search(covered | cells, chosen + [key], cut + 2 * (h + w))

    search(frozenset(), [], 0)
    return best


def make_grid(rows: int, cols: int, hollows: List[Tuple[int, int]]) -> List[List[int]]:
    grid = [[0] * cols for _ in range(rows)]
    for r, c in hollows:
        grid[r][c] = 1
    return grid


class PlannerBasicTests(unittest.TestCase):
    def test_no_hollow_empty_plan(self) -> None:
        plan = plan_repairs(make_grid(4, 4, []))
        self.assertEqual(plan.piece_count, 0)
        self.assertEqual(plan.total_cut_length, 0)
        self.assertEqual(plan.pieces, ())

    def test_single_hollow_single_patch(self) -> None:
        plan = plan_repairs(make_grid(4, 4, [(2, 3)]))
        check_plan_invariants(plan, make_grid(4, 4, [(2, 3)]))
        self.assertEqual(plan.piece_count, 1)
        self.assertEqual(plan.total_cut_length, 4)
        self.assertEqual(plan.pieces[0], Patch(3, 4, 3, 4, 1, 4))

    def test_full_grid_one_patch(self) -> None:
        grid = [[1] * 5 for _ in range(5)]
        plan = plan_repairs(grid)
        check_plan_invariants(plan, grid)
        self.assertEqual(plan.piece_count, 1)
        self.assertEqual(plan.pieces[0], Patch(1, 1, 5, 5, 25, 20))
        self.assertEqual(plan.total_cut_length, 20)

    def test_diagonal_four_singles_sorted(self) -> None:
        hollows = [(0, 0), (1, 1), (2, 2), (3, 3)]
        grid = make_grid(4, 4, hollows)
        plan = plan_repairs(grid)
        check_plan_invariants(plan, grid)
        self.assertEqual(plan.piece_count, 4)
        self.assertEqual(plan.total_cut_length, 16)
        self.assertEqual(
            [p.key for p in plan.pieces],
            [(1, 1, 1, 1), (2, 2, 2, 2), (3, 3, 3, 3), (4, 4, 4, 4)],
        )

    def test_min_pieces_prefers_large_rectangle(self) -> None:
        # 3 行 2 列缺左下角：2×2 整块 + 1×1 单片，共 2 片，周长 8+4=12。
        hollows = [(0, 0), (0, 1), (1, 0), (1, 1), (2, 1)]
        grid = make_grid(3, 2, hollows)
        plan = plan_repairs(grid)
        check_plan_invariants(plan, grid)
        self.assertEqual(plan.piece_count, 2)
        self.assertEqual(plan.total_cut_length, 12)
        self.assertEqual(
            [p.key for p in plan.pieces], [(1, 1, 2, 2), (3, 2, 3, 2)]
        )

    def test_zigzag_two_horizontal_pieces_share_edge(self) -> None:
        # 错行相连的 Z 形四砖：只能由两条 1×2 组成（共边不重叠）。
        hollows = [(0, 0), (0, 1), (1, 1), (1, 2)]
        grid = make_grid(2, 3, hollows)
        plan = plan_repairs(grid)
        check_plan_invariants(plan, grid)
        self.assertEqual(plan.piece_count, 2)
        self.assertEqual(plan.total_cut_length, 12)
        self.assertEqual(
            [p.key for p in plan.pieces], [(1, 1, 1, 2), (2, 2, 2, 3)]
        )

    def test_perimeter_tie_break_lexicographic(self) -> None:
        # L 形三砖：横排+单块 与 竖排+单块 均为 2 片、周长 10；
        # 坐标序列 (1,1,1,2)... 字典序小于 (1,1,2,1)...，取横排方案。
        hollows = [(0, 0), (0, 1), (1, 0)]
        grid = make_grid(2, 2, hollows)
        plan = plan_repairs(grid)
        check_plan_invariants(plan, grid)
        self.assertEqual(
            [p.key for p in plan.pieces], [(1, 1, 1, 2), (2, 1, 2, 1)]
        )
        self.assertEqual(plan.total_cut_length, 10)

    def test_intact_brick_never_included(self) -> None:
        # 空鼓环绕一块完好砖：任何包含中心的大片都非法，规划须绕开。
        hollows = [
            (0, 0), (0, 1), (0, 2),
            (1, 0),         (1, 2),
            (2, 0), (2, 1), (2, 2),
        ]
        grid = make_grid(3, 3, hollows)
        plan = plan_repairs(grid)
        check_plan_invariants(plan, grid)
        for p in plan.pieces:
            self.assertFalse(p.r1 == 1 and p.c1 == 1 and p.r2 >= 2 and p.c2 >= 2)


class PlannerBruteForceTests(unittest.TestCase):
    def _assert_matches_brute(self, grid: List[List[int]]) -> None:
        plan = plan_repairs(grid)
        check_plan_invariants(plan, grid)
        expected = brute_force_plan(grid)
        self.assertIsNotNone(expected)
        assert expected is not None
        exp_count, exp_cut, exp_keys = expected
        self.assertEqual(plan.piece_count, exp_count)
        self.assertEqual(plan.total_cut_length, exp_cut)
        self.assertEqual(tuple(p.key for p in plan.pieces), exp_keys)

    def test_bf_tailored_shapes(self) -> None:
        shapes = [
            [(0, 0)],
            [(0, 0), (0, 1), (1, 0), (1, 1)],
            [(r, c) for r in range(3) for c in range(3)],
            [(0, 0), (0, 2), (2, 0), (2, 2)],
            [(0, 0), (0, 1), (1, 1), (2, 1), (2, 2)],
            [(r, c) for r in range(3) for c in range(3) if (r, c) != (1, 1)],
            [(0, 0), (1, 0), (1, 1), (2, 1)],
        ]
        for hollows in shapes:
            self._assert_matches_brute(make_grid(3, 3, hollows))

    def test_bf_random_3x3(self) -> None:
        rng = random.Random(20260925)
        for _ in range(120):
            hollows = [
                (r, c)
                for r in range(3)
                for c in range(3)
                if rng.random() < 0.55
            ]
            self._assert_matches_brute(make_grid(3, 3, hollows))

    def test_bf_random_sparse_4x4(self) -> None:
        rng = random.Random(7)
        for _ in range(40):
            hollows = [
                (r, c)
                for r in range(4)
                for c in range(4)
                if rng.random() < 0.3
            ]
            self._assert_matches_brute(make_grid(4, 4, hollows))


if __name__ == "__main__":
    unittest.main()
