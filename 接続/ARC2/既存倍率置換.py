from __future__ import annotations
from collections import Counter, defaultdict, deque
from typing import Any
from .既存凡例穴対応 import grid_shape, clone_grid
from .既存凡例経路 import dominant_background
Grid=list[list[int]]
Pattern=tuple[tuple[int | None, ...], ...]
Cell=tuple[int,int]


def extract_motif_components(grid: Grid) -> list[dict[str, Any]]:
    background = dominant_background(grid)
    height, width = grid_shape(grid)
    seen: set[Cell] = set()
    components: list[dict[str, Any]] = []
    neighbors = [
        (row_delta, col_delta)
        for row_delta in (-1, 0, 1)
        for col_delta in (-1, 0, 1)
        if (row_delta, col_delta) != (0, 0)
    ]
    for row in range(height):
        for col in range(width):
            if grid[row][col] == background or (row, col) in seen:
                continue
            queue: deque[Cell] = deque([(row, col)])
            seen.add((row, col))
            cells: list[tuple[int, int, int]] = []
            while queue:
                current_row, current_col = queue.popleft()
                cells.append((current_row, current_col, grid[current_row][current_col]))
                for row_delta, col_delta in neighbors:
                    next_row = current_row + row_delta
                    next_col = current_col + col_delta
                    next_cell = (next_row, next_col)
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if next_cell in seen or grid[next_row][next_col] == background:
                        continue
                    seen.add(next_cell)
                    queue.append(next_cell)
            rows = [cell[0] for cell in cells]
            cols = [cell[1] for cell in cells]
            components.append(
                {
                    "bbox": (min(rows), min(cols), max(rows), max(cols)),
                    "cells": sorted(cells),
                    "size": len(cells),
                    "histogram": dict(Counter(value for _, _, value in cells)),
                }
            )
    return sorted(components, key=lambda component: component["bbox"])

def pattern_from_component(component: dict[str, Any]) -> Pattern:
    row0, col0, row1, col1 = component["bbox"]
    cells = {(row - row0, col - col0): value for row, col, value in component["cells"]}
    return tuple(
        tuple(cells.get((row, col), None) for col in range(col1 - col0 + 1))
        for row in range(row1 - row0 + 1)
    )

def compress_pattern(pattern: Pattern) -> tuple[int, Pattern]:
    height = len(pattern)
    width = len(pattern[0])
    best: tuple[int, Pattern] | None = None
    for scale in range(1, min(height, width) + 1):
        if height % scale != 0 or width % scale != 0:
            continue
        compressed_rows: list[tuple[int | None, ...]] = []
        valid = True
        for block_row in range(0, height, scale):
            compressed_row: list[int | None] = []
            for block_col in range(0, width, scale):
                value = pattern[block_row][block_col]
                for row in range(block_row, block_row + scale):
                    for col in range(block_col, block_col + scale):
                        if pattern[row][col] != value:
                            valid = False
                            break
                    if not valid:
                        break
                if not valid:
                    break
                compressed_row.append(value)
            if not valid:
                break
            compressed_rows.append(tuple(compressed_row))
        if valid:
            best = (scale, tuple(compressed_rows))
    return best if best is not None else (1, pattern)

def pattern_colors(pattern: Pattern) -> set[int]:
    return {value for row in pattern for value in row if value is not None}

def pattern_color_count(pattern: Pattern, color: int) -> int:
    return sum(1 for row in pattern for value in row if value == color)

def choose_anchor_color(first: Pattern, second: Pattern) -> int | None:
    common_colors = pattern_colors(first) & pattern_colors(second)
    if not common_colors:
        return None
    return min(
        common_colors,
        key=lambda color: (
            pattern_color_count(first, color) + pattern_color_count(second, color),
            color,
        ),
    )

