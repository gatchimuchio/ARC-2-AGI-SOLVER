"""旧ARCのdomino標識と放射方向D4組立prior。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_program_search。
7関数は原文のまま。最小対向境界を優先する固定規則を保持する。
"""
from __future__ import annotations
from typing import Any
from .既存領域転写 import Grid
from .既存穴充填 import _grid_shape, _dominant_color
from .既存物体特徴 import color_component_dicts_for_grid

def _marker_radial_component_sets(
    grid: Grid,
    background: int,
) -> dict[int, list[set[tuple[int, int]]]]:
    components_by_color: dict[int, list[set[tuple[int, int]]]] = {}
    colors = sorted(
        {
            int(value)
            for row in grid
            for value in row
            if int(value) != int(background)
        }
    )
    for color in colors:
        components_by_color[color] = [
            {
                (int(row), int(col))
                for row, col in component["cells"]
            }
            for component in color_component_dicts_for_grid(grid, color, True)
        ]
        components_by_color[color].sort(
            key=lambda cells: (
                -len(cells),
                min(cells),
            )
        )
    return components_by_color

def _marker_radial_shape_variants(
    cells: set[tuple[int, int]],
) -> list[set[tuple[int, int]]]:
    row0 = min(row for row, _col in cells)
    col0 = min(col for _row, col in cells)
    normalized = {(row - row0, col - col0) for row, col in cells}
    variants: list[set[tuple[int, int]]] = []
    for transform_index in range(8):
        transformed: set[tuple[int, int]] = set()
        for row, col in normalized:
            if transform_index == 0:
                next_row, next_col = row, col
            elif transform_index == 1:
                next_row, next_col = col, -row
            elif transform_index == 2:
                next_row, next_col = -row, -col
            elif transform_index == 3:
                next_row, next_col = -col, row
            elif transform_index == 4:
                next_row, next_col = row, -col
            elif transform_index == 5:
                next_row, next_col = -row, col
            elif transform_index == 6:
                next_row, next_col = col, row
            else:
                next_row, next_col = -col, -row
            transformed.add((next_row, next_col))
        next_row0 = min(row for row, _col in transformed)
        next_col0 = min(col for _row, col in transformed)
        translated = {
            (row - next_row0, col - next_col0)
            for row, col in transformed
        }
        if translated not in variants:
            variants.append(translated)
    return variants

def _marker_radial_direction(
    marker: set[tuple[int, int]],
    all_markers: set[tuple[int, int]],
) -> str | None:
    marker_count = len(marker)
    total_count = len(all_markers)
    marker_row_sum = sum(row for row, _col in marker)
    marker_col_sum = sum(col for _row, col in marker)
    all_row_sum = sum(row for row, _col in all_markers)
    all_col_sum = sum(col for _row, col in all_markers)
    row_delta = marker_row_sum * total_count - all_row_sum * marker_count
    col_delta = marker_col_sum * total_count - all_col_sum * marker_count
    if row_delta == 0 and col_delta == 0:
        return None
    if abs(row_delta) == abs(col_delta) and row_delta != 0 and col_delta != 0:
        return None
    if abs(row_delta) > abs(col_delta):
        return "down" if row_delta > 0 else "up"
    return "right" if col_delta > 0 else "left"

