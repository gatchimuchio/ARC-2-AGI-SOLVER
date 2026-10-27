# 出典: gatchimuchio/ARC-Layer-0-Functional-Compliance
# commit 454670a13024ccf28dc7e9ed9d8ee256ee6cd365
# arc_agi_2_solver/arc2_runtime_program_search.py の純粋関数本体を無改変で再利用。
from __future__ import annotations
from typing import Any
from .既存穴充填 import _grid_shape, _dominant_color
Grid = list[list[int]]

def _orthogonal_component_count(cells: set[tuple[int, int]]) -> int:
    remaining = set(cells)
    component_count = 0
    while remaining:
        component_count += 1
        stack = [remaining.pop()]
        while stack:
            row, col = stack.pop()
            for neighbor in (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            ):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    stack.append(neighbor)
    return component_count

def _nested_panel_relation_record(
    grid: Grid,
    row: int,
    col: int,
    size: int,
    marker_color: int,
    background: int,
) -> dict[str, Any] | None:
    height, width = _grid_shape(grid)
    if size < 3 or row + size > height or col + size > width:
        return None
    base = int(grid[row][col])
    if base == background:
        return None
    if any(
        grid[row][current_col] != base
        or grid[row + size - 1][current_col] != base
        for current_col in range(col, col + size)
    ):
        return None
    if any(
        grid[current_row][col] != base
        or grid[current_row][col + size - 1] != base
        for current_row in range(row, row + size)
    ):
        return None
    non_base_cells = {
        (current_row, current_col)
        for current_row in range(row + 1, row + size - 1)
        for current_col in range(col + 1, col + size - 1)
        if grid[current_row][current_col] != base
    }
    if non_base_cells and {
        int(grid[current_row][current_col])
        for current_row, current_col in non_base_cells
    } != {marker_color}:
        return None
    marker_cells = {
        (current_row, current_col)
        for current_row, current_col in non_base_cells
        if int(grid[current_row][current_col]) == marker_color
    }
    return {
        "row": row,
        "col": col,
        "size": size,
        "base": base,
        "marker_component_count": _orthogonal_component_count(marker_cells),
        "marker_cell_count": len(marker_cells),
        "cells": {
            (current_row, current_col)
            for current_row in range(row, row + size)
            for current_col in range(col, col + size)
        },
    }

def _nested_panel_layout(
    positions: dict[tuple[int, int], dict[str, Any]],
    size: int,
    row: int,
    col: int,
    row_count: int,
    col_count: int,
) -> list[dict[str, Any]] | None:
    panels = [
        positions.get((row + row_index * size, col + col_index * size))
        for row_index in range(row_count)
        for col_index in range(col_count)
    ]
    if any(panel is None for panel in panels):
        return None
    selected = [panel for panel in panels if panel is not None]
    if len({int(panel["base"]) for panel in selected}) != len(selected):
        return None
    return selected

def _nested_panel_layout_is_maximal(
    positions: dict[tuple[int, int], dict[str, Any]],
    size: int,
    grid_shape: tuple[int, int],
    row: int,
    col: int,
    row_count: int,
    col_count: int,
) -> bool:
    height, width = grid_shape
    extensions = (
        (row, col - size, row_count, col_count + 1),
        (row, col, row_count, col_count + 1),
        (row - size, col, row_count + 1, col_count),
        (row, col, row_count + 1, col_count),
    )
    for extended_row, extended_col, extended_rows, extended_cols in extensions:
        if (
            extended_row < 0
            or extended_col < 0
            or extended_row + extended_rows * size > height
            or extended_col + extended_cols * size > width
        ):
            continue
        if _nested_panel_layout(
            positions,
            size,
            extended_row,
            extended_col,
            extended_rows,
            extended_cols,
        ) is not None:
            return False
    return True

def _nested_panel_relation_candidate_details(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "target_size": int(candidate["target_size"]),
        "marker_color": int(candidate["marker_color"]),
        "layout_origin": [
            int(candidate["layout_origin"][0]),
            int(candidate["layout_origin"][1]),
        ],
        "layout_shape": [
            int(candidate["layout_shape"][0]),
            int(candidate["layout_shape"][1]),
        ],
        "target_origins": [
            [int(panel["row"]), int(panel["col"])]
            for panel in candidate["targets"]
        ],
        "source_origins": [
            [int(panel["row"]), int(panel["col"])]
            for panel in candidate["sources"]
        ],
        "target_marker_component_counts": [
            int(panel["marker_component_count"])
            for panel in candidate["targets"]
        ],
        "source_marker_component_counts": [
            int(panel["marker_component_count"])
            for panel in candidate["sources"]
        ],
    }

