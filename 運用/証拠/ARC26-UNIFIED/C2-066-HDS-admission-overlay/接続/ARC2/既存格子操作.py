"""旧ARCの格子分割・色mask・D4の純粋定義だけを再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_fit_generator.py。
"""
from __future__ import annotations
from collections import Counter
from typing import Any
from .既存領域転写 import Grid, BBox, Cell
from .既存凡例穴対応 import clone_grid, grid_shape

def separator_lattice_segments(length: int, separators: list[int]) -> list[tuple[int, int]]:
    points = [-1] + sorted(separators) + [length]
    return [
        (points[index] + 1, points[index + 1] - 1)
        for index in range(len(points) - 1)
        if points[index] + 1 <= points[index + 1] - 1
    ]


def detect_separator_lattice(grid: Grid) -> dict[str, Any] | None:
    if not grid or not grid[0]:
        return None
    height, width = grid_shape(grid)
    row_records: list[tuple[int, int]] = []
    for row in range(height):
        row_values = {int(value) for value in grid[row]}
        if len(row_values) == 1:
            row_records.append((row, next(iter(row_values))))
    col_records: list[tuple[int, int]] = []
    for col in range(width):
        col_values = {int(grid[row][col]) for row in range(height)}
        if len(col_values) == 1:
            col_records.append((col, next(iter(col_values))))
    if not row_records or not col_records:
        return None
    separator_colors = {color for _, color in row_records} | {color for _, color in col_records}
    if len(separator_colors) != 1:
        return None
    separator_color = next(iter(separator_colors))
    row_segments = separator_lattice_segments(height, [row for row, _ in row_records])
    col_segments = separator_lattice_segments(width, [col for col, _ in col_records])
    if len(row_segments) < 2 or len(col_segments) < 2:
        return None
    non_separator_values = [
        int(grid[row][col])
        for row in range(height)
        for col in range(width)
        if row not in {item[0] for item in row_records}
        and col not in {item[0] for item in col_records}
        and int(grid[row][col]) != separator_color
    ]
    if not non_separator_values:
        return None
    background_color = Counter(non_separator_values).most_common(1)[0][0]
    return {
        "separator_color": int(separator_color),
        "background_color": int(background_color),
        "row_segments": row_segments,
        "col_segments": col_segments,
        "separator_rows": [row for row, _ in row_records],
        "separator_cols": [col for col, _ in col_records],
    }


def lattice_tile_mask(grid: Grid, bbox: BBox, color: int) -> frozenset[Cell]:
    row0, col0, row1, col1 = bbox
    return frozenset(
        (row - row0, col - col0)
        for row in range(row0, row1 + 1)
        for col in range(col0, col1 + 1)
        if int(grid[row][col]) == int(color)
    )


def transform_grid_by_name(grid: Grid, transform_name: str) -> Grid | None:
    if transform_name == "identity":
        return clone_grid(grid)
    if transform_name == "rot90":
        return [list(row) for row in zip(*grid[::-1])]
    if transform_name == "rot180":
        return [row[::-1] for row in grid[::-1]]
    if transform_name == "rot270":
        return [list(row) for row in zip(*grid)][::-1]
    if transform_name == "flip_h":
        return [row[::-1] for row in grid]
    if transform_name == "flip_v":
        return grid[::-1]
    if transform_name == "transpose":
        return [list(row) for row in zip(*grid)]
    if transform_name == "anti_transpose":
        return [list(row) for row in zip(*[row[::-1] for row in grid[::-1]])]
    return None


