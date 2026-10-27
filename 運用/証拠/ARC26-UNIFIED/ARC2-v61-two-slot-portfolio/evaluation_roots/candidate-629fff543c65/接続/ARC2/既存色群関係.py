"""旧ARCの色集合・境界箱整列関係だけを再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 の同名定義。
"""

from __future__ import annotations

from functools import lru_cache

from typing import NamedTuple

from .既存領域転写 import Grid, Cell, BBox

def scaffold_legend_color_cells(grid: Grid, color: int) -> set[Cell]:
    return {
        (row_index, col_index)
        for row_index, row in enumerate(grid)
        for col_index, value in enumerate(row)
        if value == color
    }

def scaffold_legend_bbox(cells: set[Cell]) -> BBox:
    rows = [row for row, _ in cells]
    cols = [col for _, col in cells]
    return min(rows), min(cols), max(rows), max(cols)

class BBoxRelationRecord(NamedTuple):
    row_overlap: int
    col_overlap: int
    row_gap: int
    col_gap: int
    chebyshev_gap: int
    manhattan_gap: int
    disjoint: bool
    adjacent_or_overlapping: bool
    same_bbox: bool
    same_bbox_shape: bool
    first_contains_second: bool
    second_contains_first: bool
    first_strictly_contains_second: bool
    second_strictly_contains_first: bool
    aligned_directions: tuple[str, ...]

@lru_cache(maxsize=32768)
def bbox_relation_for_bboxes(first: BBox, second: BBox) -> BBoxRelationRecord:
    first_row0, first_col0, first_row1, first_col1 = first
    second_row0, second_col0, second_row1, second_col1 = second
    row_overlap = max(0, min(first_row1, second_row1) - max(first_row0, second_row0) + 1)
    col_overlap = max(0, min(first_col1, second_col1) - max(first_col0, second_col0) + 1)
    horizontal_gap = max(second_col0 - first_col1 - 1, first_col0 - second_col1 - 1)
    vertical_gap = max(second_row0 - first_row1 - 1, first_row0 - second_row1 - 1)
    row_gap = max(0, vertical_gap)
    col_gap = max(0, horizontal_gap)
    disjoint = (
        first_row1 < second_row0
        or second_row1 < first_row0
        or first_col1 < second_col0
        or second_col1 < first_col0
    )
    aligned_directions: list[str] = []
    if first_row0 == second_row0 and first_row1 == second_row1:
        if second_col1 < first_col0:
            aligned_directions.append("L")
        if second_col0 > first_col1:
            aligned_directions.append("R")
    if first_col0 == second_col0 and first_col1 == second_col1:
        if second_row1 < first_row0:
            aligned_directions.append("U")
        if second_row0 > first_row1:
            aligned_directions.append("D")
    return BBoxRelationRecord(
        row_overlap=row_overlap,
        col_overlap=col_overlap,
        row_gap=row_gap,
        col_gap=col_gap,
        chebyshev_gap=max(row_gap, col_gap),
        manhattan_gap=row_gap + col_gap,
        disjoint=disjoint,
        adjacent_or_overlapping=(row_overlap > 0 and horizontal_gap <= 0)
        or (col_overlap > 0 and vertical_gap <= 0),
        same_bbox=first == second,
        same_bbox_shape=(first_row1 - first_row0, first_col1 - first_col0)
        == (second_row1 - second_row0, second_col1 - second_col0),
        first_contains_second=(
            first_row0 <= second_row0
            and first_col0 <= second_col0
            and second_row1 <= first_row1
            and second_col1 <= first_col1
        ),
        second_contains_first=(
            second_row0 <= first_row0
            and second_col0 <= first_col0
            and first_row1 <= second_row1
            and first_col1 <= second_col1
        ),
        first_strictly_contains_second=(
            first_row0 < second_row0
            and first_col0 < second_col0
            and second_row1 < first_row1
            and second_col1 < first_col1
        ),
        second_strictly_contains_first=(
            second_row0 < first_row0
            and second_col0 < first_col0
            and first_row1 < second_row1
            and first_col1 < second_col1
        ),
        aligned_directions=tuple(aligned_directions),
    )
