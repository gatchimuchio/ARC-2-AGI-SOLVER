from __future__ import annotations
from collections import Counter
from typing import Any
from .既存穴充填 import _grid_shape, _dominant_color
Grid=list[list[int]]
_BARRIER_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))

def _barrier_component_records(grid: Grid, color: int) -> list[dict[str, Any]]:
    height, width = _grid_shape(grid)
    remaining = {
        (row, col)
        for row in range(height)
        for col in range(width)
        if int(grid[row][col]) == int(color)
    }
    records: list[dict[str, Any]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        cells = {start}
        while stack:
            row, col = stack.pop()
            for row_delta, col_delta in _BARRIER_NEIGHBORS:
                cell = (row + row_delta, col + col_delta)
                if cell not in remaining:
                    continue
                remaining.remove(cell)
                cells.add(cell)
                stack.append(cell)
        row0 = min(row for row, _ in cells)
        col0 = min(col for _, col in cells)
        row1 = max(row for row, _ in cells)
        col1 = max(col for _, col in cells)
        records.append(
            {
                "color": int(color),
                "cells": cells,
                "bbox": (row0, col0, row1, col1),
                "height": row1 - row0 + 1,
                "width": col1 - col0 + 1,
                "center": (
                    sum(row for row, _ in cells) / len(cells),
                    sum(col for _, col in cells) / len(cells),
                ),
            }
        )
    return records

def _palette_cell_components(
    cells: set[tuple[int, int]],
    diagonal: bool = False,
) -> list[set[tuple[int, int]]]:
    neighbors = (
        tuple(
            (row_delta, col_delta)
            for row_delta in (-1, 0, 1)
            for col_delta in (-1, 0, 1)
            if (row_delta, col_delta) != (0, 0)
        )
        if diagonal
        else _BARRIER_NEIGHBORS
    )
    remaining = set(cells)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component = {start}
        while stack:
            row, col = stack.pop()
            for row_delta, col_delta in neighbors:
                cell = (row + row_delta, col + col_delta)
                if cell not in remaining:
                    continue
                remaining.remove(cell)
                component.add(cell)
                stack.append(cell)
        components.append(component)
    return sorted(
        components,
        key=lambda component: (
            min(row for row, _ in component),
            min(col for _, col in component),
            -len(component),
        ),
    )

def _target_square_palette_sector(
    component: set[tuple[int, int]],
    square_origin: tuple[int, int],
) -> tuple[str, Any] | None:
    row0, col0 = square_origin
    center_row = sum(row for row, _ in component) / len(component)
    center_col = sum(col for _, col in component) / len(component)
    if center_row < row0:
        if center_col < col0:
            return "top_left", lambda row, col: row < row0 and col < col0
        if center_col > col0 + 2:
            return "top_right", lambda row, col: row < row0 and col > col0 + 2
        return "top", lambda row, _col: row < row0
    if center_row > row0 + 2:
        if center_col < col0:
            return "bottom_left", lambda row, col: row > row0 + 2 and col < col0
        if center_col > col0 + 2:
            return "bottom_right", lambda row, col: row > row0 + 2 and col > col0 + 2
        return "bottom", lambda row, _col: row > row0 + 2
    if center_col < col0:
        return "left", lambda _row, col: col < col0
    if center_col > col0 + 2:
        return "right", lambda _row, col: col > col0 + 2
    return None

def _target_square_palette_render(
    grid: Grid,
) -> tuple[Grid | None, dict[str, Any]]:
    background = _dominant_color(grid)
    if background is None:
        return None, {"failure": "target_square_palette_missing_background"}
    height, width = _grid_shape(grid)
    color_components = [
        (int(color), component)
        for color in sorted(
            {
                int(value)
                for row in grid
                for value in row
                if int(value) != int(background)
            }
        )
        for component in _barrier_component_records(grid, int(color))
    ]
    if not color_components:
        return None, {"failure": "target_square_palette_missing_foreground"}
    largest_size = max(len(component["cells"]) for _, component in color_components)
    largest = [
        (color, component)
        for color, component in color_components
        if len(component["cells"]) == largest_size
    ]
    if len(largest) != 1:
        return None, {"failure": "target_square_palette_ambiguous_target_component"}
    target_color, target_component = largest[0]
    target_cells = {
        (row, col)
        for row in range(height)
        for col in range(width)
        if int(grid[row][col]) == target_color
    }
    if target_cells != set(target_component["cells"]):
        return None, {"failure": "target_square_palette_split_target_color"}
    source_cells = {
        (row, col)
        for row in range(height)
        for col in range(width)
        if int(grid[row][col]) not in (int(background), target_color)
    }
    source_colors = sorted({int(grid[row][col]) for row, col in source_cells})
    if len(source_colors) != 2 or not source_cells:
        return None, {"failure": "target_square_palette_requires_two_source_colors"}

    square_origins = []
    for row in range(height - 2):
        for col in range(width - 2):
            square = {
                (square_row, square_col)
                for square_row in range(row, row + 3)
                for square_col in range(col, col + 3)
            }
            if square <= target_cells:
                square_origins.append((row, col))
    if len(square_origins) != 1:
        return None, {
            "failure": "target_square_palette_requires_unique_3x3_anchor",
            "square_count": len(square_origins),
        }
    square_origin = square_origins[0]
    row0, col0 = square_origin
    perimeter = (
        {(row0, col) for col in range(col0, col0 + 3)}
        | {(row0 + 2, col) for col in range(col0, col0 + 3)}
        | {(row, col0) for row in range(row0, row0 + 3)}
        | {(row, col0 + 2) for row in range(row0, row0 + 3)}
    )
    source_patches = _palette_cell_components(source_cells, diagonal=True)
    output = [list(row) for row in grid]
    assignments: list[dict[str, Any]] = []
    deferred_center: list[set[tuple[int, int]]] = []
    for component in _palette_cell_components(target_cells - perimeter):
        if component == {(row0 + 1, col0 + 1)}:
            deferred_center.append(component)
            continue
        sector = _target_square_palette_sector(component, square_origin)
        if sector is None:
            return None, {"failure": "target_square_palette_unclassified_component"}
        sector_name, predicate = sector
        candidates = [
            (row, col)
            for row, col in source_cells
            if predicate(row, col)
        ]
        if not candidates:
            return None, {
                "failure": "target_square_palette_sector_without_source",
                "sector": sector_name,
            }
        counts = Counter(int(grid[row][col]) for row, col in candidates)
        selected_color = min(counts, key=lambda color: (-counts[color], color))
        for row, col in component:
            output[row][col] = int(selected_color)
        assignments.append(
            {
                "sector": sector_name,
                "component_size": len(component),
                "selected_color": int(selected_color),
                "source_counts": {
                    str(color): int(count) for color, count in sorted(counts.items())
                },
            }
        )
    if len(deferred_center) != 1:
        return None, {
            "failure": "target_square_palette_requires_single_center_cell",
            "center_component_count": len(deferred_center),
        }
    palette_counts = Counter(
        int(record["selected_color"])
        for record in assignments
        for _ in range(int(record["component_size"]))
    )
    if not palette_counts:
        return None, {"failure": "target_square_palette_missing_outer_components"}
    max_count = max(palette_counts.values())
    tied_colors = {
        color for color, count in palette_counts.items() if count == max_count
    }
    if len(tied_colors) == 1:
        center_color = next(iter(tied_colors))
    else:
        left_colors = Counter(
            int(record["selected_color"])
            for record in assignments
            if record["sector"] in {"top_left", "bottom_left", "left"}
        )
        left_tied = [color for color in tied_colors if left_colors[color]]
        center_color = min(
            left_tied or sorted(tied_colors),
            key=lambda color: (-left_colors[color], color),
        )
    for row, col in deferred_center[0]:
        output[row][col] = int(center_color)
    return output, {
        "renderer_case": "target_square_quadrant_palette_rewrite",
        "background_color": int(background),
        "target_color": int(target_color),
        "source_colors": source_colors,
        "square_origin": list(square_origin),
        "outer_component_count": len(assignments),
        "center_color": int(center_color),
        "assignments": assignments,
        "source_patch_count": len(source_patches),
    }