def _marker_radial_attachment_options(
    grid: Grid,
    large: set[tuple[int, int]],
    marker: set[tuple[int, int]],
    other_markers: set[tuple[int, int]],
    direction: str,
) -> list[dict[str, Any]]:
    height, width = _grid_shape(grid)
    marker_rows = [row for row, _col in marker]
    marker_cols = [col for _row, col in marker]
    options: list[dict[str, Any]] = []
    seen: set[frozenset[tuple[int, int]]] = set()
    for transform_index, variant in enumerate(_marker_radial_shape_variants(large)):
        max_row = max(row for row, _col in variant)
        max_col = max(col for _row, col in variant)
        for row0 in range(height - max_row):
            for col0 in range(width - max_col):
                placed = {
                    (row0 + row, col0 + col)
                    for row, col in variant
                }
                if placed & marker:
                    continue
                if placed & other_markers:
                    continue
                if direction == "left" and not all(
                    col < min(marker_cols) for _row, col in placed
                ):
                    continue
                if direction == "right" and not all(
                    col > max(marker_cols) for _row, col in placed
                ):
                    continue
                if direction == "up" and not all(
                    row < min(marker_rows) for row, _col in placed
                ):
                    continue
                if direction == "down" and not all(
                    row > max(marker_rows) for row, _col in placed
                ):
                    continue
                if direction in {"left", "right"}:
                    if sum(row for row, _col in placed) * len(marker) != (
                        sum(row for row, _col in marker) * len(placed)
                    ):
                        continue
                else:
                    if sum(col for _row, col in placed) * len(marker) != (
                        sum(col for _row, col in marker) * len(placed)
                    ):
                        continue
                contact_marker_cells = {
                    marker_cell
                    for marker_cell in marker
                    if any(
                        (marker_cell[0] + row_delta, marker_cell[1] + col_delta)
                        in placed
                        for row_delta, col_delta in (
                            (-1, 0),
                            (1, 0),
                            (0, -1),
                            (0, 1),
                        )
                    )
                }
                if contact_marker_cells != marker:
                    continue
                placed_marker = frozenset(placed | marker)
                if placed_marker in seen:
                    continue
                seen.add(placed_marker)
                options.append(
                    {
                        "cells": placed_marker,
                        "large_cells": frozenset(placed),
                        "transform_index": transform_index,
                        "direction": direction,
                    }
                )
    return options

def _marker_radial_marker_facing_boundary_count(
    option: dict[str, Any],
    direction: str,
) -> int:
    large_cells = set(option["large_cells"])
    rows = [row for row, _col in large_cells]
    cols = [col for _row, col in large_cells]
    if direction == "right":
        boundary = min(cols)
        return sum(col == boundary for _row, col in large_cells)
    if direction == "left":
        boundary = max(cols)
        return sum(col == boundary for _row, col in large_cells)
    if direction == "up":
        boundary = max(rows)
        return sum(row == boundary for row, _col in large_cells)
    boundary = min(rows)
    return sum(row == boundary for row, _col in large_cells)

