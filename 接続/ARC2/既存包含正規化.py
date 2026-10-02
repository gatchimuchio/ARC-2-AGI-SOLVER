from __future__ import annotations
from collections import Counter
from typing import Any
from .既存凡例穴対応 import grid_shape
Grid=list[list[int]]
NEIGHBORS_4=((1,0),(-1,0),(0,1),(0,-1))

def color_counter(grid: Grid) -> Counter[int]:
    return Counter(value for row in grid for value in row)

def dominant_color(grid: Grid) -> int:
    return color_counter(grid).most_common(1)[0][0]

def foreground_colors(grid: Grid, background: int) -> list[int]:
    return sorted(color for color in color_counter(grid) if color != background)

def bbox_contains(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
    outer_row0, outer_col0, outer_row1, outer_col1 = outer
    inner_row0, inner_col0, inner_row1, inner_col1 = inner
    return (
        outer_row0 < inner_row0
        and outer_col0 < inner_col0
        and outer_row1 > inner_row1
        and outer_col1 > inner_col1
    )

def intervals_overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return not (left[1] < right[0] or right[1] < left[0])

def foreground_components(grid: Grid, background: int) -> list[dict[str, Any]]:
    height, width = grid_shape(grid)
    seen: set[tuple[int, int]] = set()
    components = []
    component_id = 0
    for row in range(height):
        for col in range(width):
            if (row, col) in seen or grid[row][col] == background:
                continue
            color = grid[row][col]
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
                    if grid[next_row][next_col] != color:
                        continue
                    seen.add((next_row, next_col))
                    stack.append((next_row, next_col))

            rows = [cell_row for cell_row, _ in cells]
            cols = [cell_col for _, cell_col in cells]
            row0, col0, row1, col1 = min(rows), min(cols), max(rows), max(cols)
            components.append(
                {
                    "id": component_id,
                    "color": color,
                    "bbox": (row0, col0, row1, col1),
                    "height": row1 - row0 + 1,
                    "width": col1 - col0 + 1,
                    "size": len(cells),
                    "cells": cells,
                    "children": [],
                    "parent": None,
                }
            )
            component_id += 1
    return sorted(components, key=lambda item: (item["bbox"], item["size"]))

def build_containment_tree(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {component["id"]: component for component in components}
    for component in components:
        component["children"] = []
        component["parent"] = None

    for child in components:
        containers = [
            component
            for component in components
            if component["id"] != child["id"]
            and bbox_contains(component["bbox"], child["bbox"])
        ]
        if not containers:
            continue
        parent = min(
            containers,
            key=lambda item: (item["height"] * item["width"], item["size"]),
        )
        child["parent"] = parent["id"]
        by_id[parent["id"]]["children"].append(child["id"])
    return components

def arrange_axis(items: list[dict[str, Any]], axis: str) -> tuple[dict[int, int], list[dict[str, Any]]]:
    index = 0 if axis == "row" else 1
    length_key = "render_height" if axis == "row" else "render_width"
    records = []
    for item in items:
        bbox = item["bbox"]
        interval = (bbox[index], bbox[index + 2])
        center = (interval[0] + interval[1]) / 2
        records.append(
            {
                "item": item,
                "interval": interval,
                "center": center,
                "half_extent": (item[length_key] - 1) // 2,
            }
        )
    records.sort(key=lambda item: (item["center"], item["interval"]))

    groups: list[dict[str, Any]] = []
    for record in records:
        for group in groups:
            if intervals_overlap(record["interval"], group["interval"]):
                group["records"].append(record)
                group["interval"] = (
                    min(group["interval"][0], record["interval"][0]),
                    max(group["interval"][1], record["interval"][1]),
                )
                group["half_extent"] = max(group["half_extent"], record["half_extent"])
                break
        else:
            groups.append(
                {
                    "records": [record],
                    "interval": record["interval"],
                    "half_extent": record["half_extent"],
                }
            )

    changed = True
    while changed:
        changed = False
        merged: list[dict[str, Any]] = []
        for group in groups:
            for existing in merged:
                if intervals_overlap(group["interval"], existing["interval"]):
                    existing["records"].extend(group["records"])
                    existing["interval"] = (
                        min(existing["interval"][0], group["interval"][0]),
                        max(existing["interval"][1], group["interval"][1]),
                    )
                    existing["half_extent"] = max(
                        existing["half_extent"], group["half_extent"]
                    )
                    changed = True
                    break
            else:
                merged.append(group)
        groups = sorted(
            merged,
            key=lambda item: (item["interval"][0] + item["interval"][1]) / 2,
        )

    positions: dict[int, int] = {}
    previous_center_half: tuple[int, int] | None = None
    for group in groups:
        if previous_center_half is None:
            output_center = group["half_extent"]
        else:
            previous_center, previous_half = previous_center_half
            output_center = previous_center + previous_half + 2 + group["half_extent"]
        group["output_center"] = output_center
        for record in group["records"]:
            positions[record["item"]["id"]] = output_center - record["half_extent"]
        previous_center_half = (output_center, group["half_extent"])
    return positions, groups

def render_node(
    node_id: int,
    components_by_id: dict[int, dict[str, Any]],
    background: int,
    foreground: int,
) -> dict[str, Any]:
    node = components_by_id[node_id]
    if not node["children"]:
        node["render_height"] = 1
        node["render_width"] = 1
        node["grid"] = [[foreground]]
        node["axis_groups"] = {"row": [], "col": []}
        return node

    children = [
        render_node(child_id, components_by_id, background, foreground)
        for child_id in node["children"]
    ]
    row_positions, row_groups = arrange_axis(children, "row")
    col_positions, col_groups = arrange_axis(children, "col")
    max_row = max(
        row_positions[child["id"]] + child["render_height"] - 1
        for child in children
    )
    max_col = max(
        col_positions[child["id"]] + child["render_width"] - 1
        for child in children
    )
    height = max_row + 5
    width = max_col + 5
    grid = [[background] * width for _ in range(height)]
    for row in range(height):
        grid[row][0] = foreground
        grid[row][width - 1] = foreground
    for col in range(width):
        grid[0][col] = foreground
        grid[height - 1][col] = foreground

    child_positions: dict[int, tuple[int, int]] = {}
    for child in children:
        row0 = row_positions[child["id"]] + 2
        col0 = col_positions[child["id"]] + 2
        child_positions[child["id"]] = (row0, col0)
        for row, values in enumerate(child["grid"]):
            for col, value in enumerate(values):
                if value == foreground:
                    grid[row0 + row][col0 + col] = foreground

    node["render_height"] = height
    node["render_width"] = width
    node["grid"] = grid
    node["child_positions"] = child_positions
    node["axis_groups"] = {
        "row": [
            {
                "interval": group["interval"],
                "output_center": group["output_center"] + 2,
            }
            for group in row_groups
        ],
        "col": [
            {
                "interval": group["interval"],
                "output_center": group["output_center"] + 2,
            }
            for group in col_groups
        ],
    }
    return node

def map_external_axis(component: dict[str, Any], root: dict[str, Any], axis: str) -> tuple[int, str]:
    index = 0 if axis == "row" else 1
    size = root["render_height"] if axis == "row" else root["render_width"]
    interval = (component["bbox"][index], component["bbox"][index + 2])
    root_interval = (root["bbox"][index], root["bbox"][index + 2])
    if interval[1] < root_interval[0]:
        return -2, "before"
    if interval[0] > root_interval[1]:
        return size + 1, "after"

    overlapping_groups = [
        group
        for group in root["axis_groups"][axis]
        if intervals_overlap(interval, group["interval"])
    ]
    if overlapping_groups:
        center = (interval[0] + interval[1]) / 2
        best_group = min(
            overlapping_groups,
            key=lambda group: (
                abs(((group["interval"][0] + group["interval"][1]) / 2) - center),
                group["interval"][1] - group["interval"][0],
            ),
        )
        return best_group["output_center"], "aligned"
    return (size - 1) // 2, "root_center"

def serializable_component(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": component["id"],
        "color": component["color"],
        "bbox": list(component["bbox"]),
        "height": component["height"],
        "width": component["width"],
        "size": component["size"],
        "parent": component["parent"],
        "children": sorted(component["children"]),
    }

def render_nested_frame_inventory(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    background = dominant_color(grid)
    colors = foreground_colors(grid, background)
    if len(colors) != 1:
        return None, {
            "failure": "not_single_foreground_color",
            "background": background,
            "foreground_colors": colors,
        }
    foreground = colors[0]
    components = build_containment_tree(foreground_components(grid, background))
    if not (2 <= len(components) <= 8):
        return None, {
            "failure": "component_count_out_of_range",
            "background": background,
            "foreground": foreground,
            "component_count": len(components),
        }

    roots = [component for component in components if component["parent"] is None]
    frame_roots = [component for component in roots if component["children"]]
    if len(frame_roots) != 1:
        return None, {
            "failure": "expected_one_root_frame",
            "background": background,
            "foreground": foreground,
            "root_count": len(roots),
            "frame_root_count": len(frame_roots),
        }
    if any(component["children"] for component in roots if component["id"] != frame_roots[0]["id"]):
        return None, {
            "failure": "external_frame_not_supported",
            "background": background,
            "foreground": foreground,
        }

    components_by_id = {component["id"]: component for component in components}
    root = render_node(frame_roots[0]["id"], components_by_id, background, foreground)
    base_grid = root["grid"]
    external_components = [
        component for component in roots if component["id"] != root["id"]
    ]

    external_placements = []
    min_row = 0
    min_col = 0
    max_row = root["render_height"] - 1
    max_col = root["render_width"] - 1
    for component in external_components:
        row, row_relation = map_external_axis(component, root, "row")
        col, col_relation = map_external_axis(component, root, "col")
        external_placements.append(
            {
                "component_id": component["id"],
                "output_cell": [row, col],
                "row_relation": row_relation,
                "col_relation": col_relation,
            }
        )
        if row < 0:
            min_row = min(min_row, row - 1)
        if col < 0:
            min_col = min(min_col, col - 1)
        if row > max_row:
            max_row = max(max_row, row + 1)
        if col > max_col:
            max_col = max(max_col, col + 1)

    output = [
        [background] * (max_col - min_col + 1)
        for _ in range(max_row - min_row + 1)
    ]
    for row, values in enumerate(base_grid):
        for col, value in enumerate(values):
            output[row - min_row][col - min_col] = value
    for placement in external_placements:
        row, col = placement["output_cell"]
        output[row - min_row][col - min_col] = foreground

    input_height, input_width = grid_shape(grid)
    output_height, output_width = grid_shape(output)
    if output_height >= input_height or output_width >= input_width:
        return None, {
            "failure": "output_not_smaller_than_input",
            "input_shape": [input_height, input_width],
            "candidate_shape": [output_height, output_width],
        }

    record = {
        "background": background,
        "foreground": foreground,
        "input_shape": [input_height, input_width],
        "output_shape": [output_height, output_width],
        "component_count": len(components),
        "components": [serializable_component(component) for component in components],
        "root_component_id": root["id"],
        "root_render_shape": [root["render_height"], root["render_width"]],
        "root_axis_groups": {
            axis: [
                {
                    "interval": list(group["interval"]),
                    "output_center": group["output_center"],
                }
                for group in groups
            ]
            for axis, groups in root["axis_groups"].items()
        },
        "external_placements": external_placements,
    }
    return output, record
