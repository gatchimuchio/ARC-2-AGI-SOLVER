"""旧v93のrun長→周期・近傍run優先を原文ASTのまま再利用する。"""
from __future__ import annotations
from collections import Counter
from typing import Any
import math
from .既存凡例穴対応 import grid_shape, clone_grid
Grid=list[list[int]]

def dominant_background(grid: Grid) -> int:
    return Counter(value for row in grid for value in row).most_common(1)[0][0]

def find_partial_vertical_separator(grid: Grid, background: int) -> tuple[int, int, dict[str, Any]] | None:
    height, width = grid_shape(grid)
    candidates: list[dict[str, Any]] = []
    for col in range(1, width - 1):
        non_background_values = [
            grid[row][col]
            for row in range(height)
            if grid[row][col] != background
        ]
        if not non_background_values or len(set(non_background_values)) != 1:
            continue
        separator_color = non_background_values[0]
        required_rows = [
            row
            for row in range(height)
            if any(grid[row][other_col] != background for other_col in range(width) if other_col != col)
        ]
        if any(grid[row][col] != separator_color for row in required_rows):
            continue
        if len(non_background_values) < max(2, len(required_rows)):
            continue
        candidates.append(
            {
                "col": col,
                "color": separator_color,
                "non_background_count": len(non_background_values),
                "required_row_count": len(required_rows),
            }
        )

    if not candidates:
        return None
    candidates.sort(
        key=lambda candidate: (
            candidate["non_background_count"],
            -abs(candidate["col"] - width // 2),
            -candidate["col"],
        ),
        reverse=True,
    )
    if len(candidates) > 1 and candidates[0]["non_background_count"] == candidates[1]["non_background_count"]:
        return None
    best = candidates[0]
    return best["col"], best["color"], best

def runs_from_separator(code: list[int], background: int, active_side: str) -> list[dict[str, int]]:
    sequence = list(reversed(code)) if active_side == "left" else list(code)
    runs: list[dict[str, int]] = []
    index = 0
    while index < len(sequence):
        if sequence[index] == background:
            index += 1
            continue
        color = sequence[index]
        end = index
        while end < len(sequence) and sequence[end] == color:
            end += 1
        runs.append(
            {
                "color": color,
                "length": end - index,
                "start_distance": index,
                "end_distance": end - 1,
                "priority": len(runs),
            }
        )
        index = end
    return runs

def period_length_for_runs(runs: list[dict[str, int]]) -> int:
    result = 1
    for run in runs:
        result = math.lcm(result, run["length"])
    return result

def superposed_cell_value(runs: list[dict[str, int]], distance: int, background: int) -> int:
    for run in runs:
        if distance % run["length"] == 0:
            return run["color"]
    return background

def render_separator_run_period_superposition(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    background = dominant_background(grid)
    separator = find_partial_vertical_separator(grid, background)
    if separator is None:
        return None, {"failure": "missing_unique_partial_vertical_separator", "background": background}

    separator_col, separator_color, separator_record = separator
    output = clone_grid(grid)
    row_records: list[dict[str, Any]] = []
    for row in range(height):
        left_code = grid[row][:separator_col]
        right_code = grid[row][separator_col + 1 :]
        left_active = any(value != background for value in left_code)
        right_active = any(value != background for value in right_code)
        if left_active and right_active:
            return None, {
                "failure": "both_sides_active",
                "row": row,
                "separator_col": separator_col,
            }
        if not left_active and not right_active:
            continue

        active_side = "left" if left_active else "right"
        active_code = left_code if left_active else right_code
        fill_length = len(right_code) if left_active else len(left_code)
        runs = runs_from_separator(active_code, background, active_side)
        if not runs:
            continue

        before_row = output[row][:]
        if left_active:
            for distance in range(fill_length):
                output[row][separator_col + 1 + distance] = superposed_cell_value(
                    runs,
                    distance,
                    background,
                )
        else:
            for distance in range(fill_length):
                output[row][separator_col - 1 - distance] = superposed_cell_value(
                    runs,
                    distance,
                    background,
                )

        changed_cols = [
            col for col in range(width) if before_row[col] != output[row][col]
        ]
        if changed_cols:
            period_length = period_length_for_runs(runs)
            period_sample = [
                superposed_cell_value(runs, distance, background)
                for distance in range(period_length)
            ]
            row_records.append(
                {
                    "row": row,
                    "active_side": active_side,
                    "active_code": active_code,
                    "fill_length": fill_length,
                    "runs_from_separator": runs,
                    "period_length": period_length,
                    "period_sample_from_separator": period_sample,
                    "changed_cols": changed_cols,
                }
            )

    if not row_records:
        return None, {
            "failure": "no_rows_changed",
            "separator_col": separator_col,
            "separator_color": separator_color,
        }

    return output, {
        "background": background,
        "separator": {
            "col": separator_col,
            "color": separator_color,
            "candidate_record": separator_record,
        },
        "row_records": row_records,
    }
