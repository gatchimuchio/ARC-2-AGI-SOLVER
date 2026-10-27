from __future__ import annotations
from collections import Counter, deque
from typing import Any
from .既存凡例経路 import dominant_background
from .既存凡例穴対応 import grid_shape, bbox_to_list
Grid=list[list[int]]
Cell=tuple[int,int]
BBox=tuple[int,int,int,int]

def color_components(grid: Grid, color: int) -> list[dict[str, Any]]:
    height, width = grid_shape(grid)
    seen: set[Cell] = set()
    components: list[dict[str, Any]] = []
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
                for row_delta, col_delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
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
            components.append(
                {
                    "color": color,
                    "cells": cells,
                    "bbox": (min(rows), min(cols), max(rows), max(cols)),
                    "size": len(cells),
                }
            )
    return sorted(components, key=lambda component: (component["bbox"], component["size"]))

def foreground_components(grid: Grid, background: int) -> list[dict[str, Any]]:
    colors = sorted({value for row in grid for value in row if value != background})
    components: list[dict[str, Any]] = []
    for color in colors:
        components.extend(color_components(grid, color))
    return sorted(components, key=lambda component: (component["bbox"], component["color"]))

def component_summary(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "color": component["color"],
        "bbox": bbox_to_list(component["bbox"]),
        "size": component["size"],
    }

def perimeter_cells(bbox: BBox) -> set[Cell]:
    row0, col0, row1, col1 = bbox
    return {
        (row, col)
        for row in range(row0, row1 + 1)
        for col in range(col0, col1 + 1)
        if row in {row0, row1} or col in {col0, col1}
    }

def is_rectangular_frame(component: dict[str, Any]) -> bool:
    row0, col0, row1, col1 = component["bbox"]
    height = row1 - row0 + 1
    width = col1 - col0 + 1
    if height < 5 or width < 5:
        return False
    return component["cells"] == perimeter_cells(component["bbox"])

def render_frame_component_count_slots(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    background = dominant_background(grid)
    components = foreground_components(grid, background)
    frames = [component for component in components if is_rectangular_frame(component)]
    if len(frames) < 2:
        return None, {
            "failure": "too_few_rectangular_frames",
            "frame_count": len(frames),
        }

    frame_shapes = {
        (
            frame["bbox"][2] - frame["bbox"][0] + 1,
            frame["bbox"][3] - frame["bbox"][1] + 1,
        )
        for frame in frames
    }
    if len(frame_shapes) != 1:
        return None, {
            "failure": "mixed_frame_shapes",
            "frame_shapes": [list(shape) for shape in sorted(frame_shapes)],
        }

    small_components = [component for component in components if not is_rectangular_frame(component)]
    count_by_color = Counter(component["color"] for component in small_components)

    output = [[background for _ in row] for row in grid]
    frame_records: list[dict[str, Any]] = []
    for frame in sorted(frames, key=lambda component: (component["bbox"], component["color"])):
        color = frame["color"]
        for row, col in frame["cells"]:
            output[row][col] = color

        row0, col0, row1, col1 = frame["bbox"]
        center_row = (row0 + row1) // 2
        slots = list(range(col0 + 2, col1 - 1, 2))
        count = count_by_color[color]
        if count > len(slots):
            return None, {
                "failure": "slot_overflow",
                "frame": component_summary(frame),
                "small_component_count": count,
                "slots": slots,
            }
        chosen_slots = slots[-count:] if count else []
        for col in chosen_slots:
            output[center_row][col] = color

        frame_records.append(
            {
                "frame": component_summary(frame),
                "small_component_count": count,
                "slot_columns": slots,
                "chosen_slot_columns": chosen_slots,
                "center_row": center_row,
            }
        )

    if output == grid:
        return None, {"failure": "identity_render"}
    return output, {
        "background": background,
        "frame_records": frame_records,
        "small_components": [component_summary(component) for component in small_components],
    }
