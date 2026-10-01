"""旧ARCの汎用物体抽出・九特徴・教師辺対応だけを再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 の同名定義。
最近傍分類、large_cross_top_prior、固定役割色は含めない。
"""

from __future__ import annotations

from collections import deque

from functools import lru_cache

from typing import Any

from .既存領域転写 import Cell, BBox, Grid, GridKey, grid_key, _bbox_for_cells, ORTHOGONAL_DIRECTIONS, DIAGONAL_DIRECTIONS

ComponentRecord = tuple[int, tuple[Cell, ...], BBox, int]

def _record(color: int, cells: list[Cell]) -> ComponentRecord:
    sorted_cells = tuple(sorted(cells))
    return int(color), sorted_cells, _bbox_for_cells(cells), len(cells)

@lru_cache(maxsize=8192)
def _same_color_component_records(
    key: GridKey,
    color: int,
    include_diagonal: bool,
) -> tuple[ComponentRecord, ...]:
    height = len(key)
    width = len(key[0]) if key else 0
    directions = ORTHOGONAL_DIRECTIONS + (DIAGONAL_DIRECTIONS if include_diagonal else tuple())
    seen: set[Cell] = set()
    components: list[ComponentRecord] = []

    for row in range(height):
        for col in range(width):
            if key[row][col] != color or (row, col) in seen:
                continue
            queue: deque[Cell] = deque([(row, col)])
            seen.add((row, col))
            cells: list[Cell] = []
            while queue:
                current_row, current_col = queue.popleft()
                cells.append((current_row, current_col))
                for row_delta, col_delta in directions:
                    next_row = current_row + row_delta
                    next_col = current_col + col_delta
                    next_cell = (next_row, next_col)
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if next_cell in seen or key[next_row][next_col] != color:
                        continue
                    seen.add(next_cell)
                    queue.append(next_cell)
            components.append(_record(color, cells))

    return tuple(sorted(components, key=lambda component: (component[2], component[3])))

def color_component_dicts_for_grid(
    grid: Grid,
    color: int,
    include_diagonal: bool = False,
) -> list[dict[str, Any]]:
    return [
        {
            "color": int(record_color),
            "cells": set(cells),
            "bbox": bbox,
            "size": size,
        }
        for record_color, cells, bbox, size in _same_color_component_records(
            grid_key(grid),
            int(color),
            bool(include_diagonal),
        )
    ]

@lru_cache(maxsize=8192)
def _color_stats_for_key(key: GridKey) -> tuple[tuple[int, int, int], ...]:
    counts: dict[int, int] = {}
    first_seen: dict[int, int] = {}
    offset = 0
    for row in key:
        for value in row:
            counts[value] = counts.get(value, 0) + 1
            if value not in first_seen:
                first_seen[value] = offset
            offset += 1
    return tuple((color, counts[color], first_seen[color]) for color in first_seen)

def _dominant_from_stats(stats: tuple[tuple[int, int, int], ...]) -> int:
    if not stats:
        raise IndexError("list index out of range")
    return max(stats, key=lambda item: (item[1], -item[2]))[0]

def dominant_background_for_grid(grid: Grid) -> int:
    return _dominant_from_stats(_color_stats_for_key(grid_key(grid)))

def color_components(grid: Grid, color: int, include_diagonal: bool = False) -> list[dict[str, Any]]:
    return color_component_dicts_for_grid(grid, color, include_diagonal=include_diagonal)

def edge_pack_components(grid: Grid, background_color: int) -> list[dict[str, Any]]:
    colors = sorted({value for row in grid for value in row if value != background_color})
    components: list[dict[str, Any]] = []
    for color in colors:
        components.extend(color_components(grid, color, include_diagonal=True))
    return sorted(components, key=lambda component: (component["bbox"], component["color"]))

def edge_pack_component_feature(component: dict[str, Any]) -> list[float]:
    row_min, col_min, row_max, col_max = component["bbox"]
    height = row_max - row_min + 1
    width = col_max - col_min + 1
    mask = {(row - row_min, col - col_min) for row, col in component["cells"]}
    size = len(mask)
    return [
        float(height),
        float(width),
        float(size),
        float(sum(1 for row, _ in mask if row == 0)),
        float(sum(1 for row, _ in mask if row == height - 1)),
        float(sum(1 for _, col in mask if col == 0)),
        float(sum(1 for _, col in mask if col == width - 1)),
        sum(row for row, _ in mask) / size,
        sum(col for _, col in mask) / size,
    ]

def edge_pack_side_for_train_component(
    component: dict[str, Any],
    output: Grid,
    height: int,
) -> str | None:
    row_min, col_min, row_max, col_max = component["bbox"]
    component_height = row_max - row_min + 1
    mask = {(row - row_min, col - col_min) for row, col in component["cells"]}
    sides: list[str] = []
    for side, target_row in (("top", 0), ("bottom", height - component_height)):
        if all(output[target_row + rel_row][col_min + rel_col] == component["color"] for rel_row, rel_col in mask):
            sides.append(side)
    return sides[0] if len(sides) == 1 else None
