"""既存の行stripe列から距離層square ringへの符号化。"""
from __future__ import annotations
from typing import Any
from .既存凡例穴対応 import grid_shape
Grid=list[list[int]]

def row_stripe_colors(grid: Grid) -> list[int] | None:
    if not grid:
        return None
    widths = {len(row) for row in grid}
    if len(widths) != 1:
        return None
    colors: list[int] = []
    for row in grid:
        row_colors = set(row)
        if len(row_colors) != 1:
            return None
        colors.append(row[0])
    return colors

def render_stripe_sequence_nested_square_frames(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    stripe_colors = row_stripe_colors(grid)
    if stripe_colors is None:
        return None, {"failure": "input_not_horizontal_stripe_sequence"}
    height, width = grid_shape(grid)
    if height < 3 or width < 2:
        return None, {
            "failure": "stripe_sequence_too_small",
            "input_shape": [height, width],
        }
    if stripe_colors[-1] != stripe_colors[-2]:
        return None, {
            "failure": "terminal_center_color_not_duplicated",
            "last_colors": stripe_colors[-2:],
        }

    ring_colors = stripe_colors[:-1]
    output_size = 2 * len(ring_colors)
    if output_size > 30:
        return None, {
            "failure": "nested_square_output_exceeds_arc_grid_limit",
            "output_shape": [output_size, output_size],
        }

    output = [
        [
            ring_colors[min(row, col, output_size - 1 - row, output_size - 1 - col)]
            for col in range(output_size)
        ]
        for row in range(output_size)
    ]
    if output == grid:
        return None, {"failure": "identity_render"}
    return output, {
        "renderer_case": "stripe_sequence_nested_square_frames",
        "input_shape": [height, width],
        "output_shape": [output_size, output_size],
        "ring_count": len(ring_colors),
        "ring_colors": ring_colors,
        "terminal_duplicate_color": stripe_colors[-1],
    }
