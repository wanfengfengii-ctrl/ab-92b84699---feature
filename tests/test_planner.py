"""最小切缝修补规划测试。

确定性用例验证“片数最少 → 切缝总长最短 → 坐标序列字典序最小”的
逐级取舍；随机用例与穷举所有矩形划分的暴力法逐项对照。
"""

from __future__ import annotations

import random
import unittest
from typing import List, Optional, Sequence, Tuple

from app.planner import Plan, _corner_rects, plan_patches


def grid_of(rows: int, cols: int, cells: Sequence[Tuple[int, int]]) -> List[List[int]]:
    g = [[0] * cols for _ in range(rows)]
    for r, c in cells:
        g[r][c] = 1
    return g


def plan_signature(plan: Plan) -> Tuple[int, int, Tuple[Tuple[int, int, int, int], ...]]:
    return (
        len(plan.patches),
        plan.total_perimeter,
        tuple((p.r1, p.c1, p.r2, p.c2) for p in plan.patches),
    )


def brute_force_best(
    rows: int, cols: int, ones: int
) -> Tuple[int, int, Tuple[Tuple[int, int, int, int], ...]]:
    """穷举所有矩形划分，返回最优 (片数, 总切缝, 排序坐标序列)。"""
    corner = _corner_rects(rows, cols)
    best: Optional[Tuple[int, int, Tuple[Tuple[int, int, int, int], ...]]] = None

    def rec(mask: int, pieces: List[Tuple[int, int, int, int]]) -> None:
        nonlocal best
        if mask == 0:
            cand = (
                len(pieces),
                sum(2 * ((r2 - r1 + 1) + (c2 - c1 + 1)) for r1, c1, r2, c2 in pieces),
                tuple(sorted(pieces)),
            )
            if best is None or cand < best:
                best = cand
            return
        if best is not None and len(pieces) >= best[0]:
            return
        i = (mask & -mask).bit_length() - 1
        r, c = divmod(i, cols)
        for rmask, _perim, r2, c2 in corner[i]:
            if rmask & mask == rmask:
                rec(mask ^ rmask, pieces + [(r, c, r2, c2)])

    rec(ones, [])
    assert best is not None
    return best


def check_plan_invariants(
    plan: Plan, rows: int, cols: int, grid: Sequence[Sequence[int]]
) -> None:
    """每片只含空鼓砖、片间不重叠、并集恰为全部空鼓砖、合计一致。"""
    seen = set()
    expected = {
        (r, c) for r in range(rows) for c in range(cols) if grid[r][c] == 1
    }
    covered = set()
    for p in plan.patches:
        assert 0 <= p.r1 <= p.r2 < rows and 0 <= p.c1 <= p.c2 < cols
        for r in range(p.r1, p.r2 + 1):
            for c in range(p.c1, p.c2 + 1):
                assert grid[r][c] == 1, (r, c, "修补片覆盖了完好砖")
                assert (r, c) not in seen, (r, c, "修补片重叠")
                seen.add((r, c))
                covered.add((r, c))
        assert p.cells == (p.r2 - p.r1 + 1) * (p.c2 - p.c1 + 1)
        assert p.perimeter == 2 * ((p.r2 - p.r1 + 1) + (p.c2 - p.c1 + 1))
    assert covered == expected
    assert plan.total_perimeter == sum(p.perimeter for p in plan.patches)
    assert plan.piece_count == len(plan.patches)
    keys = [(p.r1, p.c1, p.r2, p.c2) for p in plan.patches]
    assert keys == sorted(keys), "修补片应按坐标升序"


