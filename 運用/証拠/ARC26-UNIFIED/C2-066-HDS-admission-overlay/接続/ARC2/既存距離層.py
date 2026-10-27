"""既存v59の領域・境界距離層・seed周期充填演算。

出典: ARC-Layer-0-Functional-Compliance@454670a13024ccf28dc7e9ed9d8ee256ee6cd365
arc2_l0_agent_compiler_v59_seeded_separator_layer_fill.py
Git blob: fa4fd3b9bf166e9bc769ec16338b58d56f2f8c7d
純粋7関数・近傍定義2つは原文。周期は最大seed層+1という固定prior。
旧component、課題ID、reportは含めない。
"""
from __future__ import annotations
from collections import Counter,deque
from .既存凡例穴対応 import grid_shape
Grid=list[list[int]]

NEIGHBORS_4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

NEIGHBORS_8 = tuple(
    (delta_row, delta_col)
    for delta_row in (-1, 0, 1)
    for delta_col in (-1, 0, 1)
    if delta_row or delta_col
)

def dominant_color(grid: Grid) -> int:
    return Counter(value for row in grid for value in row).most_common(1)[0][0]

def component_bbox(cells: set[tuple[int, int]]) -> tuple[int, int, int, int]:
    rows = [row for row, _ in cells]
    cols = [col for _, col in cells]
    return min(rows), min(cols), max(rows), max(cols)

def detect_separator(grid: Grid) -> tuple[int | None, dict]:
    background = dominant_color(grid)
    counts = Counter(value for row in grid for value in row if value != background)
    if not counts:
        return None, {
            "background": background,
            "failure": "no non-background separator candidate",
        }

    ranked = counts.most_common()
    separator_color, separator_count = ranked[0]
    next_count = ranked[1][1] if len(ranked) > 1 else 0
    height, width = grid_shape(grid)
    min_count = max(4, min(height, width))
    ratio_ok = separator_count >= max(min_count, next_count * 3)
    record = {
        "background": background,
        "separator_color": separator_color,
        "separator_count": separator_count,
        "next_non_background_count": next_count,
        "min_required_count": min_count,
        "ratio_ok": ratio_ok,
        "non_background_counts": {
            str(color): count for color, count in sorted(counts.items())
        },
    }
    if not ratio_ok:
        record["failure"] = "separator color is not dominant enough"
        return None, record
    return separator_color, record

def separator_cells(grid: Grid, separator_color: int) -> set[tuple[int, int]]:
    return {
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == separator_color
    }

def open_components(
    grid: Grid, blocked: set[tuple[int, int]]
) -> list[set[tuple[int, int]]]:
    height, width = grid_shape(grid)
    seen = set(blocked)
    components = []
    for row in range(height):
        for col in range(width):
            if (row, col) in seen:
                continue
            stack = [(row, col)]
            seen.add((row, col))
            cells: set[tuple[int, int]] = set()
            while stack:
                current_row, current_col = stack.pop()
                cells.add((current_row, current_col))
                for delta_row, delta_col in NEIGHBORS_4:
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if (next_row, next_col) in seen:
                        continue
                    seen.add((next_row, next_col))
                    stack.append((next_row, next_col))
            components.append(cells)
    return components

def boundary_layers_8(
    cells: set[tuple[int, int]], height: int, width: int
) -> dict[tuple[int, int], int]:
    queue: deque[tuple[int, int]] = deque()
    distances: dict[tuple[int, int], int] = {}
    for row, col in cells:
        is_boundary = (
            row == 0
            or col == 0
            or row == height - 1
            or col == width - 1
            or any(
                (row + delta_row, col + delta_col) not in cells
                for delta_row, delta_col in NEIGHBORS_8
            )
        )
        if is_boundary:
            distances[(row, col)] = 0
            queue.append((row, col))

    while queue:
        row, col = queue.popleft()
        for delta_row, delta_col in NEIGHBORS_8:
            next_cell = (row + delta_row, col + delta_col)
            if next_cell not in cells or next_cell in distances:
                continue
            distances[next_cell] = distances[(row, col)] + 1
            queue.append(next_cell)
    return distances

def seeded_separator_layer_fill(grid: Grid) -> tuple[Grid | None, dict | None]:
    height, width = grid_shape(grid)
    background = dominant_color(grid)
    separator_color, separator_record = detect_separator(grid)
    if separator_color is None:
        return None, separator_record

    blocked = separator_cells(grid, separator_color)
    output = [row[:] for row in grid]
    rewrite_records = []
    conflict_records = []

    for cells in open_components(grid, blocked):
        layers = boundary_layers_8(cells, height, width)
        seed_cells = [
            cell
            for cell in sorted(cells)
            if grid[cell[0]][cell[1]] not in {background, separator_color}
        ]
        if not seed_cells:
            continue

        layer_colors: dict[int, int] = {}
        conflicts = []
        for row, col in seed_cells:
            layer = layers[(row, col)]
            color = grid[row][col]
            if layer in layer_colors and layer_colors[layer] != color:
                conflicts.append(
                    {
                        "cell": [row, col],
                        "layer": layer,
                        "existing_color": layer_colors[layer],
                        "new_color": color,
                    }
                )
            layer_colors[layer] = color

        bbox = component_bbox(cells)
        if conflicts:
            conflict_records.append(
                {
                    "component_bbox": list(bbox),
                    "seed_cells": [list(cell) for cell in seed_cells],
                    "conflicts": conflicts,
                }
            )
            continue

        max_seed_layer = max(layer_colors)
        sequence = [
            layer_colors.get(layer, background) for layer in range(max_seed_layer + 1)
        ]
        if not sequence:
            continue

        changed = 0
        for row, col in cells:
            value = sequence[layers[(row, col)] % len(sequence)]
            if output[row][col] != value:
                changed += 1
            output[row][col] = value

        rewrite_records.append(
            {
                "component_bbox": list(bbox),
                "component_size": len(cells),
                "seed_cells": [list(cell) for cell in seed_cells],
                "layer_colors": {
                    str(layer): color for layer, color in sorted(layer_colors.items())
                },
                "sequence": sequence,
                "max_layer": max(layers.values()),
                "changed": changed,
            }
        )

    if conflict_records or not rewrite_records or output == grid:
        return None, {
            **separator_record,
            "rewrite_records": rewrite_records,
            "conflict_records": conflict_records,
            "failure": "seed conflicts, no rewrites, or no-op output",
        }

    return output, {
        **separator_record,
        "rewrite_records": rewrite_records,
        "blocked_cell_count": len(blocked),
        "open_component_count": len(open_components(grid, blocked)),
    }
