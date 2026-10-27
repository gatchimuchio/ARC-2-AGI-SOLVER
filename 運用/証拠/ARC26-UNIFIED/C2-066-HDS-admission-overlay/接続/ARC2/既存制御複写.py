"""既存の下端bar役割とcomponent数による複写・再着色。"""
from __future__ import annotations
from collections import Counter,deque
from functools import lru_cache
from typing import Any
import math
from .既存凡例穴対応 import grid_shape,clone_grid
from .既存辺対応抽出 import dominant_background
from .既存領域転写 import Grid,GridKey,Cell,BBox,grid_key,ORTHOGONAL_DIRECTIONS
from .既存物体特徴 import _record
ComponentRecord=tuple[int,tuple[Cell,...],BBox,int]

@lru_cache(maxsize=8192)
def _color_set_component_records(
    key: GridKey,
    colors: tuple[int, ...],
) -> tuple[ComponentRecord, ...]:
    color_set = set(colors)
    height = len(key)
    width = len(key[0]) if key else 0
    seen: set[Cell] = set()
    components: list[ComponentRecord] = []

    for row in range(height):
        for col in range(width):
            color = int(key[row][col])
            if color not in color_set or (row, col) in seen:
                continue
            queue: deque[Cell] = deque([(row, col)])
            seen.add((row, col))
            cells: list[Cell] = []
            while queue:
                current_row, current_col = queue.popleft()
                cells.append((current_row, current_col))
                for row_delta, col_delta in ORTHOGONAL_DIRECTIONS:
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

    return tuple(components)

def connected_component_dicts_for_grid(
    grid: Grid,
    colors: set[int],
) -> list[dict[str, Any]]:
    return [
        {
            "color": int(record_color),
            "cells": list(cells),
            "bbox": bbox,
        }
        for record_color, cells, bbox, _size in _color_set_component_records(
            grid_key(grid),
            tuple(sorted(int(color) for color in colors)),
        )
    ]

def _control_bar_shape_source(grid: Grid) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    if height < 3 or width < 3:
        return None, {
            "failure": "control_bar_shape_invalid_shape",
            "control_bar_shape_input_shape": [height, width],
        }
    if any(len(row) != width for row in grid):
        return None, {"failure": "control_bar_shape_ragged_grid"}

    background = int(dominant_background(grid))
    colors = {
        int(value)
        for row in grid
        for value in row
        if int(value) != background
    }
    components = connected_component_dicts_for_grid(grid, colors)
    control_bars: list[dict[str, Any]] = []
    shapes: list[dict[str, Any]] = []
    for component in components:
        cells = [(int(row), int(col)) for row, col in component["cells"]]
        row0, col0, row1, col1 = tuple(int(value) for value in component["bbox"])
        if row0 == row1 == height - 1:
            if col1 - col0 + 1 < 2:
                return None, {
                    "failure": "control_bar_shape_control_segment_too_short",
                    "control_bar_shape_control_bbox": [row0, col0, row1, col1],
                }
            control_bars.append(
                {
                    "color": int(component["color"]),
                    "cells": cells,
                    "bbox": (row0, col0, row1, col1),
                }
            )
        elif all(row < height - 1 for row, _ in cells):
            shapes.append(
                {
                    "color": int(component["color"]),
                    "cells": cells,
                    "bbox": (row0, col0, row1, col1),
                }
            )

    control_colors = sorted({int(bar["color"]) for bar in control_bars})
    if len(control_bars) < 2 or len(control_colors) < 2:
        return None, {
            "failure": "control_bar_shape_requires_two_control_roles",
            "control_bar_shape_control_count": len(control_bars),
            "control_bar_shape_control_colors": control_colors,
        }
    if not shapes:
        return None, {"failure": "control_bar_shape_requires_noncontrol_shapes"}

    row_starts = sorted({int(shape["bbox"][0]) for shape in shapes})
    row_gaps = [right - left for left, right in zip(row_starts, row_starts[1:]) if right > left]
    shape_heights = [int(shape["bbox"][2]) - int(shape["bbox"][0]) + 1 for shape in shapes]
    common_height = Counter(shape_heights).most_common(1)[0][0]
    inferred_period = int(common_height) + 1
    if row_gaps:
        gap_gcd = int(math.gcd(*row_gaps))
        if gap_gcd > 0 and inferred_period <= 1:
            inferred_period = gap_gcd
        elif gap_gcd > 0 and any(gap % inferred_period for gap in row_gaps):
            inferred_period = gap_gcd

    return {
        "background": background,
        "height": height,
        "width": width,
        "control_bars": control_bars,
        "control_colors": control_colors,
        "shapes": shapes,
        "inferred_period": inferred_period,
    }, {}

def _control_bar_affected_shape_indexes(
    source: dict[str, Any],
    control_color: int,
) -> list[int]:
    bar_columns = {
        col
        for bar in source["control_bars"]
        if int(bar["color"]) == int(control_color)
        for _, col in bar["cells"]
    }
    return [
        index
        for index, shape in enumerate(source["shapes"])
        if any(col in bar_columns for _, col in shape["cells"])
    ]

