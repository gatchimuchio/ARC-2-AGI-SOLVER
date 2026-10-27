from __future__ import annotations
from collections import Counter, deque
from .既存凡例穴対応 import grid_shape, clone_grid
from .既存対角領域 import is_rectangular
from .既存種境界 import component_bbox
Grid=list[list[int]]
NEIGHBORS_4=((1,0),(-1,0),(0,1),(0,-1))

def color_count(grid: Grid, color: int) -> int:
    return sum(value == color for row in grid for value in row)

def infer_marker_target_background(task: dict) -> dict | None:
    marker_colors: set[int] = set()
    target_colors: set[int] = set()
    background_colors: set[int] = set()

    for pair in task["train"]:
        input_grid = pair["input"]
        output_grid = pair["output"]
        if not (is_rectangular(input_grid) and is_rectangular(output_grid)):
            return None

        input_colors = {value for row in input_grid for value in row}
        output_colors = {value for row in output_grid for value in row}
        disappeared = input_colors - output_colors
        if len(disappeared) != 1:
            return None
        marker = next(iter(disappeared))

        preserved = [
            color
            for color in input_colors & output_colors
            if color_count(input_grid, color) == color_count(output_grid, color)
        ]
        if len(preserved) != 1:
            return None
        target = preserved[0]

        remaining = (input_colors | output_colors) - {marker, target}
        if len(remaining) != 1:
            return None
        background = next(iter(remaining))

        marker_colors.add(marker)
        target_colors.add(target)
        background_colors.add(background)

    if not (
        len(marker_colors) == 1
        and len(target_colors) == 1
        and len(background_colors) == 1
    ):
        return None

    return {
        "marker": next(iter(marker_colors)),
        "target": next(iter(target_colors)),
        "background": next(iter(background_colors)),
    }


def same_color_components(grid: Grid, color: int) -> list[dict]:
    if not is_rectangular(grid):
        return []
    height, width = grid_shape(grid)
    seen: set[tuple[int, int]] = set()
    components: list[dict] = []

    for row in range(height):
        for col in range(width):
            if (row, col) in seen or grid[row][col] != color:
                continue
            queue = deque([(row, col)])
            seen.add((row, col))
            cells: list[tuple[int, int]] = []
            while queue:
                current_row, current_col = queue.popleft()
                cells.append((current_row, current_col))
                for delta_row, delta_col in NEIGHBORS_4:
                    next_row = current_row + delta_row
                    next_col = current_col + delta_col
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if (next_row, next_col) in seen:
                        continue
                    if grid[next_row][next_col] != color:
                        continue
                    seen.add((next_row, next_col))
                    queue.append((next_row, next_col))

            bbox = component_bbox(cells)
            components.append(
                {
                    "cells": set(cells),
                    "bbox": bbox,
                    "size": len(cells),
                }
            )

    return sorted(components, key=lambda item: item["bbox"])

def tight_render(
    cells: set[tuple[int, int]], background: int, target: int
) -> tuple[Grid | None, tuple[int, int, int, int] | None]:
    if not cells:
        return None, None
    top, left, bottom, right = component_bbox(cells)
    output = [
        [
            target if (row, col) in cells else background
            for col in range(left, right + 1)
        ]
        for row in range(top, bottom + 1)
    ]
    return output, (top, left, bottom, right)

def marker_guided_assembly_candidates(grid: Grid, colors: dict) -> list[dict]:
    marker = colors["marker"]
    target = colors["target"]
    background = colors["background"]
    if not is_rectangular(grid):
        return []

    height, width = grid_shape(grid)
    target_components = same_color_components(grid, target)
    marker_components = same_color_components(grid, marker)
    if len(marker_components) != 2 or len(target_components) < 2:
        return []

    candidates: list[dict] = []
    for source_index, source_marker in enumerate(marker_components):
        for dest_index, dest_marker in enumerate(marker_components):
            if source_index == dest_index:
                continue
            if source_marker["size"] != dest_marker["size"]:
                continue

            source_top, source_left, _, _ = source_marker["bbox"]
            dest_top, dest_left, _, _ = dest_marker["bbox"]
            for direction_index, (delta_row, delta_col) in enumerate(NEIGHBORS_4):
                attached_cells = {
                    (row + delta_row, col + delta_col)
                    for row, col in source_marker["cells"]
                }
                if not all(
                    0 <= row < height
                    and 0 <= col < width
                    and grid[row][col] == target
                    for row, col in attached_cells
                ):
                    continue

                vector_row = dest_top - (source_top + delta_row)
                vector_col = dest_left - (source_left + delta_col)
                if vector_row == 0 and vector_col == 0:
                    continue

                moving_indices: list[int] = []
                fixed_indices: list[int] = []
                for component_index, component in enumerate(target_components):
                    component_cells = component["cells"]
                    comp_top, comp_left, comp_bottom, comp_right = component["bbox"]
                    include = bool(component_cells & attached_cells)
                    if not include:
                        if abs(vector_col) >= abs(vector_row):
                            if vector_col < 0 and comp_left >= source_left:
                                include = True
                            if vector_col > 0 and comp_right <= source_marker["bbox"][3]:
                                include = True
                        else:
                            if vector_row < 0 and comp_top >= source_top:
                                include = True
                            if vector_row > 0 and comp_bottom <= source_marker["bbox"][2]:
                                include = True

                    if include:
                        moving_indices.append(component_index)
                    else:
                        fixed_indices.append(component_index)

                if not moving_indices or not fixed_indices:
                    continue

                output_cells: set[tuple[int, int]] = set()
                overlap = False
                for component_index, component in enumerate(target_components):
                    if component_index in moving_indices:
                        component_cells = {
                            (row + vector_row, col + vector_col)
                            for row, col in component["cells"]
                        }
                    else:
                        component_cells = set(component["cells"])
                    if output_cells & component_cells:
                        overlap = True
                        break
                    output_cells |= component_cells

                if overlap:
                    continue

                output, output_bbox = tight_render(output_cells, background, target)
                if output is None or output_bbox is None:
                    continue
                output_height, output_width = grid_shape(output)
                candidates.append(
                    {
                        "output": output,
                        "record": {
                            "source_marker_index": source_index,
                            "source_marker_bbox": list(source_marker["bbox"]),
                            "dest_marker_index": dest_index,
                            "dest_marker_bbox": list(dest_marker["bbox"]),
                            "attachment_direction": [delta_row, delta_col],
                            "direction_index": direction_index,
                            "translation_vector": [vector_row, vector_col],
                            "moving_component_indices": moving_indices,
                            "fixed_component_indices": fixed_indices,
                            "target_component_bboxes": [
                                list(component["bbox"]) for component in target_components
                            ],
                            "output_bbox": list(output_bbox),
                            "output_shape": [output_height, output_width],
                            "output_area": output_height * output_width,
                        },
                    }
                )

    candidates.sort(
        key=lambda item: (
            item["record"]["output_area"],
            item["record"]["output_shape"],
            len(item["record"]["moving_component_indices"]),
            item["record"]["source_marker_bbox"],
            item["record"]["dest_marker_bbox"],
            item["record"]["direction_index"],
        )
    )
    return candidates

def marker_guided_foreground_component_assembly(
    grid: Grid, colors: dict
) -> tuple[Grid | None, list[dict]]:
    candidates = marker_guided_assembly_candidates(grid, colors)
    if not candidates:
        return None, []
    selected = candidates[0]
    return selected["output"], [selected["record"]]
