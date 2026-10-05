from __future__ import annotations
from collections import Counter
from typing import Any
from 接続.ARC2.既存凡例穴対応 import grid_shape, clone_grid
Grid=list[list[int]]

def color_counter(grid: Grid) -> Counter[int]:
    return Counter(value for row in grid for value in row)

def dominant_color(grid: Grid) -> int:
    return color_counter(grid).most_common(1)[0][0]

def contiguous_axis_tokens(
    grid: Grid,
    row: int,
    background: int,
    axis_color: int,
) -> list[tuple[int, int, int]]:
    _, width = grid_shape(grid)
    tokens: list[tuple[int, int, int]] = []
    col = 0
    while col < width:
        color = grid[row][col]
        if color in (background, axis_color):
            col += 1
            continue
        col0 = col
        while col + 1 < width and grid[row][col + 1] == color:
            col += 1
        tokens.append((col0, col, color))
        col += 1
    return tokens

def token_footprint_offsets(
    grid: Grid,
    axis_row: int,
    col0: int,
    col1: int,
    color: int,
) -> tuple[int, ...]:
    height, _ = grid_shape(grid)
    offsets: list[int] = []
    row = axis_row
    while row >= 0 and all(grid[row][col] == color for col in range(col0, col1 + 1)):
        offsets.append(row - axis_row)
        row -= 1
    row = axis_row + 1
    while row < height and all(grid[row][col] == color for col in range(col0, col1 + 1)):
        offsets.append(row - axis_row)
        row += 1
    return tuple(sorted(offsets))

def is_contiguous_offset_interval(offsets: tuple[int, ...]) -> bool:
    return list(offsets) == list(range(min(offsets), max(offsets) + 1))

def render_axis_token_footprint_sorter(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    background = dominant_color(grid)
    candidates: list[dict[str, Any]] = []

    for row in range(1, height - 1):
        non_background = [value for value in grid[row] if value != background]
        if len(non_background) < 5:
            continue
        counts = Counter(non_background)
        axis_color, axis_count = max(counts.items(), key=lambda item: (item[1], -item[0]))
        if axis_count < 3:
            continue

        tokens = contiguous_axis_tokens(grid, row, background, axis_color)
        if len(tokens) < 3:
            continue

        footprints: list[tuple[int, ...]] = []
        valid = True
        for col0, col1, color in tokens:
            offsets = token_footprint_offsets(grid, row, col0, col1, color)
            if 0 not in offsets or not is_contiguous_offset_interval(offsets):
                valid = False
                break
            footprints.append(offsets)
        if not valid:
            continue

        sorted_footprints = sorted(footprints, key=lambda offsets: (len(offsets), min(offsets), max(offsets)))
        if sorted_footprints == footprints:
            continue

        output = clone_grid(grid)
        for (col0, col1, color), old_offsets, new_offsets in zip(tokens, footprints, sorted_footprints):
            for offset in old_offsets:
                target_row = row + offset
                for col in range(col0, col1 + 1):
                    output[target_row][col] = background
            for offset in new_offsets:
                target_row = row + offset
                if not (0 <= target_row < height):
                    valid = False
                    break
                for col in range(col0, col1 + 1):
                    if output[target_row][col] not in (background, color):
                        valid = False
                        break
                    output[target_row][col] = color
                if not valid:
                    break
            if not valid:
                break
        if not valid:
            continue

        candidates.append(
            {
                "axis_row": row,
                "axis_color": axis_color,
                "background": background,
                "tokens": [
                    {"col0": col0, "col1": col1, "color": color}
                    for col0, col1, color in tokens
                ],
                "footprint_lengths": [len(offsets) for offsets in footprints],
                "sorted_footprint_lengths": [len(offsets) for offsets in sorted_footprints],
                "shape": [height, width],
                "output": output,
            }
        )

    diagnostic_records = [
        {key: value for key, value in candidate.items() if key != "output"} for candidate in candidates
    ]
    if len(candidates) != 1:
        return None, {
            "background": background,
            "shape": [height, width],
            "candidate_count": len(candidates),
            "candidate_records": diagnostic_records,
        }

    selected = candidates[0]
    output = selected["output"]
    record = {key: value for key, value in selected.items() if key != "output"}
    record["candidate_count"] = 1
    return output, record
