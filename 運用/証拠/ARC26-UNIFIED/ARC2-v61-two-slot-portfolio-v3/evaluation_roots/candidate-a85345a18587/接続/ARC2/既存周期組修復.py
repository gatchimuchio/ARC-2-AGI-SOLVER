"""旧ARCのpanel内tuple周期修復をそのまま再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / v39_periodic_tuple_repair。
6関数は原文のまま。周期上限6、形状で決まる軸、元の誤差順序を保つ。
"""
from __future__ import annotations
from collections import Counter
from .既存領域転写 import Grid
from .既存凡例穴対応 import clone_grid, grid_shape
from .既存対角領域 import is_rectangular

def full_separator_lines(grid: Grid) -> dict[int, dict[str, list[int]]]:
    if not is_rectangular(grid):
        return {}
    height, width = grid_shape(grid)
    result: dict[int, dict[str, list[int]]] = {}
    for color in sorted({value for row in grid for value in row}):
        rows = [row for row in range(height) if all(value == color for value in grid[row])]
        cols = [
            col
            for col in range(width)
            if all(grid[row][col] == color for row in range(height))
        ]
        if rows or cols:
            result[color] = {"rows": rows, "cols": cols}
    return result

def framed_panel_bboxes(grid: Grid) -> list[tuple[int, int, int, int, int | None]]:
    if not is_rectangular(grid):
        return []
    height, width = grid_shape(grid)
    bboxes: list[tuple[int, int, int, int, int | None]] = []

    for color, lines in full_separator_lines(grid).items():
        rows = lines["rows"]
        cols = lines["cols"]
        if not (0 in rows and height - 1 in rows and 0 in cols and width - 1 in cols):
            continue
        for row_index in range(len(rows) - 1):
            top = rows[row_index]
            bottom = rows[row_index + 1]
            if bottom - top < 2:
                continue
            for col_index in range(len(cols) - 1):
                left = cols[col_index]
                right = cols[col_index + 1]
                if right - left < 2:
                    continue
                bboxes.append((top, left, bottom, right, color))

    return bboxes or [(0, 0, height - 1, width - 1, None)]

def peel_uniform_borders(
    grid: Grid, bbox: tuple[int, int, int, int, int | None]
) -> tuple[int, int, int, int, list[int]]:
    top, left, bottom, right, _ = bbox
    peeled_colors: list[int] = []
    while bottom - top >= 2 and right - left >= 2:
        perimeter = (
            [grid[top][col] for col in range(left, right + 1)]
            + [grid[bottom][col] for col in range(left, right + 1)]
            + [grid[row][left] for row in range(top, bottom + 1)]
            + [grid[row][right] for row in range(top, bottom + 1)]
        )
        colors = set(perimeter)
        if len(colors) != 1:
            break
        peeled_colors.append(next(iter(colors)))
        top += 1
        left += 1
        bottom -= 1
        right -= 1
    return top, left, bottom, right, peeled_colors

def sequence_cell_mismatch(left: tuple[int, ...], right: tuple[int, ...]) -> int:
    return sum(a != b for a, b in zip(left, right))

def repair_tuple_sequence(
    sequence: list[tuple[int, ...]], max_period: int = 6
) -> tuple[list[tuple[int, ...]], dict]:
    best: tuple[tuple[int, int, int, list[tuple[int, ...]]], list[tuple[int, ...]]] | None = None
    length = len(sequence)
    for period in range(1, min(max_period, length) + 1):
        motif: list[tuple[int, ...]] = []
        for offset in range(period):
            values = [sequence[index] for index in range(offset, length, period)]
            motif.append(Counter(values).most_common(1)[0][0])
        candidate = [motif[index % period] for index in range(length)]
        tuple_mismatch = sum(a != b for a, b in zip(sequence, candidate))
        cell_mismatch = sum(
            sequence_cell_mismatch(a, b) for a, b in zip(sequence, candidate)
        )
        key = (tuple_mismatch, cell_mismatch, period, candidate)
        if best is None or key < best[0]:
            best = (key, motif)

    assert best is not None
    key, motif = best
    tuple_mismatch, cell_mismatch, period, candidate = key
    return candidate, {
        "tuple_mismatch": tuple_mismatch,
        "cell_mismatch": cell_mismatch,
        "period": period,
        "motif": [list(item) for item in motif],
    }

def periodic_panel_tuple_repair(grid: Grid) -> tuple[Grid | None, list[dict]]:
    if not is_rectangular(grid):
        return None, []
    output = clone_grid(grid)
    records: list[dict] = []

    for bbox in framed_panel_bboxes(grid):
        top, left, bottom, right, peeled_colors = peel_uniform_borders(output, bbox)
        height = bottom - top + 1
        width = right - left + 1
        if height <= 0 or width <= 0:
            continue

        if width >= height:
            axis = "columns"
            sequence = [
                tuple(output[row][col] for row in range(top, bottom + 1))
                for col in range(left, right + 1)
            ]
        else:
            axis = "rows"
            sequence = [
                tuple(output[row][col] for col in range(left, right + 1))
                for row in range(top, bottom + 1)
            ]

        repaired, repair_record = repair_tuple_sequence(sequence)
        if repair_record["cell_mismatch"] == 0:
            continue
        if repair_record["tuple_mismatch"] > max(1, len(sequence) // 3):
            continue

        if axis == "columns":
            for col, tuple_values in zip(range(left, right + 1), repaired):
                for row, value in zip(range(top, bottom + 1), tuple_values):
                    output[row][col] = value
        else:
            for row, tuple_values in zip(range(top, bottom + 1), repaired):
                for col, value in zip(range(left, right + 1), tuple_values):
                    output[row][col] = value

        records.append(
            {
                "panel_bbox": list(bbox[:4]),
                "separator_color": bbox[4],
                "peeled_colors": peeled_colors,
                "pattern_area": [top, left, bottom, right],
                "axis": axis,
                **repair_record,
            }
        )

    return output, records
