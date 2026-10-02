"""旧ARCの対角線橋と交点からの垂直対角線を再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / v72_diagonal_bridge_crossing_emitter。
5関数は原文のまま。主色を教師から選び、描画優先は別guardで排除する。
"""
from __future__ import annotations
from itertools import combinations
from typing import Any
from .既存領域転写 import Grid
from .既存凡例穴対応 import grid_shape, clone_grid
from .既存物体特徴 import dominant_background_for_grid as dominant_color

MAX_PREDICT_PRIMARY_MARKERS = 30

def foreground_colors(grid: Grid) -> list[int]:
    background = dominant_color(grid)
    return sorted({value for row in grid for value in row if value != background})

def foreground_count(grid: Grid) -> int:
    background = dominant_color(grid)
    return sum(1 for row in grid for value in row if value != background)

def diagonal_segment(
    first: tuple[int, int],
    second: tuple[int, int],
) -> list[tuple[int, int]]:
    first_row, first_col = first
    second_row, second_col = second
    row_delta = second_row - first_row
    col_delta = second_col - first_col
    if abs(row_delta) != abs(col_delta) or row_delta == 0:
        return []
    row_step = 1 if row_delta > 0 else -1
    col_step = 1 if col_delta > 0 else -1
    return [
        (first_row + index * row_step, first_col + index * col_step)
        for index in range(abs(row_delta) + 1)
    ]

def full_diagonal_through(
    height: int,
    width: int,
    row: int,
    col: int,
    direction: str,
) -> list[tuple[int, int]]:
    if direction == "main":
        offset = row - col
        return [
            (next_row, next_row - offset)
            for next_row in range(height)
            if 0 <= next_row - offset < width
        ]

    total = row + col
    return [
        (next_row, total - next_row)
        for next_row in range(height)
        if 0 <= total - next_row < width
    ]

def render_diagonal_bridge_crossing(
    grid: Grid,
    primary_color: int,
) -> tuple[Grid | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    background = dominant_color(grid)
    output = clone_grid(grid)
    primary_positions = [
        (row, col)
        for row, line in enumerate(grid)
        for col, value in enumerate(line)
        if value == primary_color
    ]
    if not (2 <= len(primary_positions) <= MAX_PREDICT_PRIMARY_MARKERS):
        return None, {
            "background": background,
            "primary_color": primary_color,
            "primary_marker_count": len(primary_positions),
            "failure": "primary_marker_count_out_of_bounds",
        }

    bridges: list[dict[str, Any]] = []
    blockers: list[tuple[int, int, int, str]] = []
    for first, second in combinations(primary_positions, 2):
        segment = diagonal_segment(first, second)
        if not segment:
            continue
        interior = segment[1:-1]
        if not interior:
            continue
        if any(grid[row][col] == primary_color for row, col in interior):
            continue
        if not any(grid[row][col] == background for row, col in interior):
            continue
        direction = "main" if second[0] - first[0] == second[1] - first[1] else "anti"
        bridges.append({"endpoints": [first, second], "cells": segment, "direction": direction})

    if not bridges:
        return None, {
            "background": background,
            "primary_color": primary_color,
            "primary_marker_count": len(primary_positions),
            "failure": "no_primary_bridges",
        }

    filled_primary: set[tuple[int, int]] = set()
    for bridge in bridges:
        first, second = bridge["endpoints"]
        for row, col in bridge["cells"]:
            if grid[row][col] == background:
                output[row][col] = primary_color
                filled_primary.add((row, col))
            elif grid[row][col] != primary_color and (row, col) not in {first, second}:
                perpendicular = "anti" if bridge["direction"] == "main" else "main"
                blockers.append((row, col, grid[row][col], perpendicular))

    filled_blocker: set[tuple[int, int]] = set()
    for row, col, blocker_color, perpendicular in blockers:
        for next_row, next_col in full_diagonal_through(height, width, row, col, perpendicular):
            if grid[next_row][next_col] == background and output[next_row][next_col] == background:
                output[next_row][next_col] = blocker_color
                filled_blocker.add((next_row, next_col))

    record = {
        "background": background,
        "primary_color": primary_color,
        "shape": [height, width],
        "primary_marker_count": len(primary_positions),
        "bridge_count": len(bridges),
        "bridges": [
            {
                "endpoints": [list(cell) for cell in bridge["endpoints"]],
                "direction": bridge["direction"],
                "length": len(bridge["cells"]),
            }
            for bridge in bridges
        ],
        "blockers": [
            {
                "cell": [row, col],
                "color": color,
                "perpendicular_direction": perpendicular,
            }
            for row, col, color, perpendicular in blockers
        ],
        "filled_primary_cells": [list(cell) for cell in sorted(filled_primary)],
        "filled_blocker_cells": [list(cell) for cell in sorted(filled_blocker)],
    }
    if output == grid:
        return None, {**record, "failure": "no_change"}
    return output, record
