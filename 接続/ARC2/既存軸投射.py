"""境界markerによる軸・半平面・角への旧幾何投射7関数。"""
from __future__ import annotations
from typing import Any
from collections import Counter
from .既存物体特徴 import dominant_background_for_grid
Grid=list[list[int]]
Cell=tuple[int,int]
BBox=tuple[int,int,int,int]

def grid_shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0

def dominant_background(grid: Grid) -> int:
    return dominant_background_for_grid(grid)

def bbox_to_list(bbox: BBox) -> list[int]:
    return [bbox[0], bbox[1], bbox[2], bbox[3]]

def cells_to_bbox(cells: list[Cell]) -> BBox:
    return (
        min(row for row, _ in cells),
        min(col for _, col in cells),
        max(row for row, _ in cells),
        max(col for _, col in cells),
    )

def infer_edge_marker_axis_roles(grid: Grid) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}

    height, width = grid_shape(grid)
    background = dominant_background(grid)
    color_counts = Counter(value for row in grid for value in row)
    non_background_colors = set(color_counts) - {background}
    if len(non_background_colors) != 2:
        return None, {
            "failure": "non_background_color_count_not_two",
            "background": background,
            "non_background_colors": sorted(non_background_colors),
        }

    marker_candidates: list[dict[str, Any]] = []
    for color in sorted(non_background_colors):
        cells = [(row, col) for row, values in enumerate(grid) for col, value in enumerate(values) if value == color]
        edge_cells = [
            (row, col)
            for row, col in cells
            if row in {0, height - 1} or col in {0, width - 1}
        ]
        if len(cells) != len(edge_cells) or not (1 <= len(cells) <= 2):
            continue
        vertical_markers = [(row, col) for row, col in cells if row in {0, height - 1}]
        horizontal_markers = [(row, col) for row, col in cells if col in {0, width - 1}]
        if len(vertical_markers) > 1 or len(horizontal_markers) > 1:
            continue
        if len(vertical_markers) + len(horizontal_markers) != len(cells):
            continue
        marker_candidates.append(
            {
                "marker_color": color,
                "vertical_markers": vertical_markers,
                "horizontal_markers": horizontal_markers,
            }
        )

    if len(marker_candidates) != 1:
        return None, {
            "failure": "edge_marker_color_not_unique",
            "background": background,
            "non_background_colors": sorted(non_background_colors),
            "marker_candidate_count": len(marker_candidates),
        }

    marker_candidate = marker_candidates[0]
    marker_color = int(marker_candidate["marker_color"])
    object_colors = non_background_colors - {marker_color}
    if len(object_colors) != 1:
        return None, {"failure": "object_color_not_unique", "object_colors": sorted(object_colors)}

    object_color = next(iter(object_colors))
    object_cells = [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value == object_color
    ]
    if not object_cells:
        return None, {"failure": "no_object_cells", "object_color": object_color}
    if any(row in {0, height - 1} or col in {0, width - 1} for row, col in object_cells):
        return None, {
            "failure": "object_touches_edge",
            "object_color": object_color,
            "object_bbox": bbox_to_list(cells_to_bbox(object_cells)),
        }

    vertical_markers = marker_candidate["vertical_markers"]
    horizontal_markers = marker_candidate["horizontal_markers"]
    if not vertical_markers and not horizontal_markers:
        return None, {"failure": "no_axis_marker"}

    vertical_axis_col = vertical_markers[0][1] if vertical_markers else None
    vertical_marker_side = None
    if vertical_markers:
        vertical_marker_side = "top" if vertical_markers[0][0] == 0 else "bottom"

    horizontal_axis_row = horizontal_markers[0][0] if horizontal_markers else None
    horizontal_marker_side = None
    if horizontal_markers:
        horizontal_marker_side = "left" if horizontal_markers[0][1] == 0 else "right"

    return {
        "background": background,
        "marker_color": marker_color,
        "object_color": object_color,
        "object_cells": object_cells,
        "object_bbox": cells_to_bbox(object_cells),
        "vertical_axis_col": vertical_axis_col,
        "vertical_marker_side": vertical_marker_side,
        "horizontal_axis_row": horizontal_axis_row,
        "horizontal_marker_side": horizontal_marker_side,
        "marker_cell_count": color_counts[marker_color],
        "object_cell_count": color_counts[object_color],
    }, {}

