from __future__ import annotations
from collections import Counter, deque
from dataclasses import dataclass
from .既存凡例穴対応 import grid_shape, clone_grid
from .既存対角領域 import is_rectangular
Grid=list[list[int]]

@dataclass(frozen=True)
class CorridorFit:
    flow_color: int
    obstacle_color: int

def colors(grid: Grid) -> set[int]:
    return {cell for row in grid for cell in row}

def background_color(grid: Grid) -> int:
    return Counter(cell for row in grid for cell in row).most_common(1)[0][0]

def gravity_corridor_route(grid: Grid, fit: CorridorFit) -> Grid | None:
    if not is_rectangular(grid):
        return None
    if fit.flow_color not in colors(grid) or fit.obstacle_color not in colors(grid):
        return None

    height, width = grid_shape(grid)
    bg = background_color(grid)
    output = clone_grid(grid)
    active = deque(
        (r, c)
        for r, row in enumerate(grid)
        for c, value in enumerate(row)
        if value == fit.flow_color
    )
    seen = set(active)
    changed = 0

    while active:
        r, c = active.popleft()
        next_r = r + 1
        if next_r >= height:
            continue

        below = output[next_r][c]
        if below == bg:
            output[next_r][c] = fit.flow_color
            changed += 1
            if (next_r, c) not in seen:
                seen.add((next_r, c))
                active.append((next_r, c))
            continue

        if below == fit.flow_color:
            if (next_r, c) not in seen:
                seen.add((next_r, c))
                active.append((next_r, c))
            continue

        if below != fit.obstacle_color:
            continue

        left = right = c
        while left - 1 >= 0 and output[next_r][left - 1] == fit.obstacle_color:
            left -= 1
        while right + 1 < width and output[next_r][right + 1] == fit.obstacle_color:
            right += 1

        for fill_c in range(max(0, left - 1), min(width - 1, right + 1) + 1):
            if output[r][fill_c] == bg:
                output[r][fill_c] = fit.flow_color
                changed += 1
            if output[r][fill_c] == fit.flow_color and (r, fill_c) not in seen:
                seen.add((r, fill_c))
                active.append((r, fill_c))

    if changed == 0:
        return None
    return output
