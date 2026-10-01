"""旧ARCの入力凡例・穴数対応候補。教師による分岐許可は呼出側で判定する。
出典: ARC-Layer-0-Functional-Compliance@454670a1
arc2_runtime_fit_generator.py の同名純粋関数。密度・線除外heuristicは元のまま。
"""

from __future__ import annotations

from collections import deque

from typing import Any

from .既存物体特徴 import color_components

from .既存領域転写 import normalized_shape_for_cells

Grid = list[list[int]]
Cell = tuple[int, int]
BBox = tuple[int, int, int, int]
ORTHOGONAL_DELTAS = ((-1, 0), (1, 0), (0, -1), (0, 1))

def clone_grid(grid: Grid) -> Grid:
    return [row[:] for row in grid]

def grid_shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0

def bbox_to_list(bbox: BBox) -> list[int]:
    return [bbox[0], bbox[1], bbox[2], bbox[3]]

def component_relative_mask(component: dict[str, Any]) -> set[Cell]:
    return set(normalized_shape_for_cells(component["cells"]))

def component_hole_count(component: dict[str, Any]) -> int:
    row_min, col_min, row_max, col_max = component["bbox"]
    height = row_max - row_min + 1
    width = col_max - col_min + 1
    mask = component_relative_mask(component)
    seen: set[Cell] = set()
    hole_count = 0
    for row in range(height):
        for col in range(width):
            if (row, col) in mask or (row, col) in seen:
                continue
            queue: deque[Cell] = deque([(row, col)])
            seen.add((row, col))
            touches_border = False
            while queue:
                current_row, current_col = queue.popleft()
                if current_row in (0, height - 1) or current_col in (0, width - 1):
                    touches_border = True
                for row_delta, col_delta in ORTHOGONAL_DELTAS:
                    next_row = current_row + row_delta
                    next_col = current_col + col_delta
                    next_cell = (next_row, next_col)
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if next_cell in seen or next_cell in mask:
                        continue
                    seen.add(next_cell)
                    queue.append(next_cell)
            if not touches_border:
                hole_count += 1
    return hole_count

def legend_hole_prototype_components(
    grid: Grid,
    marker_color: int,
    background_color: int,
) -> list[dict[str, Any]]:
    height, width = grid_shape(grid)
    prototypes: list[dict[str, Any]] = []
    for color in sorted({value for row in grid for value in row if value not in {background_color, marker_color}}):
        for component in color_components(grid, color):
            row_min, col_min, row_max, col_max = component["bbox"]
            component_height = row_max - row_min + 1
            component_width = col_max - col_min + 1
            component_area = component_height * component_width
            if component["size"] <= 1 or component_area == 0:
                continue
            density = component["size"] / component_area
            if density < 0.5:
                continue
            if component_height == 1 and component_width > max(10, width // 3):
                continue
            if component_width == 1 and component_height > max(10, height // 3):
                continue
            prototypes.append(
                {
                    "color": color,
                    "bbox": component["bbox"],
                    "size": component["size"],
                    "density": round(density, 6),
                    "hole_count": component_hole_count(component),
                }
            )
    return prototypes

def legend_hole_color_map(prototypes: list[dict[str, Any]]) -> tuple[dict[int, int], list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for prototype in prototypes:
        grouped.setdefault(int(prototype["hole_count"]), []).append(prototype)
    hole_map: dict[int, int] = {}
    conflicts: list[dict[str, Any]] = []
    for hole_count, records in sorted(grouped.items()):
        colors = sorted({int(record["color"]) for record in records})
        if len(colors) == 1:
            hole_map[hole_count] = colors[0]
        else:
            conflicts.append(
                {
                    "hole_count": hole_count,
                    "prototype_colors": colors,
                    "prototype_bboxes": [bbox_to_list(record["bbox"]) for record in records],
                }
            )
    return hole_map, conflicts

def render_legend_hole_count_recolorer(
    grid: Grid,
    marker_color: int,
    background_color: int,
) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}
    marker_components = color_components(grid, marker_color)
    if not marker_components:
        return None, {
            "failure": "no_marker_components",
            "legend_marker_color": marker_color,
            "legend_background_color": background_color,
        }
    prototypes = legend_hole_prototype_components(grid, marker_color, background_color)
    hole_map, conflicts = legend_hole_color_map(prototypes)
    if conflicts:
        return None, {
            "failure": "ambiguous_legend_hole_map",
            "legend_marker_color": marker_color,
            "legend_background_color": background_color,
            "legend_prototype_component_count": len(prototypes),
            "conflicts": conflicts,
        }
    if not hole_map:
        return None, {
            "failure": "empty_legend_hole_map",
            "legend_marker_color": marker_color,
            "legend_background_color": background_color,
            "legend_prototype_component_count": len(prototypes),
        }

    output = clone_grid(grid)
    recolored_components = 0
    removed_components = 0
    recolored_cells = 0
    removed_cells = 0
    component_records: list[dict[str, Any]] = []
    for component in marker_components:
        hole_count = component_hole_count(component)
        target_color = hole_map.get(hole_count, background_color)
        if target_color == background_color:
            removed_components += 1
            removed_cells += component["size"]
        else:
            recolored_components += 1
            recolored_cells += component["size"]
        for row, col in component["cells"]:
            output[row][col] = target_color
        component_records.append(
            {
                "bbox": bbox_to_list(component["bbox"]),
                "size": component["size"],
                "hole_count": hole_count,
                "target_color": target_color,
            }
        )

    if output == grid:
        return None, {"failure": "legend_hole_recolorer_no_change"}
    return output, {
        "renderer_case": "legend_hole_count_recolorer",
        "legend_marker_color": marker_color,
        "legend_background_color": background_color,
        "legend_prototype_component_count": len(prototypes),
        "legend_hole_map_size": len(hole_map),
        "legend_hole_color_map": {str(key): value for key, value in sorted(hole_map.items())},
        "legend_recolored_component_count": recolored_components,
        "legend_removed_component_count": removed_components,
        "legend_recolored_cell_count": recolored_cells,
        "legend_removed_cell_count": removed_cells,
        "component_records": component_records,
    }
