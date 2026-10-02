"""旧ARCの平行な反対角線分間の領域和を再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / v29_diagonal_region。
dataclassと5関数は原文のまま。方向探索や線分長の追加条件は設けない。
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from .既存領域転写 import Grid
from .既存凡例穴対応 import clone_grid, grid_shape
from .既存物体特徴 import dominant_background_for_grid as background_color

@dataclass(frozen=True)
class AntiDiagonalSegment:
    s: int
    r0: int
    r1: int

    @property
    def d_range(self) -> tuple[int, int]:
        return 2 * self.r0 - self.s, 2 * self.r1 - self.s

def is_rectangular(grid: Grid) -> bool:
    return bool(grid) and all(len(row) == len(grid[0]) for row in grid)

def colors(grid: Grid) -> set[int]:
    return {cell for row in grid for cell in row}

def infer_single_fill_color(train_pairs: list[dict]) -> int | None:
    fill_colors: set[int] = set()
    for pair in train_pairs:
        inp: Grid = pair["input"]
        out: Grid = pair["output"]
        if not is_rectangular(inp) or not is_rectangular(out):
            return None
        if grid_shape(inp) != grid_shape(out):
            return None
        bg = background_color(inp)
        for r, row in enumerate(inp):
            for c, value in enumerate(row):
                out_value = out[r][c]
                if value == out_value:
                    continue
                if value != bg:
                    return None
                fill_colors.add(out_value)
    if len(fill_colors) != 1:
        return None
    fill_color = next(iter(fill_colors))
    if any(fill_color in colors(pair["input"]) for pair in train_pairs):
        return None
    return fill_color

def anti_diagonal_segments(grid: Grid) -> list[AntiDiagonalSegment] | None:
    bg = background_color(grid)
    non_bg_colors = colors(grid) - {bg}
    if len(non_bg_colors) != 1:
        return None

    by_s: dict[int, list[int]] = defaultdict(list)
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            if value != bg:
                by_s[r + c].append(r)

    segments: list[AntiDiagonalSegment] = []
    for s, rows in sorted(by_s.items()):
        sorted_rows = sorted(rows)
        start = previous = sorted_rows[0]
        for row in sorted_rows[1:]:
            if row == previous + 1:
                previous = row
                continue
            segments.append(AntiDiagonalSegment(s=s, r0=start, r1=previous))
            start = previous = row
        segments.append(AntiDiagonalSegment(s=s, r0=start, r1=previous))

    if len(segments) < 2:
        return None
    return segments

def diagonal_implied_boundary_region_fill(grid: Grid, fill_color: int) -> Grid | None:
    if not is_rectangular(grid):
        return None

    segments = anti_diagonal_segments(grid)
    if not segments:
        return None

    bg = background_color(grid)
    height, width = grid_shape(grid)
    output = clone_grid(grid)
    changed = 0

    for left_index, left in enumerate(segments):
        for right in segments[left_index + 1 :]:
            if left.s == right.s:
                continue
            first, second = (left, right) if left.s < right.s else (right, left)
            first_d0, first_d1 = first.d_range
            second_d0, second_d1 = second.d_range
            overlap_d0 = max(first_d0, second_d0)
            overlap_d1 = min(first_d1, second_d1)
            if overlap_d0 > overlap_d1:
                continue

            for r in range(height):
                for c in range(width):
                    s = r + c
                    d = r - c
                    if (
                        output[r][c] == bg
                        and first.s < s < second.s
                        and overlap_d0 <= d <= overlap_d1
                    ):
                        output[r][c] = fill_color
                        changed += 1

    if changed == 0:
        return None
    return output
