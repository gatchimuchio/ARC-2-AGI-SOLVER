"""既存v43のseed到達領域・barrier選択・境界着色。

出典: ARC-Layer-0-Functional-Compliance@454670a13024ccf28dc7e9ed9d8ee256ee6cd365
arc2_l0_agent_compiler_v43_seeded_boundary_recolor.py
Git blob: 2bf77dca8cc3302ad06a378401ce5df02597605f
純粋7関数と近傍定義2つは原文。旧component/ID/reportは除外。
"""
from __future__ import annotations
from collections import Counter,deque
from typing import Iterable
from .既存凡例穴対応 import grid_shape
from .既存対角領域 import is_rectangular
Grid=list[list[int]]

NEIGHBORS_4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

NEIGHBORS_8 = tuple(
    (delta_row, delta_col)
    for delta_row in (-1, 0, 1)
    for delta_col in (-1, 0, 1)
    if delta_row or delta_col
)

def infer_seed_boundary_colors(task: dict) -> dict | None:
    fill_colors: set[int] = set()
    seed_colors: set[int] = set()
    background_colors: set[int] = set()
    barrier_colors: set[int] = set()

    for pair in task["train"]:
        input_grid = pair["input"]
        output_grid = pair["output"]
        if not (is_rectangular(input_grid) and is_rectangular(output_grid)):
            return None
        if grid_shape(input_grid) != grid_shape(output_grid):
            return None

        input_colors = {value for row in input_grid for value in row}
        output_colors = {value for row in output_grid for value in row}
        new_colors = output_colors - input_colors
        if len(new_colors) != 1:
            return None
        fill_color = next(iter(new_colors))

        input_counts = Counter(value for row in input_grid for value in row)
        output_counts = Counter(value for row in output_grid for value in row)
        seeds = [
            color
            for color, count in input_counts.items()
            if count == 1 and output_counts[color] == 1
        ]
        if len(seeds) != 1:
            return None
        seed_color = seeds[0]

        background = input_counts.most_common(1)[0][0]
        remaining = input_colors - {seed_color, background}
        if len(remaining) != 1:
            return None
        barrier_color = next(iter(remaining))

        if fill_color in {seed_color, background, barrier_color}:
            return None

        fill_colors.add(fill_color)
        seed_colors.add(seed_color)
        background_colors.add(background)
        barrier_colors.add(barrier_color)

    if not (
        len(fill_colors) == 1
        and len(seed_colors) == 1
        and len(background_colors) == 1
        and len(barrier_colors) == 1
    ):
        return None

    return {
        "fill": next(iter(fill_colors)),
        "seed": next(iter(seed_colors)),
        "background": next(iter(background_colors)),
        "barrier": next(iter(barrier_colors)),
    }

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

def touches_grid_edge(cells: set[tuple[int, int]], height: int, width: int) -> bool:
    return any(row in (0, height - 1) or col in (0, width - 1) for row, col in cells)

def adjacent_to_region(
    cells: set[tuple[int, int]], region: set[tuple[int, int]], height: int, width: int
) -> bool:
    return any(
        0 <= row + delta_row < height
        and 0 <= col + delta_col < width
        and (row + delta_row, col + delta_col) in region
        for row, col in cells
        for delta_row, delta_col in NEIGHBORS_4
    )

def seeded_boundary_barrier_recolor(
    grid: Grid, colors: dict
) -> tuple[Grid | None, list[dict]]:
    if not is_rectangular(grid):
        return None, []

    height, width = grid_shape(grid)
    fill = colors["fill"]
    seed = colors["seed"]
    background = colors["background"]
    barrier = colors["barrier"]

    seed_cells = [
        (row, col)
        for row in range(height)
        for col in range(width)
        if grid[row][col] == seed
    ]
    if len(seed_cells) != 1:
        return None, []
    seed_row, seed_col = seed_cells[0]

    region_starts = []
    for delta_row, delta_col in NEIGHBORS_4:
        next_row = seed_row + delta_row
        next_col = seed_col + delta_col
        if not (0 <= next_row < height and 0 <= next_col < width):
            continue
        if grid[next_row][next_col] == background:
            region_starts.append((next_row, next_col))
    if not region_starts:
        return None, []

    seed_region = flood_same_color(grid, region_starts, background)
    preserved_barriers: set[tuple[int, int]] = set()
    edge_barriers: set[tuple[int, int]] = set()
    barrier_records: list[dict] = []

    for component in same_color_components(grid, barrier):
        adjacent = adjacent_to_region(component, seed_region, height, width)
        touches_edge = touches_grid_edge(component, height, width)
        bbox = component_bbox(component)
        if adjacent:
            preserved_barriers |= component
            if touches_edge:
                edge_barriers |= component
        barrier_records.append(
            {
                "bbox": list(bbox),
                "size": len(component),
                "adjacent_to_seed_region": adjacent,
                "touches_grid_edge": touches_edge,
                "preserved": adjacent,
                "boundary_source": adjacent and touches_edge,
            }
        )

    fill_cells: set[tuple[int, int]] = set()
    for row, col in seed_region:
        if row in (0, height - 1) or col in (0, width - 1):
            fill_cells.add((row, col))
            continue
        if any(
            0 <= row + delta_row < height
            and 0 <= col + delta_col < width
            and (row + delta_row, col + delta_col) in edge_barriers
            for delta_row, delta_col in NEIGHBORS_8
        ):
            fill_cells.add((row, col))

    output = [[background for _ in range(width)] for _ in range(height)]
    for row, col in preserved_barriers:
        output[row][col] = barrier
    for row, col in fill_cells:
        output[row][col] = fill
    output[seed_row][seed_col] = seed

    record = {
        "colors": dict(colors),
        "seed": [seed_row, seed_col],
        "seed_region_size": len(seed_region),
        "seed_region_bbox": list(component_bbox(seed_region)),
        "preserved_barrier_cell_count": len(preserved_barriers),
        "edge_barrier_cell_count": len(edge_barriers),
        "fill_cell_count": len(fill_cells),
        "barrier_records": barrier_records,
    }
    return output, [record]
