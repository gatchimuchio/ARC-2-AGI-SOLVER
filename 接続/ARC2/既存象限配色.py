"""入力四象限の寸法符号・柄・配色を展開する旧3関数。"""
from __future__ import annotations
from typing import Any
Grid=list[list[int]]

def _grid_shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0

def _window(grid: Grid, origin: tuple[int, int], shape: tuple[int, int]) -> Grid:
    row, col = origin
    height, width = shape
    return [list(values[col : col + width]) for values in grid[row : row + height]]

def _quadrant_template_palette_render(
    grid: Grid,
    _policy: dict[str, Any] | None = None,
) -> tuple[Grid | None, dict[str, Any]]:
    height, width = _grid_shape(grid)
    if height != width or height < 2 or height % 2 != 0:
        return None, {
            "failure": "quadrant_template_palette_requires_even_square_grid",
            "quadrant_template_input_shape": [height, width],
        }

    size = height // 2
    top_left = _window(grid, (0, 0), (size, size))
    top_right = _window(grid, (0, size), (size, size))
    bottom_left = _window(grid, (size, 0), (size, size))
    bottom_right = _window(grid, (size, size), (size, size))
    output_height = sum(value != 0 for row in top_left for value in row)
    output_width = sum(value != 0 for row in top_right for value in row)
    if output_height <= 0 or output_width <= 0:
        return None, {
            "failure": "quadrant_template_palette_missing_output_extent",
            "quadrant_template_output_shape": [output_height, output_width],
        }

    payload_uniform = len({value for row in bottom_left for value in row}) == 1
    template_blank = all(value == 0 for row in bottom_right for value in row)
    output: Grid = []
    for row in range(output_height):
        output_row: list[int] = []
        for col in range(output_width):
            value = bottom_right[row % size][col % size]
            if value == 0:
                if template_blank:
                    value = bottom_left[row % size][col % size]
                elif payload_uniform:
                    value = bottom_left[0][0]
                else:
                    value = bottom_left[(row // size) % size][(col // size) % size]
            output_row.append(int(value))
        output.append(output_row)

    if not output or output == grid:
        return None, {
            "failure": "quadrant_template_palette_no_emission",
            "quadrant_template_output_shape": [output_height, output_width],
        }
    return output, {
        "renderer_case": "quadrant_template_palette_tiler",
        "quadrant_template_size": int(size),
        "quadrant_template_output_shape": [int(output_height), int(output_width)],
        "quadrant_template_payload_mode": (
            "blank_template_payload"
            if template_blank
            else "scalar_palette"
            if payload_uniform
            else "cellwise_payload"
        ),
    }
