"""旧ARCの標識優先scan・燃料数に従う型付き移動prior。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_program_search。
7関数と近傍定数は原文のまま。wallという変数名は移動/消去背景を指す。
"""
from __future__ import annotations
from typing import Any
from .既存領域転写 import Grid
from .既存穴充填 import _grid_shape

_BARRIER_NEIGHBORS = ((1, 0), (-1, 0), (0, 1), (0, -1))

def _guided_box_components(
    grid: Grid,
    roles: dict[str, int],
) -> list[set[tuple[int, int]]]:
    role_colors = set(roles.values())
    marker_color = int(roles["marker_color"])
    allowed = {
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if int(value) in role_colors
    }
    remaining = set(allowed)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        stack = [start]
        cells = {start}
        while stack:
            row, col = stack.pop()
            for row_delta, col_delta in _BARRIER_NEIGHBORS:
                neighbor = (row + row_delta, col + col_delta)
                if neighbor not in remaining:
                    continue
                remaining.remove(neighbor)
                cells.add(neighbor)
                stack.append(neighbor)
        if any(
            int(grid[row][col]) != marker_color
            for row, col in cells
        ) and any(
            int(grid[row][col]) == marker_color for row, col in cells
        ):
            components.append(cells)
    return components

def _guided_box_side(
    grid: Grid,
    cells: set[tuple[int, int]],
    marker_color: int,
) -> tuple[str, tuple[int, int, int, int], tuple[int, int, int, int]] | None:
    row0 = min(row for row, _ in cells)
    col0 = min(col for _, col in cells)
    row1 = max(row for row, _ in cells)
    col1 = max(col for _, col in cells)
    marker_cells = [
        (row, col)
        for row, col in cells
        if int(grid[row][col]) == marker_color
    ]
    if not marker_cells:
        return None
    marker_row0 = min(row for row, _ in marker_cells)
    marker_col0 = min(col for _, col in marker_cells)
    marker_row1 = max(row for row, _ in marker_cells)
    marker_col1 = max(col for _, col in marker_cells)
    marker_height = marker_row1 - marker_row0 + 1
    marker_width = marker_col1 - marker_col0 + 1
    if marker_width > marker_height:
        side = "U" if marker_row0 - row0 <= row1 - marker_row1 else "D"
    elif marker_height > marker_width:
        side = "L" if marker_col0 - col0 <= col1 - marker_col1 else "R"
    else:
        return None
    return side, (row0, col0, row1, col1), (
        marker_row0,
        marker_col0,
        marker_row1,
        marker_col1,
    )

def _guided_box_fill_key(side: str):
    if side == "U":
        return lambda cell: (cell[0], cell[1])
    if side == "D":
        return lambda cell: (-cell[0], -cell[1])
    if side == "L":
        return lambda cell: (cell[1], -cell[0])
    return lambda cell: (-cell[1], cell[0])

def _guided_box_far_wall(
    grid: Grid,
    bbox: tuple[int, int, int, int],
    marker_bbox: tuple[int, int, int, int],
    side: str,
    roles: dict[str, int],
    wall_color: int,
) -> tuple[int, bool] | None:
    height, width = _grid_shape(grid)
    row0, col0, row1, col1 = bbox
    marker_row0, marker_col0, marker_row1, marker_col1 = marker_bbox
    marker_color = int(roles["marker_color"])
    if side in "LR":
        direction = -1 if side == "L" else 1
        near = marker_col0 if side == "L" else marker_col1
        scan = range(near + direction, -1, -1) if direction < 0 else range(near + direction, width)
        for col in scan:
            if any(int(grid[row][col]) == marker_color for row in range(row0, row1 + 1)):
                return col, False
        for col in scan:
            values = [int(grid[row][col]) for row in range(row0, row1 + 1)]
            if values and all(value == wall_color for value in values):
                return col, True
        return (0 if direction < 0 else width - 1), True
    direction = -1 if side == "U" else 1
    near = marker_row0 if side == "U" else marker_row1
    scan = range(near + direction, -1, -1) if direction < 0 else range(near + direction, height)
    for row in scan:
        if any(int(grid[row][col]) == marker_color for col in range(col0, col1 + 1)):
            return row, False
    for row in scan:
        values = [int(grid[row][col]) for col in range(col0, col1 + 1)]
        if values and all(value == wall_color for value in values):
            return row, True
    return (0 if direction < 0 else height - 1), True

def _guided_box_marker_shape_candidate(grid: Grid, color: int) -> bool:
    cells = {
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if int(value) == color
    }
    while cells:
        start = min(cells)
        cells.remove(start)
        stack = [start]
        component = {start}
        while stack:
            row, col = stack.pop()
            for row_delta, col_delta in _BARRIER_NEIGHBORS:
                neighbor = (row + row_delta, col + col_delta)
                if neighbor not in cells:
                    continue
                cells.remove(neighbor)
                component.add(neighbor)
                stack.append(neighbor)
        row0 = min(row for row, _ in component)
        row1 = max(row for row, _ in component)
        col0 = min(col for _, col in component)
        col1 = max(col for _, col in component)
        height = row1 - row0 + 1
        width = col1 - col0 + 1
        if len(component) >= 2 and max(height, width) >= 2 * min(height, width):
            return True
    return False

