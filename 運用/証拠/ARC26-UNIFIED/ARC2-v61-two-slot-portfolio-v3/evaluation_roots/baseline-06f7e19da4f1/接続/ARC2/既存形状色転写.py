"""旧ARCのtemplate形状・prototype色modeによる背景patch転写prior。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_fit_generator。
6関数は原文のまま。成分record・正規化・格子primitiveは既採用部品を共有。
"""
from __future__ import annotations
from collections import Counter, defaultdict, deque
from typing import Any
from .既存領域転写 import Grid, Cell, BBox, normalized_shape_for_cells
from .既存凡例穴対応 import grid_shape, bbox_to_list, ORTHOGONAL_DELTAS
from .既存物体特徴 import dominant_background_for_grid as dominant_background
from .既存軸反射 import connected_components_for_colors

def cells_to_bbox(cells: list[Cell]) -> BBox:
    return (
        min(row for row, _ in cells),
        min(col for _, col in cells),
        max(row for row, _ in cells),
        max(col for _, col in cells),
    )

def normalize_shape(cells: set[Cell] | list[Cell] | tuple[Cell, ...]) -> tuple[Cell, ...]:
    return normalized_shape_for_cells(cells)

def canonical_shape(shape: tuple[Cell, ...]) -> tuple[Cell, ...]:
    if not shape:
        return tuple()
    height = max(row for row, _ in shape) + 1
    width = max(col for _, col in shape) + 1
    transforms = (
        lambda row, col: (row, col),
        lambda row, col: (col, height - 1 - row),
        lambda row, col: (height - 1 - row, width - 1 - col),
        lambda row, col: (width - 1 - col, row),
        lambda row, col: (row, width - 1 - col),
        lambda row, col: (height - 1 - row, col),
        lambda row, col: (col, row),
        lambda row, col: (width - 1 - col, height - 1 - row),
    )
    return min(normalize_shape([transform(row, col) for row, col in shape]) for transform in transforms)

def connected_cell_groups(cells: set[Cell]) -> list[set[Cell]]:
    seen: set[Cell] = set()
    groups: list[set[Cell]] = []
    for cell in sorted(cells):
        if cell in seen:
            continue
        queue: deque[Cell] = deque([cell])
        seen.add(cell)
        group: set[Cell] = set()
        while queue:
            row, col = queue.popleft()
            group.add((row, col))
            for row_delta, col_delta in ORTHOGONAL_DELTAS:
                next_cell = (row + row_delta, col + col_delta)
                if next_cell not in cells or next_cell in seen:
                    continue
                seen.add(next_cell)
                queue.append(next_cell)
        groups.append(group)
    return groups

def template_hole_component_shape(component: dict[str, Any]) -> tuple[Cell, ...]:
    cells = component.get("cells", [])
    return canonical_shape(normalize_shape(cells))

def render_template_hole_shape_recolorer(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}
    height, width = grid_shape(grid)
    background_color = dominant_background(grid)
    foreground_colors = {value for row in grid for value in row if value != background_color}
    components = connected_components_for_colors(grid, foreground_colors)
    if not components:
        return None, {"failure": "no_template_hole_components"}

    main = max(components, key=lambda component: len(component["cells"]))
    row0, col0, row1, col1 = main["bbox"]
    main_height = row1 - row0 + 1
    main_width = col1 - col0 + 1
    main_area = main_height * main_width
    main_size = len(main["cells"])
    if main_size < 20 or main_area <= main_size or main_area < 25:
        return None, {
            "failure": "template_hole_main_not_surface",
            "main_bbox": bbox_to_list(main["bbox"]),
            "main_size": main_size,
            "main_area": main_area,
        }
    if main_height == height and main_width == width:
        return None, {"failure": "template_hole_main_full_grid", "main_bbox": bbox_to_list(main["bbox"])}

    hole_cells = {
        (row, col)
        for row in range(row0, row1 + 1)
        for col in range(col0, col1 + 1)
        if grid[row][col] == background_color
    }
    holes: list[dict[str, Any]] = []
    for group in connected_cell_groups(hole_cells):
        shape = normalize_shape(group)
        holes.append(
            {
                "cells": group,
                "bbox": cells_to_bbox(sorted(group)),
                "shape": shape,
                "canonical_shape": canonical_shape(shape),
            }
        )
    if len(holes) < 3:
        return None, {"failure": "too_few_template_holes", "hole_count": len(holes)}

    shape_color_counts: dict[tuple[Cell, ...], Counter[int]] = defaultdict(Counter)
    main_cells = set(main["cells"])
    for component in components:
        if set(component["cells"]) == main_cells:
            continue
        shape_color_counts[template_hole_component_shape(component)][int(component["color"])] += 1

    output = [row[col0 : col1 + 1] for row in grid[row0 : row1 + 1]]
    hole_records: list[dict[str, Any]] = []
    filled_cell_count = 0
    unresolved_records: list[dict[str, Any]] = []
    for hole in holes:
        color_counts = shape_color_counts.get(hole["canonical_shape"])
        if not color_counts:
            unresolved_records.append(
                {
                    "bbox": bbox_to_list(hole["bbox"]),
                    "size": len(hole["cells"]),
                    "reason": "missing_external_shape_color",
                }
            )
            continue
        common = color_counts.most_common()
        if len(common) > 1 and common[0][1] == common[1][1]:
            unresolved_records.append(
                {
                    "bbox": bbox_to_list(hole["bbox"]),
                    "size": len(hole["cells"]),
                    "reason": "external_shape_color_tie",
                    "color_counts": dict(sorted(color_counts.items())),
                }
            )
            continue
        fill_color = int(common[0][0])
        for row, col in hole["cells"]:
            output[row - row0][col - col0] = fill_color
            filled_cell_count += 1
        hole_records.append(
            {
                "bbox": bbox_to_list(hole["bbox"]),
                "size": len(hole["cells"]),
                "fill_color": fill_color,
                "external_shape_color_counts": dict(sorted(color_counts.items())),
            }
        )

    if unresolved_records:
        return None, {
            "failure": "unresolved_template_hole_shapes",
            "main_bbox": bbox_to_list(main["bbox"]),
            "unresolved_records": unresolved_records,
        }
    if not hole_records or output == grid:
        return None, {"failure": "empty_or_identity_template_hole_recolor"}

    return output, {
        "renderer_case": "template_hole_shape_recolorer",
        "template_hole_background_color": background_color,
        "template_hole_base_color": int(main["color"]),
        "template_hole_main_bbox": bbox_to_list(main["bbox"]),
        "template_hole_count": len(hole_records),
        "template_hole_shape_count": len({hole["canonical_shape"] for hole in holes}),
        "template_hole_filled_cell_count": filled_cell_count,
        "template_hole_records": hole_records,
    }