def _nested_panel_relation_candidates(
    grid: Grid,
    expected: Grid | None = None,
) -> list[dict[str, Any]]:
    height, width = _grid_shape(grid)
    if not grid or not width or any(len(row) != width for row in grid):
        return []
    background = _dominant_color(grid)
    if background is None:
        return []
    colors = sorted({int(value) for row in grid for value in row})
    if expected is None:
        size_candidates = range(3, min(height, width) + 1)
    else:
        output_height, output_width = _grid_shape(expected)
        size_candidates = [
            size
            for size in range(3, min(height, width) + 1)
            if output_height % size == 0 and output_width % size == 0
        ]
    candidates: list[dict[str, Any]] = []
    for target_size in size_candidates:
        source_size = target_size - 2
        if source_size < 1:
            continue
        for marker_color in colors:
            target_panels = [
                panel
                for row in range(height - target_size + 1)
                for col in range(width - target_size + 1)
                if (
                    panel := _nested_panel_relation_record(
                        grid,
                        row,
                        col,
                        target_size,
                        marker_color,
                        int(background),
                    )
                )
            ]
            source_panels = [
                panel
                for row in range(height - source_size + 1)
                for col in range(width - source_size + 1)
                if (
                    panel := _nested_panel_relation_record(
                        grid,
                        row,
                        col,
                        source_size,
                        marker_color,
                        int(background),
                    )
                )
            ]
            positions = {
                (int(panel["row"]), int(panel["col"])): panel
                for panel in target_panels
            }
            if len(positions) < 2:
                continue
            if expected is None:
                row_count_candidates = range(1, height // target_size + 1)
                col_count_candidates = range(1, width // target_size + 1)
            else:
                output_height, output_width = _grid_shape(expected)
                row_count_candidates = [output_height // target_size]
                col_count_candidates = [output_width // target_size]
            for row in sorted({position[0] for position in positions}):
                for col in sorted({position[1] for position in positions}):
                    for row_count in row_count_candidates:
                        for col_count in col_count_candidates:
                            if row_count * col_count < 2:
                                continue
                            targets = _nested_panel_layout(
                                positions,
                                target_size,
                                row,
                                col,
                                row_count,
                                col_count,
                            )
                            if targets is None or not _nested_panel_layout_is_maximal(
                                positions,
                                target_size,
                                (height, width),
                                row,
                                col,
                                row_count,
                                col_count,
                            ):
                                continue
                            if expected is not None:
                                output_height, output_width = _grid_shape(expected)
                                if (
                                    output_height != row_count * target_size
                                    or output_width != col_count * target_size
                                    or any(
                                        expected[row_index * target_size][
                                            col_index * target_size
                                        ]
                                        != targets[row_index * col_count + col_index]["base"]
                                        for row_index in range(row_count)
                                        for col_index in range(col_count)
                                    )
                                ):
                                    continue
                            target_counts = [
                                int(panel["marker_component_count"])
                                for panel in targets
                            ]
                            if len(set(target_counts)) != len(target_counts):
                                continue
                            target_cells = set().union(
                                *(panel["cells"] for panel in targets)
                            )
                            available_sources = [
                                panel
                                for panel in source_panels
                                if not panel["cells"] & target_cells
                            ]
                            sources_by_count: dict[
                                int, list[dict[str, Any]]
                            ] = {}
                            for panel in available_sources:
                                sources_by_count.setdefault(
                                    int(panel["marker_component_count"]),
                                    [],
                                ).append(panel)
                            if any(
                                len(sources_by_count.get(count, [])) != 1
                                for count in target_counts
                            ):
                                continue
                            sources = [
                                sources_by_count[count][0]
                                for count in target_counts
                            ]
                            if len({int(panel["base"]) for panel in sources}) != len(
                                sources
                            ):
                                continue
                            if any(
                                left["cells"] & right["cells"]
                                for index, left in enumerate(sources)
                                for right in sources[:index]
                            ):
                                continue
                            output: Grid = []
                            for row_index in range(row_count):
                                blocks: list[Grid] = []
                                for col_index in range(col_count):
                                    target = targets[row_index * col_count + col_index]
                                    source = sources[row_index * col_count + col_index]
                                    block = [
                                        [int(target["base"])] * target_size
                                        for _ in range(target_size)
                                    ]
                                    for source_row in range(source_size):
                                        for source_col in range(source_size):
                                            value = grid[
                                                int(source["row"]) + source_row
                                            ][int(source["col"]) + source_col]
                                            block[source_row + 1][source_col + 1] = (
                                                int(source["base"])
                                                if value == source["base"]
                                                else int(target["base"])
                                            )
                                    blocks.append(block)
                                for output_row in range(target_size):
                                    output.append(
                                        sum(
                                            (
                                                block[output_row]
                                                for block in blocks
                                            ),
                                            [],
                                        )
                                    )
                            if expected is not None and output != expected:
                                continue
                            candidates.append(
                                {
                                    "output": output,
                                    "target_size": target_size,
                                    "marker_color": marker_color,
                                    "layout_origin": (row, col),
                                    "layout_shape": (row_count, col_count),
                                    "targets": targets,
                                    "sources": sources,
                                }
                            )
    return candidates

def _nested_panel_relation_render(
    grid: Grid,
    _policy: dict[str, Any],
) -> tuple[Grid | None, dict[str, Any]]:
    candidates = _nested_panel_relation_candidates(grid)
    if len(candidates) != 1:
        return None, {
            "failure": "nested_panel_relation_candidate_count",
            "candidate_count": len(candidates),
            "candidate_details": [
                _nested_panel_relation_candidate_details(candidate)
                for candidate in candidates[:8]
            ],
        }
    candidate = candidates[0]
    return candidate["output"], {
        "event_count": len(candidate["targets"]),
        "renderer_case": "nested_panel_relation_composition",
        **_nested_panel_relation_candidate_details(candidate),
    }
