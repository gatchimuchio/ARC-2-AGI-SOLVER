"""既存v76の空白矩形・配置到達・最遠点演算。

出典: ARC-Layer-0-Functional-Compliance@454670a13024ccf28dc7e9ed9d8ee256ee6cd365
arc2_l0_agent_compiler_v76_farthest_blank_rectangle_relocator.py
Git blob: 36bc4a9e44c5866a75c687e90bc85c3100fc4381
11関数と近傍定義は原文。0は固定blank型、その他の役割色は教師から推定する。
旧component/評価/識別子によるdispatchは含めない。
"""
from __future__ import annotations
from collections import deque
from typing import Any
from .既存凡例穴対応 import grid_shape, clone_grid
Grid=list[list[int]]

NEIGHBORS_4: tuple[tuple[int, int], ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))

def bbox(cells: list[tuple[int, int]]) -> tuple[int, int, int, int]:
    return (
        min(row for row, _ in cells),
        min(col for _, col in cells),
        max(row for row, _ in cells),
        max(col for _, col in cells),
    )

def rect_cells(bounding_box: tuple[int, int, int, int]) -> list[tuple[int, int]]:
    row_min, col_min, row_max, col_max = bounding_box
    return [
        (row, col)
        for row in range(row_min, row_max + 1)
        for col in range(col_min, col_max + 1)
    ]

def rect_cells_from_position(
    position: tuple[int, int],
    height: int,
    width: int,
) -> list[tuple[int, int]]:
    row_min, col_min = position
    return [
        (row, col)
        for row in range(row_min, row_min + height)
        for col in range(col_min, col_min + width)
    ]

def connected_components_4(grid: Grid, color: int) -> list[list[tuple[int, int]]]:
    height, width = grid_shape(grid)
    cells = {
        (row, col)
        for row in range(height)
        for col in range(width)
        if grid[row][col] == color
    }
    components = []
    while cells:
        start = next(iter(cells))
        cells.remove(start)
        stack = [start]
        component = [start]
        while stack:
            row, col = stack.pop()
            for row_delta, col_delta in NEIGHBORS_4:
                neighbor = (row + row_delta, col + col_delta)
                if neighbor in cells:
                    cells.remove(neighbor)
                    stack.append(neighbor)
                    component.append(neighbor)
        components.append(sorted(component))
    return components

def is_rectangle(cells: list[tuple[int, int]]) -> bool:
    return bool(cells) and set(cells) == set(rect_cells(bbox(cells)))

def source_zero_rectangle(grid: Grid) -> tuple[int, int, int, int] | None:
    zero_components = [
        component for component in connected_components_4(grid, 0) if is_rectangle(component)
    ]
    if len(zero_components) != 1:
        return None
    return bbox(zero_components[0])

def train_transition_model(pair: dict[str, Grid]) -> dict[str, Any] | None:
    input_grid = pair["input"]
    output_grid = pair["output"]
    if grid_shape(input_grid) != grid_shape(output_grid):
        return None
    height, width = grid_shape(input_grid)
    filled_zero_cells: list[tuple[int, int]] = []
    new_zero_cells: list[tuple[int, int]] = []
    fill_colors: set[int] = set()
    for row in range(height):
        for col in range(width):
            before = input_grid[row][col]
            after = output_grid[row][col]
            if before == after:
                continue
            if before == 0 and after != 0:
                filled_zero_cells.append((row, col))
                fill_colors.add(after)
            elif before != 0 and after == 0:
                new_zero_cells.append((row, col))
            else:
                return None
    if not filled_zero_cells or not new_zero_cells or len(fill_colors) != 1:
        return None
    if not is_rectangle(filled_zero_cells) or not is_rectangle(new_zero_cells):
        return None
    source_bbox = bbox(filled_zero_cells)
    target_bbox = bbox(new_zero_cells)
    source_shape = (
        source_bbox[2] - source_bbox[0] + 1,
        source_bbox[3] - source_bbox[1] + 1,
    )
    target_shape = (
        target_bbox[2] - target_bbox[0] + 1,
        target_bbox[3] - target_bbox[1] + 1,
    )
    if source_shape != target_shape:
        return None
    return {
        "source_bbox": source_bbox,
        "target_bbox": target_bbox,
        "rectangle_shape": source_shape,
        "fill_color": next(iter(fill_colors)),
    }

