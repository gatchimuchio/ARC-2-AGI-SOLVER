from __future__ import annotations
from collections import deque
from typing import Any
from .既存凡例経路 import dominant_background
from .既存凡例穴対応 import grid_shape, bbox_to_list
from .既存枠計数 import component_summary
Grid=list[list[int]]
Cell=tuple[int,int]
BBox=tuple[int,int,int,int]

def color_components(grid: Grid, color: int, include_diagonal: bool = False) -> list[dict[str, Any]]:
    height, width = grid_shape(grid)
    neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    if include_diagonal:
        neighbors.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])

    seen: set[Cell] = set()
    results: list[dict[str, Any]] = []
    for row in range(height):
        for col in range(width):
            if grid[row][col] != color or (row, col) in seen:
                continue
            queue: deque[Cell] = deque([(row, col)])
            seen.add((row, col))
            cells: set[Cell] = set()
            while queue:
                current_row, current_col = queue.popleft()
                cells.add((current_row, current_col))
                for row_delta, col_delta in neighbors:
                    next_row = current_row + row_delta
                    next_col = current_col + col_delta
                    next_cell = (next_row, next_col)
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if next_cell in seen or grid[next_row][next_col] != color:
                        continue
                    seen.add(next_cell)
                    queue.append(next_cell)
            rows = [cell[0] for cell in cells]
            cols = [cell[1] for cell in cells]
            results.append(
                {
                    "color": color,
                    "cells": cells,
                    "bbox": (min(rows), min(cols), max(rows), max(cols)),
                    "size": len(cells),
                }
            )
    return sorted(results, key=lambda component: (component["bbox"], component["size"]))

def panel_bbox_cells(bbox: BBox) -> set[Cell]:
    row0, col0, row1, col1 = bbox
    return {
        (row, col)
        for row in range(row0, row1 + 1)
        for col in range(col0, col1 + 1)
    }

def extract_marker_panel(grid: Grid) -> tuple[dict[str, Any], list[dict[str, int]]] | tuple[None, dict[str, Any]]:
    background = dominant_background(grid)
    if background == 0:
        return None, {
            "failure": "zero_is_background",
            "background": background,
        }

    panel_candidates: list[tuple[int, dict[str, Any], list[dict[str, int]]]] = []
    for zero_component in color_components(grid, 0, include_diagonal=False):
        row0, col0, row1, col1 = zero_component["bbox"]
        panel_height = row1 - row0 + 1
        panel_width = col1 - col0 + 1
        panel_area = panel_height * panel_width
        if panel_height < 3 or panel_width < 3:
            continue
        if zero_component["size"] < panel_area * 0.5:
            continue

        markers: list[dict[str, int]] = []
        invalid = False
        for row in range(row0, row1 + 1):
            for col in range(col0, col1 + 1):
                value = grid[row][col]
                if value == 0:
                    continue
                if value == background:
                    invalid = True
                    break
                markers.append(
                    {
                        "row": row - row0,
                        "col": col - col0,
                        "color": value,
                    }
                )
            if invalid:
                break
        if invalid or not markers:
            continue
        marker_cols = {marker["col"] for marker in markers}
        marker_colors = [marker["color"] for marker in markers]
        marker_rows = sorted(marker["row"] for marker in markers)
        if len(marker_cols) != 1:
            continue
        if len(set(marker_colors)) != len(marker_colors):
            continue
        if any(row % 2 == 0 for row in marker_rows):
            continue
        if marker_rows != list(range(marker_rows[0], marker_rows[-1] + 1, 2)):
            continue
        panel_candidates.append(
            (
                panel_area,
                {
                    "color": 0,
                    "cells": zero_component["cells"],
                    "bbox": zero_component["bbox"],
                    "size": zero_component["size"],
                    "height": panel_height,
                    "width": panel_width,
                },
                sorted(markers, key=lambda marker: (marker["row"], marker["col"], marker["color"])),
            )
        )

    if len(panel_candidates) != 1:
        return None, {
            "failure": "ambiguous_marker_panel",
            "candidate_count": len(panel_candidates),
            "candidate_bboxes": [bbox_to_list(candidate[1]["bbox"]) for candidate in panel_candidates],
        }
    _, panel, markers = panel_candidates[0]
    return panel, markers

def render_marker_panel_inventory_count_lattice(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    panel, panel_or_failure = extract_marker_panel(grid)
    if panel is None:
        return None, panel_or_failure
    markers = panel_or_failure
    panel_bbox = panel["bbox"]
    panel_cells = panel_bbox_cells(panel_bbox)
    marker_col = markers[0]["col"]
    output = [[0 for _ in range(panel["width"])] for _ in range(panel["height"])]

    records: list[dict[str, Any]] = []
    for marker in markers:
        color = marker["color"]
        external_components = [
            component
            for component in color_components(grid, color, include_diagonal=True)
            if component["cells"].isdisjoint(panel_cells)
        ]
        count = len(external_components)
        last_col = marker_col + 2 * (count - 1)
        if count < 1:
            return None, {
                "failure": "missing_external_component_for_marker",
                "marker": marker,
            }
        if last_col >= panel["width"]:
            return None, {
                "failure": "marker_count_overflows_panel_width",
                "marker": marker,
                "external_count": count,
                "panel_width": panel["width"],
                "marker_col": marker_col,
            }
        for index in range(count):
            output[marker["row"]][marker_col + 2 * index] = color
        records.append(
            {
                "marker": marker,
                "external_count": count,
                "external_components": [
                    component_summary(component) for component in external_components
                ],
                "emitted_cols": [marker_col + 2 * index for index in range(count)],
            }
        )

    return output, {
        "background": dominant_background(grid),
        "panel": {
            "bbox": bbox_to_list(panel_bbox),
            "height": panel["height"],
            "width": panel["width"],
            "zero_cell_count": panel["size"],
        },
        "markers": markers,
        "records": records,
    }
