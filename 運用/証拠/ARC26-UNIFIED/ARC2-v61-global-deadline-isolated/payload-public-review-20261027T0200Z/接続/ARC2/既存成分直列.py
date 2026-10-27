from __future__ import annotations
from .既存対称剪定 import dominant_color
from .既存部分見本転写 import component_bbox
from .既存凡例穴対応 import grid_shape
from .既存対角領域 import is_rectangular
Grid=list[list[int]]

def same_color_components_excluding_background(grid: Grid) -> list[dict]:
    if not is_rectangular(grid):
        return []
    height, width = grid_shape(grid)
    background = dominant_color(grid)
    seen: set[tuple[int, int]] = set()
    components: list[dict] = []

    for row in range(height):
        for col in range(width):
            if (row, col) in seen or grid[row][col] == background:
                continue
            color = grid[row][col]
            stack = [(row, col)]
            seen.add((row, col))
            cells: list[tuple[int, int]] = []
            while stack:
                current_row, current_col = stack.pop()
                cells.append((current_row, current_col))
                for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
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
            bbox = component_bbox(cells)
            components.append(
                {
                    "color": color,
                    "cells": sorted(cells),
                    "bbox": bbox,
                    "size": len(cells),
                }
            )

    return components

def component_order_key(component: dict) -> tuple[int, int, int, int, int]:
    return (
        component["bbox"][0],
        component["bbox"][1],
        component["bbox"][2],
        component["bbox"][3],
        component["color"],
    )

def adjacent_components(left: dict, right: dict) -> bool:
    right_cells = set(right["cells"])
    for row, col in left["cells"]:
        for delta_row, delta_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if (row + delta_row, col + delta_col) in right_cells:
                return True
    return False

def order_components_by_adjacency_path(components: list[dict]) -> list[dict] | None:
    if not components:
        return None
    if len(components) == 1:
        return components

    adjacency: dict[int, set[int]] = {index: set() for index in range(len(components))}
    for left_index, left in enumerate(components):
        for right_index in range(left_index + 1, len(components)):
            if adjacent_components(left, components[right_index]):
                adjacency[left_index].add(right_index)
                adjacency[right_index].add(left_index)

    if any(len(neighbors) > 2 for neighbors in adjacency.values()):
        return None

    endpoints = [index for index, neighbors in adjacency.items() if len(neighbors) == 1]
    if len(components) > 1 and len(endpoints) != 2:
        return None

    seen: set[int] = set()
    stack = [0]
    while stack:
        index = stack.pop()
        if index in seen:
            continue
        seen.add(index)
        stack.extend(adjacency[index] - seen)
    if len(seen) != len(components):
        return None

    start = min(endpoints, key=lambda index: component_order_key(components[index]))
    ordered_indices: list[int] = []
    previous: int | None = None
    current = start
    while True:
        ordered_indices.append(current)
        next_indices = sorted(
            adjacency[current] - ({previous} if previous is not None else set()),
            key=lambda index: component_order_key(components[index]),
        )
        if not next_indices:
            break
        previous, current = current, next_indices[0]

    if len(ordered_indices) != len(components):
        return None
    return [components[index] for index in ordered_indices]

def panel_shape_ordering_compress(grid: Grid) -> Grid | None:
    components = same_color_components_excluding_background(grid)
    ordered_components = order_components_by_adjacency_path(components)
    if not ordered_components:
        return None
    return [
        [component["color"]]
        for component in ordered_components
        for _ in range(component["size"])
    ]
