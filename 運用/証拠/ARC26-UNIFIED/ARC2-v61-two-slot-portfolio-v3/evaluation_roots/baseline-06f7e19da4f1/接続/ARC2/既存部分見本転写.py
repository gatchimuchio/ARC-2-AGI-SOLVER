"""旧ARCの同色外部見本を正方形panelへ転写する機構。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / v36_partial_panel_exemplar。
7関数は原文のまま。成分recordを現在の共有extractorから投影する。
"""
from __future__ import annotations
from collections import defaultdict
from .既存領域転写 import Grid
from .既存凡例穴対応 import grid_shape
from .既存対角領域 import is_rectangular
from .既存物体特徴 import dominant_background_for_grid as dominant_color
from .既存軸反射 import connected_components_for_colors


def same_color_components_excluding_background(grid):
    if not is_rectangular(grid):
        return []
    background = dominant_color(grid)
    records = []
    for part in connected_components_for_colors(grid, {v for row in grid for v in row} - {background}):
        row0, col0, row1, col1 = part['bbox']
        h, w, size = row1-row0+1, col1-col0+1, len(part['cells'])
        records.append({**part, 'height':h, 'width':w, 'size':size, 'filled':size==h*w})
    return records

def component_bbox(cells: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    rows = [row for row, _ in cells]
    cols = [col for _, col in cells]
    return min(rows), min(cols), max(rows), max(cols)

def filled_square_panel_candidates(components: list[dict]) -> list[dict]:
    return [
        component
        for component in components
        if component["filled"]
        and component["height"] >= 3
        and component["height"] == component["width"]
    ]

def panel_group_sort_key(panels: list[dict]) -> tuple[int, int]:
    panel = panels[0]
    return panel["height"] * panel["width"], len(panels)

def color_cells_outside_panel(
    grid: Grid, color: int, panel_cells: set[tuple[int, int]]
) -> list[tuple[int, int]]:
    height, width = grid_shape(grid)
    cells: list[tuple[int, int]] = []
    for row in range(height):
        for col in range(width):
            if grid[row][col] == color and (row, col) not in panel_cells:
                cells.append((row, col))
    return cells

def exemplar_mask_for_panel(grid: Grid, panel: dict) -> dict | None:
    cells = color_cells_outside_panel(grid, panel["color"], set(panel["cells"]))
    if not cells:
        return None
    bbox = component_bbox(cells)
    mask_height = bbox[2] - bbox[0] + 1
    mask_width = bbox[3] - bbox[1] + 1
    if mask_height > panel["height"] or mask_width > panel["width"]:
        return None
    if len(cells) >= panel["size"]:
        return None
    return {
        "color": panel["color"],
        "cells": sorted(cells),
        "bbox": bbox,
        "height": mask_height,
        "width": mask_width,
        "size": len(cells),
    }

def select_panel_exemplar_group(grid: Grid) -> dict | None:
    if not is_rectangular(grid):
        return None
    components = same_color_components_excluding_background(grid)
    candidates = filled_square_panel_candidates(components)
    groups: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for candidate in candidates:
        groups[(candidate["height"], candidate["width"])].append(candidate)

    for panels in sorted(groups.values(), key=panel_group_sort_key, reverse=True):
        panel_height = panels[0]["height"]
        panel_width = panels[0]["width"]
        if len(panels) < 2:
            continue

        colors = [panel["color"] for panel in panels]
        if len(colors) != len(set(colors)):
            continue

        row_positions = sorted({panel["bbox"][0] for panel in panels})
        col_positions = sorted({panel["bbox"][1] for panel in panels})
        if len(row_positions) * len(col_positions) != len(panels):
            continue

        panel_by_position = {
            (panel["bbox"][0], panel["bbox"][1]): panel for panel in panels
        }
        if any(
            (row, col) not in panel_by_position
            for row in row_positions
            for col in col_positions
        ):
            continue

        masks: dict[int, dict] = {}
        for panel in panels:
            mask = exemplar_mask_for_panel(grid, panel)
            if mask is None:
                break
            masks[panel["color"]] = mask
        if len(masks) != len(panels):
            continue

        return {
            "background": dominant_color(grid),
            "panel_height": panel_height,
            "panel_width": panel_width,
            "row_positions": row_positions,
            "col_positions": col_positions,
            "panels": panels,
            "panel_by_position": panel_by_position,
            "masks": masks,
        }

    return None

def partial_panel_exemplar_transfer(grid: Grid) -> Grid | None:
    group = select_panel_exemplar_group(grid)
    if group is None:
        return None

    background = group["background"]
    panel_height = group["panel_height"]
    panel_width = group["panel_width"]
    row_positions = group["row_positions"]
    col_positions = group["col_positions"]
    panel_by_position = group["panel_by_position"]
    masks = group["masks"]

    output_height = len(row_positions) * (panel_height + 1) + 1
    output_width = len(col_positions) * (panel_width + 1) + 1
    output: Grid = [
        [background for _ in range(output_width)] for _ in range(output_height)
    ]

    for row_index, panel_top in enumerate(row_positions):
        for col_index, panel_left in enumerate(col_positions):
            panel = panel_by_position[(panel_top, panel_left)]
            mask = masks[panel["color"]]
            tile_top = row_index * (panel_height + 1)
            tile_left = col_index * (panel_width + 1)

            for row in range(panel_height):
                for col in range(panel_width):
                    output[tile_top + 1 + row][tile_left + 1 + col] = panel["color"]

            mask_top, mask_left, _, _ = mask["bbox"]
            offset_row = (panel_height - mask["height"]) // 2
            offset_col = (panel_width - mask["width"]) // 2
            for mask_row, mask_col in mask["cells"]:
                row = tile_top + 1 + offset_row + (mask_row - mask_top)
                col = tile_left + 1 + offset_col + (mask_col - mask_left)
                output[row][col] = background

    return output
