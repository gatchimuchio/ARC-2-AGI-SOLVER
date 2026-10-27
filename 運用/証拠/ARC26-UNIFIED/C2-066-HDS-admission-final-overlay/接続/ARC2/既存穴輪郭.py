"""旧ARCの穴・物体・外側輪郭の固定形態prior。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_fit_generator。
2関数と8近傍定数は原文のまま。その他の共通primitiveは既採用定義を共有。
"""
from __future__ import annotations
from collections import deque
from typing import Any
from .既存凡例穴対応 import Grid, Cell, ORTHOGONAL_DELTAS, clone_grid, grid_shape, bbox_to_list
from .既存物体特徴 import color_components
Direction = tuple[int, int]

EIGHT_DELTAS: tuple[Direction, ...] = tuple(
    (row_delta, col_delta)
    for row_delta in (-1, 0, 1)
    for col_delta in (-1, 0, 1)
    if row_delta != 0 or col_delta != 0
)

def component_background_holes(
    grid: Grid,
    component: dict[str, Any],
    background_color: int,
) -> list[set[Cell]]:
    row_min, col_min, row_max, col_max = component["bbox"]
    component_cells = set(component["cells"])
    seen: set[Cell] = set()
    holes: list[set[Cell]] = []
    for row in range(row_min, row_max + 1):
        for col in range(col_min, col_max + 1):
            cell = (row, col)
            if cell in component_cells or cell in seen or grid[row][col] != background_color:
                continue
            queue: deque[Cell] = deque([cell])
            seen.add(cell)
            cells: set[Cell] = set()
            touches_border = False
            while queue:
                current_row, current_col = queue.popleft()
                current = (current_row, current_col)
                cells.add(current)
                if current_row in (row_min, row_max) or current_col in (col_min, col_max):
                    touches_border = True
                for row_delta, col_delta in ORTHOGONAL_DELTAS:
                    next_row = current_row + row_delta
                    next_col = current_col + col_delta
                    next_cell = (next_row, next_col)
                    if not (row_min <= next_row <= row_max and col_min <= next_col <= col_max):
                        continue
                    if (
                        next_cell in seen
                        or next_cell in component_cells
                        or grid[next_row][next_col] != background_color
                    ):
                        continue
                    seen.add(next_cell)
                    queue.append(next_cell)
            if not touches_border:
                holes.append(cells)
    return holes

def render_binary_object_hole_outline_renderer(
    grid: Grid,
    background_color: int,
    object_color: int,
    border_color: int,
    hole_color: int,
    filled_object_color: int,
) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}
    input_colors = {value for row in grid for value in row}
    if not input_colors <= {background_color, object_color}:
        return None, {
            "failure": "unexpected_input_colors",
            "input_colors": sorted(input_colors),
            "hole_outline_background_color": background_color,
            "hole_outline_object_color": object_color,
        }

    components = color_components(grid, object_color)
    if not components:
        return None, {
            "failure": "no_object_components",
            "hole_outline_background_color": background_color,
            "hole_outline_object_color": object_color,
        }

    height, width = grid_shape(grid)
    output = clone_grid(grid)
    border_cells: set[Cell] = set()
    hole_cells: set[Cell] = set()
    filled_cell_count = 0
    holed_component_count = 0
    component_records: list[dict[str, Any]] = []
    for component in components:
        holes = component_background_holes(grid, component, background_color)
        flat_hole_cells = {cell for cells in holes for cell in cells}
        has_holes = bool(flat_hole_cells)
        if has_holes:
            holed_component_count += 1
            filled_cell_count += component["size"]
        body_color = filled_object_color if has_holes else object_color

        for row, col in component["cells"]:
            output[row][col] = body_color
        for row, col in flat_hole_cells:
            output[row][col] = hole_color
        hole_cells.update(flat_hole_cells)

        component_border_cells: set[Cell] = set()
        for row, col in component["cells"]:
            for row_delta, col_delta in EIGHT_DELTAS:
                next_row = row + row_delta
                next_col = col + col_delta
                if not (0 <= next_row < height and 0 <= next_col < width):
                    continue
                if grid[next_row][next_col] != background_color or output[next_row][next_col] != background_color:
                    continue
                output[next_row][next_col] = border_color
                border_cell = (next_row, next_col)
                border_cells.add(border_cell)
                component_border_cells.add(border_cell)

        component_records.append(
            {
                "bbox": bbox_to_list(component["bbox"]),
                "size": component["size"],
                "hole_count": len(holes),
                "hole_cell_count": len(flat_hole_cells),
                "border_cell_count": len(component_border_cells),
                "filled_body": has_holes,
            }
        )

    if output == grid:
        return None, {"failure": "binary_object_hole_outline_no_change"}
    return output, {
        "renderer_case": "binary_object_hole_outline_renderer",
        "hole_outline_background_color": background_color,
        "hole_outline_object_color": object_color,
        "hole_outline_border_color": border_color,
        "hole_outline_hole_color": hole_color,
        "hole_outline_filled_object_color": filled_object_color,
        "hole_outline_component_count": len(components),
        "hole_outline_holed_component_count": holed_component_count,
        "hole_outline_border_cell_count": len(border_cells),
        "hole_outline_hole_cell_count": len(hole_cells),
        "hole_outline_filled_cell_count": filled_cell_count,
        "component_records": component_records,
    }