def _marker_radial_assembly_parse(
    grid: Grid,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not grid or not grid[0] or any(len(row) != len(grid[0]) for row in grid):
        return None, {"failure": "marker_radial_requires_rectangular_grid"}
    background = _dominant_color(grid)
    if background is None:
        return None, {"failure": "marker_radial_missing_background"}
    components_by_color = _marker_radial_component_sets(grid, background)
    marker_records: list[dict[str, Any]] = []
    active_records: list[dict[str, Any]] = []
    for color, components in sorted(components_by_color.items()):
        markers = [component for component in components if len(component) == 2]
        if len(markers) > 1:
            return None, {
                "failure": "marker_radial_multiple_marker_components",
                "color": color,
                "component_sizes": [len(component) for component in components],
            }
        if not markers:
            if len(components) == 1 and len(components[0]) > 2:
                continue
            return None, {
                "failure": "marker_radial_unclassified_component_inventory",
                "color": color,
                "component_sizes": [len(component) for component in components],
            }
        marker = markers[0]
        marker_rows = sorted(row for row, _col in marker)
        marker_cols = sorted(col for _row, col in marker)
        if abs(marker_rows[0] - marker_rows[1]) + abs(marker_cols[0] - marker_cols[1]) != 1:
            return None, {
                "failure": "marker_radial_marker_not_orthogonal_domino",
                "color": color,
                "marker_cells": sorted([list(cell) for cell in marker]),
            }
        marker_record = {"color": int(color), "cells": marker}
        marker_records.append(marker_record)
        large_components = [component for component in components if component is not marker]
        if len(large_components) > 1:
            return None, {
                "failure": "marker_radial_multiple_large_components",
                "color": color,
                "component_sizes": [len(component) for component in components],
            }
        if large_components:
            active_records.append(
                {
                    "color": int(color),
                    "marker": marker,
                    "large": large_components[0],
                }
            )
    if len(marker_records) < 2 or not active_records:
        return None, {
            "failure": "marker_radial_requires_marker_inventory_and_active_shapes",
            "marker_count": len(marker_records),
            "active_shape_count": len(active_records),
        }
    all_markers = set().union(*(record["cells"] for record in marker_records))
    for record in active_records:
        direction = _marker_radial_direction(record["marker"], all_markers)
        if direction is None:
            return None, {
                "failure": "marker_radial_marker_direction_ambiguous",
                "color": record["color"],
            }
        record["direction"] = direction
    return {
        "background": int(background),
        "marker_records": marker_records,
        "active_records": active_records,
        "all_markers": all_markers,
    }, {}

def _marker_radial_assembly_render(
    grid: Grid,
    _policy: dict[str, Any],
) -> tuple[Grid | None, dict[str, Any]]:
    parsed, rejection = _marker_radial_assembly_parse(grid)
    if parsed is None:
        return None, rejection
    active_options: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    all_markers = set(parsed["all_markers"])
    for record in parsed["active_records"]:
        options = _marker_radial_attachment_options(
            grid,
            record["large"],
            record["marker"],
            all_markers.difference(record["marker"]),
            str(record["direction"]),
        )
        if not options:
            return None, {
                "failure": "marker_radial_no_attachment_options",
                "color": record["color"],
                "direction": record["direction"],
            }
        minimum_facing_boundary_count = min(
            _marker_radial_marker_facing_boundary_count(
                option,
                str(record["direction"]),
            )
            for option in options
        )
        options = [
            option
            for option in options
            if _marker_radial_marker_facing_boundary_count(
                option,
                str(record["direction"]),
            )
            == minimum_facing_boundary_count
        ]
        active_options.append((record, options))
    active_options.sort(key=lambda item: (len(item[1]), int(item[0]["color"])))
    solutions: list[list[tuple[dict[str, Any], dict[str, Any]]]] = []
    node_count = 0

    def visit(
        index: int,
        selected: list[tuple[dict[str, Any], dict[str, Any]]],
        occupied: set[tuple[int, int]],
    ) -> None:
        nonlocal node_count
        if len(solutions) > 2 or node_count >= 100000:
            return
        node_count += 1
        if index == len(active_options):
            solutions.append(list(selected))
            return
        record, options = active_options[index]
        for option in options:
            cells = set(option["cells"])
            if cells & occupied:
                continue
            selected.append((record, option))
            visit(index + 1, selected, occupied | cells)
            selected.pop()

    visit(0, [], set())
    if node_count >= 100000:
        return None, {
            "failure": "marker_radial_search_budget_exhausted",
            "search_nodes": node_count,
        }
    if not solutions:
        return None, {
            "failure": "marker_radial_no_global_assembly",
            "search_nodes": node_count,
        }
    outputs: dict[tuple[tuple[int, ...], ...], Grid] = {}
    background = int(parsed["background"])
    height, width = _grid_shape(grid)
    for solution in solutions:
        output = [[background for _ in range(width)] for _ in range(height)]
        for record in parsed["marker_records"]:
            for row, col in record["cells"]:
                output[row][col] = int(record["color"])
        for record, option in solution:
            for row, col in option["cells"]:
                output[row][col] = int(record["color"])
        key = tuple(tuple(int(value) for value in row) for row in output)
        outputs.setdefault(key, output)
    if len(outputs) != 1:
        return None, {
            "failure": "marker_radial_assembly_ambiguous",
            "solution_count": len(solutions),
            "distinct_output_count": len(outputs),
            "search_nodes": node_count,
        }
    output = next(iter(outputs.values()))
    return output, {
        "renderer_case": "marker_radial_shape_assembly",
        "marker_count": len(parsed["marker_records"]),
        "active_shape_count": len(parsed["active_records"]),
        "search_nodes": node_count,
        "solution_count": len(solutions),
        "changed_cell_count": sum(
            output[row][col] != grid[row][col]
            for row in range(height)
            for col in range(width)
        ),
        "directions": sorted(
            {
                str(record["direction"])
                for record in parsed["active_records"]
            }
        ),
    }
