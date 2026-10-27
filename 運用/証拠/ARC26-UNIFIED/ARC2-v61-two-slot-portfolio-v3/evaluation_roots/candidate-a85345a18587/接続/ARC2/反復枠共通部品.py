"""Exact selected accepted pure helper definitions, with type aliases only."""

from __future__ import annotations

Grid = list[list[int]]

Cell = tuple[int, int]

BBox = tuple[int, int, int, int]

def clone_grid(grid: Grid) -> Grid:
    return [row[:] for row in grid]

def _bbox_for_cells(cells: list[Cell]) -> BBox:
    rows = [row for row, _col in cells]
    cols = [col for _row, col in cells]
    return min(rows), min(cols), max(rows), max(cols)

def lattice_tile_mask(grid: Grid, bbox: BBox, color: int) -> frozenset[Cell]:
    row0, col0, row1, col1 = bbox
    return frozenset(
        (row - row0, col - col0)
        for row in range(row0, row1 + 1)
        for col in range(col0, col1 + 1)
        if int(grid[row][col]) == int(color)
    )

def transform_grid_by_name(grid: Grid, transform_name: str) -> Grid | None:
    if transform_name == "identity":
        return clone_grid(grid)
    if transform_name == "rot90":
        return [list(row) for row in zip(*grid[::-1])]
    if transform_name == "rot180":
        return [row[::-1] for row in grid[::-1]]
    if transform_name == "rot270":
        return [list(row) for row in zip(*grid)][::-1]
    if transform_name == "flip_h":
        return [row[::-1] for row in grid]
    if transform_name == "flip_v":
        return grid[::-1]
    if transform_name == "transpose":
        return [list(row) for row in zip(*grid)]
    if transform_name == "anti_transpose":
        return [list(row) for row in zip(*[row[::-1] for row in grid[::-1]])]
    return None
