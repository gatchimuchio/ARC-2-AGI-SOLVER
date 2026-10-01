# 出典: gatchimuchio/ARC-Layer-0-Functional-Compliance
# commit 454670a13024ccf28dc7e9ed9d8ee256ee6cd365
# arc_agi_2_solver/arc2_runtime_program_search.py の純粋関数7個を無改変で抽出。
# 全solver・fit選別器・task識別子によるroutingは移植しない。
from __future__ import annotations
from collections import Counter
from typing import Any
Grid = list[list[int]]

def _grid_shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0

def _dominant_color(grid: Grid) -> int | None:
    colors = Counter(value for row in grid for value in row)
    if not colors:
        return None
    return min(colors, key=lambda color: (-colors[color], color))

def _orthogonal_components(
    cells: set[tuple[int, int]],
) -> list[set[tuple[int, int]]]:
    remaining = set(cells)
    components: list[set[tuple[int, int]]] = []
    while remaining:
        component = {remaining.pop()}
        stack = list(component)
        while stack:
            row, col = stack.pop()
            for neighbor in (
                (row - 1, col),
                (row + 1, col),
                (row, col - 1),
                (row, col + 1),
            ):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components

def _template_hole_pack_output(
    template: Grid,
    source: Grid,
    hole_color: int,
) -> list[Grid]:
    height, width = _grid_shape(template)
    hole_cells = {
        (row, col)
        for row in range(height)
        for col in range(width)
        if int(template[row][col]) == hole_color
    }
    source_cells = {
        (row, col)
        for row in range(len(source))
        for col in range(len(source[0]))
        if int(source[row][col]) != hole_color
    }
    if not hole_cells or not source_cells:
        return []

    pieces: list[dict[str, Any]] = []
    for component in _orthogonal_components(source_cells):
        min_row = min(row for row, _col in component)
        min_col = min(col for _row, col in component)
        normalized = {
            (row - min_row, col - min_col): int(source[row][col])
            for row, col in component
        }
        pieces.append({"cells": set(normalized), "values": normalized})
    if sum(len(piece["cells"]) for piece in pieces) != len(hole_cells):
        return []

    placements: list[list[tuple[set[tuple[int, int]], int, int]]] = []
    for piece in pieces:
        max_row = max(row for row, _col in piece["cells"])
        max_col = max(col for _row, col in piece["cells"])
        piece_placements: list[tuple[set[tuple[int, int]], int, int]] = []
        for row in range(height - max_row):
            for col in range(width - max_col):
                placed = {
                    (row + piece_row, col + piece_col)
                    for piece_row, piece_col in piece["cells"]
                }
                if placed <= hole_cells:
                    piece_placements.append((placed, row, col))
        if not piece_placements:
            return []
        placements.append(piece_placements)

    placements_by_cell: dict[
        tuple[int, int], list[tuple[int, set[tuple[int, int]], int, int]]
    ] = {cell: [] for cell in hole_cells}
    for piece_index, piece_placements in enumerate(placements):
        for placed, row, col in piece_placements:
            for cell in placed:
                placements_by_cell[cell].append(
                    (piece_index, placed, row, col)
                )

    outputs: dict[tuple[tuple[int, ...], ...], Grid] = {}
    used = [False] * len(pieces)
    selected: list[tuple[int, set[tuple[int, int]], int, int]] = []

    def search(remaining: set[tuple[int, int]]) -> None:
        if len(outputs) > 16:
            return
        if not remaining:
            output = [list(row) for row in template]
            for piece_index, _placed, row, col in selected:
                piece = pieces[piece_index]
                for (piece_row, piece_col), value in piece["values"].items():
                    output[row + piece_row][col + piece_col] = value
            key = tuple(tuple(int(value) for value in row) for row in output)
            outputs.setdefault(key, output)
            return

        best_cell = min(
            remaining,
            key=lambda cell: sum(
                1
                for piece_index, placed, _row, _col in placements_by_cell[cell]
                if not used[piece_index] and placed <= remaining
            ),
        )
        for piece_index, placed, row, col in placements_by_cell[best_cell]:
            if used[piece_index] or not placed <= remaining:
                continue
            used[piece_index] = True
            selected.append((piece_index, placed, row, col))
            search(remaining - placed)
            selected.pop()
            used[piece_index] = False

    search(hole_cells)
    return list(outputs.values())

def _template_hole_pack_candidate_details(
    candidate: dict[str, Any],
) -> dict[str, Any]:
    return {
        "split_mode": str(candidate["split_mode"]),
        "template_origin": list(candidate["template_origin"]),
        "template_shape": list(candidate["template_shape"]),
        "source_origin": list(candidate["source_origin"]),
        "source_shape": list(candidate["source_shape"]),
        "template_background": int(candidate["template_background"]),
        "template_hole": int(candidate["template_hole"]),
        "source_piece_count": int(candidate["source_piece_count"]),
        "template_hole_count": int(candidate["template_hole_count"]),
    }

