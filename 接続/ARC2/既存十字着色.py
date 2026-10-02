from __future__ import annotations
from .既存凡例穴対応 import grid_shape, clone_grid
from .既存対角領域 import is_rectangular
Grid=list[list[int]]

def plus_recolor(grid: Grid, source: int, target: int) -> Grid | None:
    if not is_rectangular(grid):
        return None
    height, width = grid_shape(grid)
    output = clone_grid(grid)
    motif_cells: set[tuple[int, int]] = set()

    for r in range(1, height - 1):
        for c in range(1, width - 1):
            if (
                grid[r][c] == source
                and grid[r - 1][c] == source
                and grid[r + 1][c] == source
                and grid[r][c - 1] == source
                and grid[r][c + 1] == source
            ):
                motif_cells.update(
                    {
                        (r, c),
                        (r - 1, c),
                        (r + 1, c),
                        (r, c - 1),
                        (r, c + 1),
                    }
                )

    if not motif_cells:
        return None

    for r, c in motif_cells:
        output[r][c] = target
    return output