def edge_marker_axis_projection_key(
    row: int,
    col: int,
    roles: dict[str, Any],
) -> tuple[str | None, str | None] | str | None:
    vertical_axis_col = roles["vertical_axis_col"]
    horizontal_axis_row = roles["horizontal_axis_row"]
    vertical_marker_side = roles["vertical_marker_side"]
    horizontal_marker_side = roles["horizontal_marker_side"]

    if vertical_axis_col is not None and col == vertical_axis_col:
        return None
    if horizontal_axis_row is not None and row == horizontal_axis_row:
        return None

    row_side: str | None = None
    if horizontal_axis_row is not None:
        row_side = "top" if row < horizontal_axis_row else "bottom"
    elif vertical_marker_side is not None:
        row_side = vertical_marker_side

    col_side: str | None = None
    if vertical_axis_col is not None:
        col_side = "left" if col < vertical_axis_col else "right"
    elif horizontal_marker_side is not None:
        col_side = horizontal_marker_side

    if (
        vertical_marker_side is not None
        and horizontal_marker_side is not None
        and row_side != vertical_marker_side
        and col_side != horizontal_marker_side
    ):
        return "skip"
    return row_side, col_side

def render_edge_marker_axis_projection(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    roles, rejection = infer_edge_marker_axis_roles(grid)
    if roles is None:
        return None, rejection

    height, width = grid_shape(grid)
    background = int(roles["background"])
    marker_color = int(roles["marker_color"])
    object_color = int(roles["object_color"])
    object_cells: list[Cell] = roles["object_cells"]
    vertical_axis_col = roles["vertical_axis_col"]
    vertical_marker_side = roles["vertical_marker_side"]
    horizontal_axis_row = roles["horizontal_axis_row"]
    horizontal_marker_side = roles["horizontal_marker_side"]

    output = [[background for _ in range(width)] for _ in range(height)]
    axis_segment_cells: set[Cell] = set()

    if vertical_axis_col is not None:
        axis_rows = sorted(row for row, col in object_cells if col == vertical_axis_col)
        if not axis_rows:
            return None, {
                "failure": "vertical_axis_has_no_object_cells",
                "vertical_axis_col": vertical_axis_col,
            }
        if vertical_marker_side == "top":
            rows = range(0, max(axis_rows) + 1)
        else:
            rows = range(min(axis_rows), height)
        for row in rows:
            output[row][vertical_axis_col] = marker_color
            axis_segment_cells.add((row, vertical_axis_col))

    if horizontal_axis_row is not None:
        axis_cols = sorted(col for row, col in object_cells if row == horizontal_axis_row)
        if not axis_cols:
            return None, {
                "failure": "horizontal_axis_has_no_object_cells",
                "horizontal_axis_row": horizontal_axis_row,
            }
        if horizontal_marker_side == "left":
            cols = range(0, max(axis_cols) + 1)
        else:
            cols = range(min(axis_cols), width)
        for col in cols:
            output[horizontal_axis_row][col] = marker_color
            axis_segment_cells.add((horizontal_axis_row, col))

    groups: dict[tuple[str | None, str | None], list[Cell]] = {}
    skipped_cells: list[Cell] = []
    for row, col in object_cells:
        key = edge_marker_axis_projection_key(row, col, roles)
        if key == "skip":
            skipped_cells.append((row, col))
            continue
        if key is None:
            continue
        groups.setdefault(key, []).append((row, col))

    group_bboxes = {key: cells_to_bbox(cells) for key, cells in groups.items()}
    projected_cells: set[Cell] = set()
    group_records: list[dict[str, Any]] = []
    for key, cells in sorted(groups.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))):
        row_side, col_side = key
        row0, col0, row1, col1 = group_bboxes[key]
        group_records.append(
            {
                "row_side": row_side,
                "col_side": col_side,
                "source_bbox": [row0, col0, row1, col1],
                "cell_count": len(cells),
            }
        )
        for row, col in cells:
            target_row = row
            target_col = col
            if row_side == "top":
                target_row = row - row0
            elif row_side == "bottom":
                target_row = (height - 1) - (row1 - row)
            if col_side == "left":
                target_col = col - col0
            elif col_side == "right":
                target_col = (width - 1) - (col1 - col)
            if not (0 <= target_row < height and 0 <= target_col < width):
                return None, {
                    "failure": "projected_cell_out_of_bounds",
                    "source_cell": [row, col],
                    "target_cell": [target_row, target_col],
                }
            output[target_row][target_col] = object_color
            projected_cells.add((target_row, target_col))

    for row, col in object_cells:
        key = edge_marker_axis_projection_key(row, col, roles)
        if key is None:
            output[row][col] = object_color
            projected_cells.add((row, col))

    if output == grid:
        return None, {"failure": "identity_render"}

    return output, {
        "renderer_case": "edge_marker_axis_projection",
        "background": background,
        "axis_marker_color": marker_color,
        "axis_object_color": object_color,
        "vertical_axis_col": vertical_axis_col,
        "vertical_marker_side": vertical_marker_side,
        "horizontal_axis_row": horizontal_axis_row,
        "horizontal_marker_side": horizontal_marker_side,
        "object_bbox": bbox_to_list(roles["object_bbox"]),
        "axis_segment_cell_count": len(axis_segment_cells),
        "axis_projected_cell_count": len(projected_cells),
        "axis_projection_group_count": len(groups),
        "axis_skipped_cell_count": len(skipped_cells),
        "projection_groups": group_records,
    }