def _template_hole_pack_candidates(
    grid: Grid,
    expected: Grid | None = None,
) -> list[dict[str, Any]]:
    height, width = _grid_shape(grid)
    if not grid or not width or any(len(row) != width for row in grid):
        return []
    expected_shape = _grid_shape(expected) if expected is not None else None
    candidates: list[dict[str, Any]] = []

    split_specs: list[tuple[str, int, int, int, int, int, int]] = []
    for template_width in range(3, width - 2):
        split_specs.append(
            (
                "vertical_template_left",
                0,
                0,
                height,
                template_width,
                0,
                template_width,
            )
        )
        split_specs.append(
            (
                "vertical_template_right",
                0,
                width - template_width,
                height,
                template_width,
                0,
                width - template_width,
            )
        )
    for template_height in range(3, height - 2):
        split_specs.append(
            (
                "horizontal_template_top",
                0,
                0,
                template_height,
                width,
                template_height,
                0,
            )
        )
        split_specs.append(
            (
                "horizontal_template_bottom",
                height - template_height,
                0,
                template_height,
                width,
                0,
                0,
            )
        )

    for (
        split_mode,
        template_row,
        template_col,
        template_height,
        template_width,
        source_row,
        source_col,
    ) in split_specs:
        if expected_shape is not None and (
            template_height,
            template_width,
        ) != expected_shape:
            continue
        if split_mode.startswith("vertical"):
            source_height = height
            source_width = width - template_width
        else:
            source_height = height - template_height
            source_width = width
        if source_height <= 0 or source_width <= 0:
            continue
        template = [
            row[template_col : template_col + template_width]
            for row in grid[template_row : template_row + template_height]
        ]
        source = [
            row[source_col : source_col + source_width]
            for row in grid[source_row : source_row + source_height]
        ]
        template_colors = Counter(
            int(value) for row in template for value in row
        )
        if len(template_colors) != 2:
            continue
        border_values = (
            list(template[0])
            + list(template[-1])
            + [template[row][0] for row in range(1, template_height - 1)]
            + [
                template[row][template_width - 1]
                for row in range(1, template_height - 1)
            ]
        )
        border_colors = Counter(int(value) for value in border_values)
        template_background = max(
            border_colors,
            key=lambda color: (border_colors[color], template_colors[color], -color),
        )
        template_hole = next(
            color for color in template_colors if color != template_background
        )
        source_background = _dominant_color(source)
        if source_background != template_hole:
            continue
        hole_count = sum(
            int(value) == template_hole for row in template for value in row
        )
        output_candidates = _template_hole_pack_output(
            template,
            source,
            int(template_hole),
        )
        if not output_candidates:
            continue
        source_piece_count = len(
            _orthogonal_components(
                {
                    (row, col)
                    for row in range(source_height)
                    for col in range(source_width)
                    if int(source[row][col]) != template_hole
                }
            )
        )
        for output in output_candidates:
            if expected is not None and output != expected:
                continue
            candidates.append(
                {
                    "output": output,
                    "split_mode": split_mode,
                    "template_origin": (template_row, template_col),
                    "template_shape": (template_height, template_width),
                    "source_origin": (source_row, source_col),
                    "source_shape": (source_height, source_width),
                    "template_background": template_background,
                    "template_hole": template_hole,
                    "source_piece_count": source_piece_count,
                    "template_hole_count": hole_count,
                }
            )

    unique: dict[tuple[tuple[int, ...], ...], dict[str, Any]] = {}
    for candidate in candidates:
        key = tuple(tuple(int(value) for value in row) for row in candidate["output"])
        unique.setdefault(key, candidate)
    return list(unique.values())

def _template_hole_pack_render(
    grid: Grid,
    _policy: dict[str, Any],
) -> tuple[Grid | None, dict[str, Any]]:
    candidates = _template_hole_pack_candidates(grid)
    if len(candidates) != 1:
        return None, {
            "failure": "template_hole_pack_candidate_count",
            "candidate_count": len(candidates),
            "candidate_details": [
                _template_hole_pack_candidate_details(candidate)
                for candidate in candidates[:8]
            ],
        }
    candidate = candidates[0]
    return candidate["output"], {
        "event_count": int(candidate["source_piece_count"]),
        "renderer_case": "template_hole_polyomino_packing",
        **_template_hole_pack_candidate_details(candidate),
    }