def marker_color_candidates(task: dict[str, Any]) -> list[int]:
    possible: set[int] | None = None
    for pair in task["train"]:
        model = train_transition_model(pair)
        if model is None:
            return []
        rect_height, rect_width = model["rectangle_shape"]
        fill_color = model["fill_color"]
        input_grid = pair["input"]
        colors = {value for row in input_grid for value in row if value not in (0, fill_color)}
        candidates: set[int] = set()
        for color in colors:
            for component in connected_components_4(input_grid, color):
                if not is_rectangle(component):
                    continue
                component_bbox = bbox(component)
                if (
                    component_bbox[2] - component_bbox[0] + 1 == rect_height
                    and component_bbox[3] - component_bbox[1] + 1 == rect_width
                ):
                    candidates.add(color)
        possible = candidates if possible is None else possible & candidates
    return sorted(possible or [])

def valid_rectangle_positions(
    grid: Grid,
    rect_height: int,
    rect_width: int,
    allowed_colors: set[int],
) -> set[tuple[int, int]]:
    height, width = grid_shape(grid)
    positions: set[tuple[int, int]] = set()
    for row in range(height - rect_height + 1):
        for col in range(width - rect_width + 1):
            if all(
                grid[cell_row][cell_col] in allowed_colors
                for cell_row, cell_col in rect_cells_from_position((row, col), rect_height, rect_width)
            ):
                positions.add((row, col))
    return positions

def farthest_reachable_position(
    valid_positions: set[tuple[int, int]],
    source: tuple[int, int],
) -> tuple[tuple[int, int] | None, dict[str, Any]]:
    if source not in valid_positions:
        return None, {"failure": "source_position_not_valid"}
    queue = deque([source])
    distances = {source: 0}
    while queue:
        row, col = queue.popleft()
        for neighbor in ((row + 1, col), (row - 1, col), (row, col + 1), (row, col - 1)):
            if neighbor in valid_positions and neighbor not in distances:
                distances[neighbor] = distances[(row, col)] + 1
                queue.append(neighbor)

    if len(distances) < 2:
        return None, {"failure": "no_reachable_relocation_position"}
    farthest_distance = max(distances.values())
    farthest_nodes = sorted(
        position for position, distance in distances.items() if distance == farthest_distance
    )
    if len(farthest_nodes) != 1:
        return None, {
            "failure": "ambiguous_farthest_reachable_position",
            "farthest_distance": farthest_distance,
            "farthest_nodes": [list(node) for node in farthest_nodes],
        }
    return farthest_nodes[0], {
        "component_size": len(distances),
        "farthest_distance": farthest_distance,
        "valid_position_count": len(valid_positions),
    }

def render_farthest_blank_rectangle_relocator(
    grid: Grid,
    fill_color: int,
    marker_color: int,
) -> tuple[Grid | None, dict[str, Any]]:
    source_bbox = source_zero_rectangle(grid)
    if source_bbox is None:
        return None, {"failure": "requires_one_rectangular_zero_component"}
    rect_height = source_bbox[2] - source_bbox[0] + 1
    rect_width = source_bbox[3] - source_bbox[1] + 1
    source_position = (source_bbox[0], source_bbox[1])
    valid_positions = valid_rectangle_positions(
        grid,
        rect_height,
        rect_width,
        {0, fill_color, marker_color},
    )
    target_position, record = farthest_reachable_position(valid_positions, source_position)
    if target_position is None:
        return None, record

    target_bbox = (
        target_position[0],
        target_position[1],
        target_position[0] + rect_height - 1,
        target_position[1] + rect_width - 1,
    )
    output = clone_grid(grid)
    for row, col in rect_cells(source_bbox):
        output[row][col] = fill_color
    for row, col in rect_cells(target_bbox):
        output[row][col] = 0
    if output == grid:
        return None, {"failure": "no_change"}

    return output, {
        "source_bbox": list(source_bbox),
        "target_bbox": list(target_bbox),
        "rectangle_shape": [rect_height, rect_width],
        "fill_color": fill_color,
        "marker_color": marker_color,
        **record,
    }
