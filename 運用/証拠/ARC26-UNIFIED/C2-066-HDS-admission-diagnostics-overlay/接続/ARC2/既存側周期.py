"""v44 の同形key上下周期stripを原文9関数のまま再利用する。
固定のsize>=3、反復>=2、縦向き、最小prefix周期は旧認識・外挿規約。
"""
from __future__ import annotations
from collections import Counter, defaultdict, deque
from typing import Iterable
from .既存凡例穴対応 import clone_grid, grid_shape
from .既存対角領域 import is_rectangular
Grid=list[list[int]]
NEIGHBORS_4=((1,0),(-1,0),(0,1),(0,-1))

def dominant_color(grid: Grid) -> int:
    return Counter(value for row in grid for value in row).most_common(1)[0][0]

def component_bbox(cells: Iterable[tuple[int, int]]) -> tuple[int, int, int, int]:
    cell_list = list(cells)
    rows = [row for row, _ in cell_list]
    cols = [col for _, col in cell_list]
    return min(rows), min(cols), max(rows), max(cols)

def flood_same_color(
    grid: Grid, starts: Iterable[tuple[int, int]], color: int
) -> set[tuple[int, int]]:
    height, width = grid_shape(grid)
    queue = deque(starts)
    seen = set(starts)
    while queue:
        row, col = queue.popleft()
        for delta_row, delta_col in NEIGHBORS_4:
            next_row = row + delta_row
            next_col = col + delta_col
            if not (0 <= next_row < height and 0 <= next_col < width):
                continue
            if (next_row, next_col) in seen:
                continue
            if grid[next_row][next_col] != color:
                continue
            seen.add((next_row, next_col))
            queue.append((next_row, next_col))
    return seen

def same_color_components(grid: Grid, color: int) -> list[set[tuple[int, int]]]:
    if not is_rectangular(grid):
        return []
    height, width = grid_shape(grid)
    seen: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []
    for row in range(height):
        for col in range(width):
            if (row, col) in seen or grid[row][col] != color:
                continue
            cells = flood_same_color(grid, [(row, col)], color)
            seen |= cells
            components.append(cells)
    return components

def normalized_shape(cells: set[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    row0, col0, _, _ = component_bbox(cells)
    return tuple(sorted((row - row0, col - col0) for row, col in cells))

def repeated_shape_groups(
    grid: Grid,
) -> list[tuple[int, tuple[tuple[int, int], ...], list[set[tuple[int, int]]]]]:
    background = dominant_color(grid)
    colors = sorted({value for row in grid for value in row} - {background})
    groups: list[tuple[int, tuple[tuple[int, int], ...], list[set[tuple[int, int]]]]] = []
    for color in colors:
        by_shape: dict[tuple[tuple[int, int], ...], list[set[tuple[int, int]]]] = (
            defaultdict(list)
        )
        for component in same_color_components(grid, color):
            if len(component) < 3:
                continue
            by_shape[normalized_shape(component)].append(component)
        for shape, components in by_shape.items():
            if len(components) < 2:
                continue
            ordered = sorted(components, key=component_bbox)
            groups.append((color, shape, ordered))
    return groups

def minimal_period(
    patterns: list[tuple[int, ...]]
) -> list[tuple[int, ...]]:
    for period in range(1, len(patterns) + 1):
        if all(patterns[index] == patterns[index % period] for index in range(len(patterns))):
            return patterns[:period]
    return patterns

def side_seed_patterns(
    grid: Grid,
    background: int,
    key_color: int,
    component: set[tuple[int, int]],
    side: str,
) -> tuple[list[int], list[tuple[int, ...]]] | None:
    height, _ = grid_shape(grid)
    row0, col0, row1, col1 = component_bbox(component)
    step = -1 if side == "up" else 1
    start_row = row0 - 1 if side == "up" else row1 + 1
    if not (0 <= start_row < height):
        return None

    bbox_cols = list(range(col0, col1 + 1))
    projection_cols = [
        col
        for col in bbox_cols
        if grid[start_row][col] not in {background, key_color}
    ]
    if not projection_cols:
        return None

    expected_projection = list(range(min(projection_cols), max(projection_cols) + 1))
    if projection_cols != expected_projection:
        return None

    seed: list[tuple[int, ...]] = []
    row = start_row
    while 0 <= row < height:
        values: list[int] = []
        valid = True
        for col in projection_cols:
            value = grid[row][col]
            if value in {background, key_color}:
                valid = False
                break
            values.append(value)
        extra = [
            col
            for col in bbox_cols
            if col not in projection_cols and grid[row][col] not in {background, key_color}
        ]
        if not valid or extra:
            break
        seed.append(tuple(values))
        row += step

    if not seed:
        return None
    return projection_cols, minimal_period(seed)

def repeated_shape_vertical_side_periodic_extension(
    grid: Grid,
) -> tuple[Grid | None, list[dict]]:
    if not is_rectangular(grid):
        return None, []

    height, _ = grid_shape(grid)
    background = dominant_color(grid)
    output = clone_grid(grid)
    records: list[dict] = []

    for key_color, shape, components in repeated_shape_groups(grid):
        key_cells = set().union(*components)
        for component in components:
            row0, col0, row1, col1 = component_bbox(component)
            for side in ("up", "down"):
                seed = side_seed_patterns(grid, background, key_color, component, side)
                if seed is None:
                    continue
                projection_cols, period = seed
                rows = (
                    range(row0 - 1, -1, -1)
                    if side == "up"
                    else range(row1 + 1, height)
                )
                local_changed = False
                for index, row in enumerate(rows):
                    pattern = period[index % len(period)]
                    for col, value in zip(projection_cols, pattern):
                        if (row, col) in key_cells:
                            continue
                        if output[row][col] != value:
                            output[row][col] = value
                            local_changed = True
                if local_changed:
                    records.append(
                        {
                            "key_color": key_color,
                            "key_shape_size": len(shape),
                            "side": side,
                            "key_bbox": [row0, col0, row1, col1],
                            "projection_cols": projection_cols,
                            "period": [list(pattern) for pattern in period],
                        }
                    )

    return output, records