class PlannerDeterministicTests(unittest.TestCase):
    def test_no_hollow_needs_no_patch(self) -> None:
        plan = plan_patches(4, 4, grid_of(4, 4, []))
        self.assertEqual(plan.patches, ())
        self.assertEqual(plan.piece_count, 0)
        self.assertEqual(plan.total_perimeter, 0)

    def test_full_grid_single_patch(self) -> None:
        cells = [(r, c) for r in range(5) for c in range(5)]
        plan = plan_patches(5, 5, grid_of(5, 5, cells))
        self.assertEqual(plan_signature(plan), (1, 20, ((0, 0, 4, 4),)))

    def test_single_cell(self) -> None:
        plan = plan_patches(4, 5, grid_of(4, 5, [(2, 3)]))
        self.assertEqual(plan_signature(plan), (1, 4, ((2, 3, 2, 3),)))

    def test_adjacent_pair_merges(self) -> None:
        plan = plan_patches(4, 4, grid_of(4, 4, [(1, 1), (1, 2)]))
        self.assertEqual(plan_signature(plan), (1, 6, ((1, 1, 1, 2),)))

    def test_diagonal_pair_stays_separate(self) -> None:
        plan = plan_patches(4, 4, grid_of(4, 4, [(0, 0), (3, 3)]))
        self.assertEqual(
            plan_signature(plan), (2, 8, ((0, 0, 0, 0), (3, 3, 3, 3)))
        )

    def test_lexicographic_tie_break_l_shape(self) -> None:
        # L 形 (0,0) (1,0) (1,1)：两种 2 片方案切缝同为 10，
        # 坐标序列 ((0,0,0,0),(1,0,1,1)) 字典序小于 ((0,0,1,0),(1,1,1,1))。
        plan = plan_patches(4, 4, grid_of(4, 4, [(0, 0), (1, 0), (1, 1)]))
        self.assertEqual(
            plan_signature(plan), (2, 10, ((0, 0, 0, 0), (1, 0, 1, 1)))
        )

    def test_lexicographic_tie_break_plus_shape(self) -> None:
        # 十字形：横条方案与竖条方案同为 3 片、切缝 16（1×3 片周长 8，
        # 两片 1×1 各 4）；((0,1,0,1),(1,0,1,2),(2,1,2,1)) 字典序更小。
        cells = [(0, 1), (1, 0), (1, 1), (1, 2), (2, 1)]
        plan = plan_patches(3, 3, grid_of(3, 3, cells))
        self.assertEqual(
            plan_signature(plan),
            (3, 16, ((0, 1, 0, 1), (1, 0, 1, 2), (2, 1, 2, 1))),
        )

    def test_perimeter_beats_lexicographic(self) -> None:
        # 2×2 整块加孤立格：2 片方案中整片 2×2（切缝 8+4=12）
        # 优于任何同片数的细分；坐标序列不再是决定因素。
        cells = [(0, 0), (0, 1), (1, 0), (1, 1), (3, 3)]
        plan = plan_patches(4, 4, grid_of(4, 4, cells))
        self.assertEqual(
            plan_signature(plan), (2, 12, ((0, 0, 1, 1), (3, 3, 3, 3)))
        )

    def test_piece_count_dominates_perimeter(self) -> None:
        # 3×2 整块：1 片（切缝 10）优于 2 片横切（切缝 12）。
        cells = [(r, c) for r in range(3) for c in range(2)]
        plan = plan_patches(4, 4, grid_of(4, 4, cells))
        self.assertEqual(plan_signature(plan), (1, 10, ((0, 0, 2, 1),)))

    def test_sorted_output(self) -> None:
        cells = [(3, 3), (0, 2), (1, 0), (3, 0)]
        plan = plan_patches(4, 4, grid_of(4, 4, cells))
        keys = [(p.r1, p.c1, p.r2, p.c2) for p in plan.patches]
        self.assertEqual(keys, sorted(keys))


class PlannerBruteForceTests(unittest.TestCase):
    """与穷举所有划分的暴力法对照 (片数, 总切缝, 排序坐标序列)。"""

    def _assert_matches_brute(self, rows: int, cols: int, ones: int) -> None:
        grid = [
            [1 if (ones >> (r * cols + c)) & 1 else 0 for c in range(cols)]
            for r in range(rows)
        ]
        plan = plan_patches(rows, cols, grid)
        check_plan_invariants(plan, rows, cols, grid)
        self.assertEqual(plan_signature(plan), brute_force_best(rows, cols, ones))

    def test_full_grids_small(self) -> None:
        for rows, cols in ((2, 2), (2, 4), (3, 3), (3, 4), (4, 4)):
            with self.subTest(rows=rows, cols=cols):
                self._assert_matches_brute(rows, cols, (1 << (rows * cols)) - 1)

    def test_random_4x4_dense(self) -> None:
        rng = random.Random(20260925)
        for _ in range(120):
            ones = 0
            for i in range(16):
                if rng.random() < 0.6:
                    ones |= 1 << i
            self._assert_matches_brute(4, 4, ones)

    def test_random_5x5_sparse(self) -> None:
        rng = random.Random(925)
        for _ in range(80):
            ones = 0
            for i in range(25):
                if rng.random() < 0.35:
                    ones |= 1 << i
            self._assert_matches_brute(5, 5, ones)

    def test_random_5x5_dense_invariants_only(self) -> None:
        # 高密度下穷举过慢，仅校验划分不变量与最优性下界。
        rng = random.Random(55)
        for _ in range(30):
            ones = 0
            for i in range(25):
                if rng.random() < 0.7:
                    ones |= 1 << i
            grid = [
                [1 if (ones >> (r * 5 + c)) & 1 else 0 for c in range(5)]
                for r in range(5)
            ]
            plan = plan_patches(5, 5, grid)
            check_plan_invariants(plan, 5, 5, grid)
            n_ones = bin(ones).count("1")
            if n_ones:
                self.assertGreaterEqual(plan.piece_count, 1)
                self.assertLessEqual(plan.piece_count, n_ones)
                self.assertGreaterEqual(plan.total_perimeter, 4 * plan.piece_count)


if __name__ == "__main__":
    unittest.main()
