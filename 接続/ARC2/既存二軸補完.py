"""固定0欠損を教師共有二軸の反射像から補完する旧6関数。"""
from __future__ import annotations
from typing import Any
Grid=list[list[int]]
Cell=tuple[int,int]

def grid_shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0

def clone_grid(grid: Grid) -> Grid:
    return [row[:] for row in grid]

def pair_preserves_nonzero_and_fills_zero(pair: dict[str, Grid]) -> tuple[bool, dict[str, Any]]:
    input_grid = pair["input"]
    output_grid = pair["output"]
    if grid_shape(input_grid) != grid_shape(output_grid):
        return False, {"failure": "shape_mismatch"}
    input_zero_count = 0
    filled_zero_count = 0
    for row_index, row in enumerate(input_grid):
        for col_index, value in enumerate(row):
            output_value = output_grid[row_index][col_index]
            if value == 0:
                input_zero_count += 1
                if output_value != 0:
                    filled_zero_count += 1
                continue
            if output_value != value:
                return False, {
                    "failure": "nonzero_cell_changed",
                    "cell": [row_index, col_index],
                    "input": value,
                    "output": output_value,
                }
    output_zero_count = sum(value == 0 for row in output_grid for value in row)
    if input_zero_count == 0:
        return False, {"failure": "no_zero_mask_cells"}
    if filled_zero_count != input_zero_count or output_zero_count != 0:
        return False, {
            "failure": "zero_mask_not_fully_filled",
            "input_zero_count": input_zero_count,
            "filled_zero_count": filled_zero_count,
            "output_zero_count": output_zero_count,
        }
    return True, {
        "input_zero_count": input_zero_count,
        "filled_zero_count": filled_zero_count,
    }

def mirror_source_values(grid: Grid, row: int, col: int, row_sum: int, col_sum: int) -> list[int]:
    height, width = grid_shape(grid)
    values: list[int] = []
    seen: set[Cell] = set()
    for source_row, source_col in (
        (row_sum - row, col),
        (row, col_sum - col),
        (row_sum - row, col_sum - col),
    ):
        if not (0 <= source_row < height and 0 <= source_col < width):
            continue
        if (source_row, source_col) in seen:
            continue
        seen.add((source_row, source_col))
        value = grid[source_row][source_col]
        if value != 0:
            values.append(value)
    return values

def zero_reflection_axes_for_pair(pair: dict[str, Grid]) -> list[dict[str, Any]]:
    ok, precheck = pair_preserves_nonzero_and_fills_zero(pair)
    if not ok:
        return []
    input_grid = pair["input"]
    output_grid = pair["output"]
    height, width = grid_shape(input_grid)
    axes: list[dict[str, Any]] = []
    for row_sum in range(0, 2 * height - 1):
        for col_sum in range(0, 2 * width - 1):
            resolved_cells: list[dict[str, Any]] = []
            valid = True
            for row_index, row in enumerate(input_grid):
                for col_index, value in enumerate(row):
                    if value != 0:
                        continue
                    source_values = mirror_source_values(input_grid, row_index, col_index, row_sum, col_sum)
                    unique_values = set(source_values)
                    if len(unique_values) != 1:
                        valid = False
                        break
                    resolved_value = next(iter(unique_values))
                    if output_grid[row_index][col_index] != resolved_value:
                        valid = False
                        break
                    resolved_cells.append(
                        {
                            "cell": [row_index, col_index],
                            "color": resolved_value,
                        }
                    )
                if not valid:
                    break
            if valid:
                axes.append(
                    {
                        "row_reflection_sum": row_sum,
                        "col_reflection_sum": col_sum,
                        "filled_zero_count": precheck["filled_zero_count"],
                        "resolved_cell_count": len(resolved_cells),
                    }
                )
    return axes

def render_zero_mask_bidirectional_reflection_fill(
    grid: Grid,
    row_reflection_sum: int,
    col_reflection_sum: int,
) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}
    output = clone_grid(grid)
    filled_cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(grid):
        for col_index, value in enumerate(row):
            if value != 0:
                continue
            source_values = mirror_source_values(
                grid,
                row_index,
                col_index,
                row_reflection_sum,
                col_reflection_sum,
            )
            unique_values = set(source_values)
            if len(unique_values) != 1:
                return None, {
                    "failure": "unresolved_or_conflicting_mirror_sources",
                    "cell": [row_index, col_index],
                    "source_values": source_values,
                    "row_reflection_sum": row_reflection_sum,
                    "col_reflection_sum": col_reflection_sum,
                }
            resolved_value = next(iter(unique_values))
            output[row_index][col_index] = resolved_value
            filled_cells.append({"cell": [row_index, col_index], "color": resolved_value})
    if not filled_cells:
        return None, {"failure": "no_zero_mask_cells"}
    return output, {
        "row_reflection_sum": row_reflection_sum,
        "col_reflection_sum": col_reflection_sum,
        "filled_zero_count": len(filled_cells),
        "resolved_cell_count": len(filled_cells),
    }