def _guided_box_role_candidates(
    train_pairs: list[dict[str, Any]],
) -> list[tuple[int, int, int, int]]:
    input_colors = sorted({
        int(value)
        for pair in train_pairs
        for row in pair["input"]
        for value in row
    })
    marker_sets = [
        {
            color
            for color in input_colors
            if _guided_box_marker_shape_candidate(pair["input"], color)
        }
        for pair in train_pairs
    ]
    if not marker_sets:
        return []
    marker_colors = set.intersection(*marker_sets)
    if not marker_colors:
        marker_colors = set.union(*marker_sets)
    color_deltas = {
        color: [
            sum(int(value) == color for row in pair["output"] for value in row)
            - sum(int(value) == color for row in pair["input"] for value in row)
            for pair in train_pairs
        ]
        for color in input_colors
    }
    stable_colors = [
        color for color, deltas in color_deltas.items()
        if all(delta == 0 for delta in deltas)
    ]
    decreasing_colors = [
        color for color, deltas in color_deltas.items()
        if all(delta <= 0 for delta in deltas) and any(delta < 0 for delta in deltas)
    ]
    increasing_colors = [
        color for color, deltas in color_deltas.items()
        if all(delta >= 0 for delta in deltas) and any(delta > 0 for delta in deltas)
    ]
    if not stable_colors:
        stable_colors = [
            color for color in input_colors
            if color not in marker_colors
        ]
    if not decreasing_colors:
        decreasing_colors = [
            color for color in input_colors
            if color not in marker_colors
        ]
    if not increasing_colors:
        increasing_colors = [
            color for color in input_colors
            if color not in marker_colors
        ]
    candidates = []
    for marker_color in sorted(marker_colors):
        for interior_color in stable_colors:
            for fuel_color in decreasing_colors:
                for filled_color in increasing_colors:
                    if len({marker_color, interior_color, fuel_color, filled_color}) != 4:
                        continue
                    candidates.append((
                        marker_color,
                        interior_color,
                        fuel_color,
                        filled_color,
                    ))
    return candidates

def _guided_box_marker_compaction_render(
    grid: Grid,
    policy: dict[str, Any],
) -> tuple[Grid | None, dict[str, Any]]:
    roles = {
        str(key): int(value)
        for key, value in policy.get("roles", {}).items()
        if isinstance(value, int)
    }
    required_roles = {"marker_color", "interior_color", "fuel_color", "filled_color"}
    if set(roles) != required_roles or len(set(roles.values())) != 4:
        return None, {"failure": "guided_box_missing_unique_roles"}
    wall_candidates = [
        (sum(int(value) == color for row in grid for value in row), color)
        for color in {
            int(value) for row in grid for value in row
        }
        if color not in set(roles.values())
    ]
    if not wall_candidates:
        return None, {"failure": "guided_box_missing_wall_color"}
    wall_color = max(wall_candidates)[1]
    components = _guided_box_components(grid, roles)
    output = [list(row) for row in grid]
    records: list[dict[str, Any]] = []
    moved_components: list[tuple[set[tuple[int, int]], str, int, bool, int]] = []
    for cells in components:
        parsed = _guided_box_side(grid, cells, roles["marker_color"])
        if parsed is None:
            continue
        side, bbox, marker_bbox = parsed
        far_record = _guided_box_far_wall(
            grid, bbox, marker_bbox, side, roles, wall_color
        )
        if far_record is None:
            return None, {"failure": "guided_box_far_wall_not_found"}
        far, far_is_wall = far_record
        marker_row0, marker_col0, marker_row1, marker_col1 = marker_bbox
        near = marker_row0 if side == "U" else marker_row1 if side == "D" else marker_col0 if side == "L" else marker_col1
        distance = abs(far - near)
        fuel = sum(
            int(grid[row][col]) == roles["fuel_color"]
            for row, col in cells
        )
        move = min(distance, fuel)
        moved_components.append((cells, side, move, far_is_wall, far))
        records.append({
            "bbox": list(bbox),
            "side": side,
            "near": int(near),
            "far": int(far),
            "distance": int(distance),
            "fuel_count": int(fuel),
            "move": int(move),
        })
    if not records:
        return None, {"failure": "guided_box_no_box_components"}
    for cells, _side, move, _far_is_wall, _far in moved_components:
        if move <= 0:
            continue
        for row, col in cells:
            output[row][col] = wall_color
    event_count = 0
    for cells, side, move, far_is_wall, far in moved_components:
        if move <= 0:
            continue
        direction = {
            "U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)
        }[side]
        five_cells = sorted(
            [
                (row, col)
                for row, col in cells
                if int(grid[row][col]) == roles["fuel_color"]
            ],
            key=_guided_box_fill_key(side),
        )
        converted = set(five_cells[:move])
        for row, col in sorted(cells):
            target_row = row + direction[0] * move
            target_col = col + direction[1] * move
            if not (0 <= target_row < len(grid) and 0 <= target_col < len(grid[0])):
                continue
            if (
                far_is_wall
                and int(grid[target_row][target_col]) == wall_color
                and int(grid[row][col]) == roles["marker_color"]
                and (
                    (side in "UD" and target_row == far)
                    or (side in "LR" and target_col == far)
                )
            ):
                continue
            current = int(output[target_row][target_col])
            if current not in {wall_color, roles["marker_color"]} and current != int(grid[row][col]):
                return None, {"failure": "guided_box_target_collision"}
            output[target_row][target_col] = (
                roles["filled_color"] if (row, col) in converted else int(grid[row][col])
            )
            event_count += 1
    if event_count == 0:
        return None, {"failure": "guided_box_no_events"}
    return output, {
        "renderer_case": "guided_box_marker_compaction",
        "guided_box_wall_color": int(wall_color),
        "guided_box_event_count": int(event_count),
        "guided_box_component_records": records,
    }