def render_control_bar_shape_rewrite(
    grid: Grid,
    recolor_control_color: int | None = None,
    copy_control_color: int | None = None,
    recolor_target_color: int | None = None,
    period: int | None = None,
) -> tuple[Grid | None, dict[str, Any]]:
    if (
        recolor_control_color is None
        or copy_control_color is None
        or recolor_target_color is None
    ):
        return None, {"failure": "control_bar_shape_missing_policy"}
    source, rejection = _control_bar_shape_source(grid)
    if source is None:
        return None, rejection
    control_colors = set(int(color) for color in source["control_colors"])
    if int(recolor_control_color) not in control_colors or int(copy_control_color) not in control_colors:
        return None, {
            "failure": "control_bar_shape_policy_color_missing",
            "control_bar_shape_control_colors": sorted(control_colors),
            "control_bar_shape_recolor_control_color": int(recolor_control_color),
            "control_bar_shape_copy_control_color": int(copy_control_color),
        }
    if int(recolor_control_color) == int(copy_control_color):
        return None, {"failure": "control_bar_shape_control_roles_collide"}

    recolor_indexes = _control_bar_affected_shape_indexes(
        source,
        int(recolor_control_color),
    )
    copy_indexes = _control_bar_affected_shape_indexes(source, int(copy_control_color))
    if not recolor_indexes or not copy_indexes:
        return None, {
            "failure": "control_bar_shape_role_has_no_affected_shapes",
            "control_bar_shape_recolor_shape_count": len(recolor_indexes),
            "control_bar_shape_copy_shape_count": len(copy_indexes),
        }

    copy_period = int(period if period is not None else source["inferred_period"])
    if copy_period <= 0:
        return None, {"failure": "control_bar_shape_invalid_period", "period": copy_period}

    highest_copy_indexes: list[int] = []
    for index in copy_indexes:
        if index not in highest_copy_indexes:
            highest_copy_indexes.append(index)
    min_rows = [int(source["shapes"][index]["bbox"][0]) for index in highest_copy_indexes]
    highest_row = min(min_rows)
    highest_copy_indexes = [
        index
        for index in highest_copy_indexes
        if int(source["shapes"][index]["bbox"][0]) == highest_row
    ]
    if len(highest_copy_indexes) != 1:
        return None, {
            "failure": "control_bar_shape_copy_highest_not_unique",
            "control_bar_shape_copy_highest_indexes": highest_copy_indexes,
        }

    source_shape = source["shapes"][highest_copy_indexes[0]]
    copy_cells: dict[Cell, int] = {}
    for repeat_index in range(1, len(set(recolor_indexes)) + 1):
        row_offset = copy_period * repeat_index
        for row, col in source_shape["cells"]:
            copied_row = int(row) - row_offset
            if copied_row < 0:
                continue
            target = (copied_row, int(col))
            if int(grid[copied_row][int(col)]) not in {
                int(source["background"]),
                int(source_shape["color"]),
            }:
                return None, {
                    "failure": "control_bar_shape_copy_hits_foreground",
                    "control_bar_shape_copy_target": [copied_row, int(col)],
                    "control_bar_shape_copy_source_color": int(source_shape["color"]),
                }
            previous = copy_cells.get(target)
            if previous is not None and previous != int(source_shape["color"]):
                return None, {
                    "failure": "control_bar_shape_copy_color_conflict",
                    "control_bar_shape_copy_target": [copied_row, int(col)],
                }
            copy_cells[target] = int(source_shape["color"])

    output = clone_grid(grid)
    last_row = int(source["height"]) - 1
    for col in range(int(source["width"])):
        output[last_row][col] = int(source["background"])
    recolor_cells = {
        cell
        for index in recolor_indexes
        for cell in source["shapes"][index]["cells"]
    }
    for row, col in recolor_cells:
        output[int(row)][int(col)] = int(recolor_target_color)
    for (row, col), color in copy_cells.items():
        output[int(row)][int(col)] = int(color)

    changed_cells = [
        (row, col)
        for row in range(int(source["height"]))
        for col in range(int(source["width"]))
        if int(output[row][col]) != int(grid[row][col])
    ]
    if not changed_cells:
        return None, {"failure": "control_bar_shape_identity_render"}
    return output, {
        "renderer_case": "control_bar_shape_rewrite",
        "control_bar_shape_background_color": int(source["background"]),
        "control_bar_shape_recolor_control_color": int(recolor_control_color),
        "control_bar_shape_copy_control_color": int(copy_control_color),
        "control_bar_shape_recolor_target_color": int(recolor_target_color),
        "control_bar_shape_period": copy_period,
        "control_bar_shape_control_count": len(source["control_bars"]),
        "control_bar_shape_recolor_shape_count": len(set(recolor_indexes)),
        "control_bar_shape_copy_shape_count": len(set(copy_indexes)),
        "control_bar_shape_copy_cell_count": len(copy_cells),
        "control_bar_shape_recolored_cell_count": len(recolor_cells),
        "control_bar_shape_event_count": len(changed_cells),
        "control_bar_shape_input_shape": [int(source["height"]), int(source["width"])],
        "control_bar_shape_output_shape": list(grid_shape(output)),
    }
