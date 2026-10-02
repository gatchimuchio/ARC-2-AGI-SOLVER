"""既存v55の縦対称部分抽出。元の選択・編集量制限は変更しない。

出典: ARC-Layer-0-Functional-Compliance@454670a13024ccf28dc7e9ed9d8ee256ee6cd365
arc2_l0_agent_compiler_v55_vertical_symmetry_pruning.py
Git blob: 7cd48715c91d235af712524019f4f17526bdd499
純粋6関数と近傍・divisor定義は原文。旧component/ID/reportは除外。
"""
from __future__ import annotations
from collections import Counter
from .既存凡例穴対応 import grid_shape,clone_grid
Grid=list[list[int]]

NEIGHBORS_8 = tuple(
    (delta_row, delta_col)
    for delta_row in (-1, 0, 1)
    for delta_col in (-1, 0, 1)
    if delta_row or delta_col
)

MAX_REMOVAL_FRACTION_DIVISOR = 4

def dominant_color(grid: Grid) -> int:
    return Counter(value for row in grid for value in row).most_common(1)[0][0]

def same_color_components_8(grid: Grid, color: int) -> list[list[tuple[int, int]]]:
    height, width = grid_shape(grid)
    seen: set[tuple[int, int]] = set()
    components = []
    for row in range(height):
        for col in range(width):
            if (row, col) in seen or grid[row][col] != color:
                continue
            stack = [(row, col)]
            seen.add((row, col))
            cells = []
            while stack:
                current_row, current_col = stack.pop()
                cells.append((current_row, current_col))
                for d_row, d_col in NEIGHBORS_8:
                    next_cell = (current_row + d_row, current_col + d_col)
                    next_row, next_col = next_cell
                    if (
                        0 <= next_row < height
                        and 0 <= next_col < width
                        and next_cell not in seen
                        and grid[next_row][next_col] == color
                    ):
                        seen.add(next_cell)
                        stack.append(next_cell)
            components.append(sorted(cells))
    return components

def bbox(cells: set[tuple[int, int]] | list[tuple[int, int]]) -> list[int]:
    rows = [row for row, _ in cells]
    cols = [col for _, col in cells]
    return [min(rows), min(cols), max(rows), max(cols)]

def component_dimensions(cells: set[tuple[int, int]]) -> tuple[int, int]:
    row0, col0, row1, col1 = bbox(cells)
    return row1 - row0 + 1, col1 - col0 + 1

def vertical_prune_candidate(cells: list[tuple[int, int]]) -> dict | None:
    cell_set = set(cells)
    cols = [col for _, col in cells]
    min_col = min(cols)
    max_col = max(cols)
    best = None
    for axis2 in range(min_col * 2, max_col * 2 + 1):
        kept = {
            (row, col)
            for row, col in cell_set
            if (row, axis2 - col) in cell_set
        }
        removed = cell_set - kept
        if not kept or not removed:
            continue
        kept_height, kept_width = component_dimensions(kept)
        key = (
            len(kept),
            kept_height * kept_width,
            kept_height,
            -abs(axis2 - (min_col + max_col)),
            -axis2,
        )
        candidate = {
            "axis2": axis2,
            "kept": kept,
            "removed": removed,
            "kept_height": kept_height,
            "kept_width": kept_width,
            "score": key,
        }
        if best is None or key > best["score"]:
            best = candidate
    return best

def apply_vertical_symmetry_pruning(grid: Grid) -> tuple[Grid | None, dict | None]:
    background = dominant_color(grid)
    output = clone_grid(grid)
    actions = []
    for color in sorted({value for row in grid for value in row if value != background}):
        for cells in same_color_components_8(grid, color):
            if len(cells) < 2:
                continue
            candidate = vertical_prune_candidate(cells)
            if candidate is None:
                continue
            max_removed = max(3, len(cells) // MAX_REMOVAL_FRACTION_DIVISOR + 1)
            if len(candidate["removed"]) > max_removed:
                continue
            removed = sorted(candidate["removed"])
            for row, col in removed:
                output[row][col] = background
            actions.append(
                {
                    "color": color,
                    "component_bbox": bbox(cells),
                    "component_size": len(cells),
                    "axis2": candidate["axis2"],
                    "removed_cells": removed,
                    "removed_count": len(removed),
                    "kept_count": len(candidate["kept"]),
                    "kept_bbox": bbox(candidate["kept"]),
                    "kept_height": candidate["kept_height"],
                    "kept_width": candidate["kept_width"],
                }
            )

    if not actions:
        return None, None
    return output, {
        "background": background,
        "actions": actions,
        "action_count": len(actions),
        "changed_count": sum(action["removed_count"] for action in actions),
    }