def anchor_offset(pattern: Pattern, color: int, scale: int) -> Cell | None:
    cells = [
        (row, col)
        for row, values in enumerate(pattern)
        for col, value in enumerate(values)
        if value == color
    ]
    if not cells:
        return None
    anchor_row = min(row for row, _ in cells)
    anchor_col = min(col for row, col in cells if row == anchor_row)
    return anchor_row * scale, anchor_col * scale

def scaled_pattern_cells(
    pattern: Pattern,
    scale: int,
    top: int,
    left: int,
) -> list[tuple[int, int, int]]:
    cells: list[tuple[int, int, int]] = []
    for row, values in enumerate(pattern):
        for col, value in enumerate(values):
            if value is None:
                continue
            for row_delta in range(scale):
                for col_delta in range(scale):
                    cells.append(
                        (
                            top + row * scale + row_delta,
                            left + col * scale + col_delta,
                            value,
                        )
                    )
    return cells

def component_summary(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "bbox": list(component["bbox"]),
        "size": component["size"],
        "histogram": component["histogram"],
    }

def render_motif_pair_scaled_anchor_swap(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    background = dominant_background(grid)
    components = extract_motif_components(grid)
    if len(components) < 2:
        return None, {"failure": "too_few_motif_components"}

    records: list[dict[str, Any]] = []
    groups: dict[Pattern, list[int]] = defaultdict(list)
    for index, component in enumerate(components):
        scale, primitive = compress_pattern(pattern_from_component(component))
        records.append(
            {
                "index": index,
                "component": component,
                "scale": scale,
                "primitive": primitive,
            }
        )
        groups[primitive].append(index)

    if len(groups) != 2:
        return None, {
            "failure": "primitive_group_count_not_two",
            "primitive_group_count": len(groups),
            "component_count": len(components),
        }

    primitive_a, primitive_b = sorted(
        groups,
        key=lambda pattern: (len(pattern), len(pattern[0]), repr(pattern)),
    )
    anchor_color = choose_anchor_color(primitive_a, primitive_b)
    if anchor_color is None:
        return None, {"failure": "no_common_anchor_color"}

    output = clone_grid(grid)
    for record in records:
        for row, col, _ in record["component"]["cells"]:
            output[row][col] = background

    placement_records: list[dict[str, Any]] = []
    for record in records:
        source = record["primitive"]
        target = primitive_b if source == primitive_a else primitive_a
        scale = record["scale"]
        source_anchor = anchor_offset(source, anchor_color, scale)
        target_anchor = anchor_offset(target, anchor_color, scale)
        if source_anchor is None or target_anchor is None:
            return None, {"failure": "missing_anchor_offset", "anchor_color": anchor_color}
        row0, col0, _, _ = record["component"]["bbox"]
        global_anchor = (row0 + source_anchor[0], col0 + source_anchor[1])
        target_top = global_anchor[0] - target_anchor[0]
        target_left = global_anchor[1] - target_anchor[1]
        rendered_cells = scaled_pattern_cells(target, scale, target_top, target_left)
        for row, col, value in rendered_cells:
            if not (0 <= row < height and 0 <= col < width):
                return None, {
                    "failure": "placement_out_of_bounds",
                    "component": component_summary(record["component"]),
                    "top_left": [target_top, target_left],
                }
            if output[row][col] not in {background, value}:
                return None, {
                    "failure": "placement_collision",
                    "cell": [row, col],
                    "existing": output[row][col],
                    "incoming": value,
                }
            output[row][col] = value
        placement_records.append(
            {
                "source_component": component_summary(record["component"]),
                "scale": scale,
                "target_top_left": [target_top, target_left],
                "anchor_global_cell": list(global_anchor),
            }
        )

    if output == grid:
        return None, {"failure": "identity_render"}
    return output, {
        "background": background,
        "anchor_color": anchor_color,
        "primitive_group_count": len(groups),
        "component_count": len(components),
        "primitive_group_sizes": [len(groups[primitive_a]), len(groups[primitive_b])],
        "placements": placement_records,
    }
