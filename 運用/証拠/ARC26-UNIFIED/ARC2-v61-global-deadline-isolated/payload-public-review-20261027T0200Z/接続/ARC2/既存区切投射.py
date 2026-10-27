"""旧separator整列・component別行gap投射の5関数。色役割は教師でfitする。"""
from __future__ import annotations
from typing import Any
from .既存凡例穴対応 import clone_grid, grid_shape, bbox_to_list
from .既存辺対応抽出 import dominant_background
from .既存物体特徴 import color_components
Grid=list[list[int]]
Cell=tuple[int,int]
BBox=tuple[int,int,int,int]

def full_height_color_columns(grid: Grid) -> list[dict[str, int]]:
    height, width = grid_shape(grid)
    columns: list[dict[str, int]] = []
    for col in range(width):
        values = {grid[row][col] for row in range(height)}
        if len(values) == 1:
            columns.append({"col": col, "color": values.pop()})
    return columns

def frame_component_summary(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "color": component["color"],
        "bbox": bbox_to_list(component["bbox"]),
        "size": component["size"],
    }

def separator_projection_component_record(component: dict[str, Any], shift_cols: int) -> dict[str, Any]:
    return {
        "bbox": bbox_to_list(component["bbox"]),
        "size": component["size"],
        "shift_cols": shift_cols,
    }

def infer_separator_projection_policy(train_pairs: list[dict[str, Grid]]) -> tuple[dict[str, int] | None, dict[str, Any]]:
    if not train_pairs:
        return None, {"failure": "no_train_pairs"}

    separator_color_sets: list[set[int]] = []
    target_color_sets: list[set[int]] = []
    movable_color_sets: list[set[int]] = []
    records: list[dict[str, Any]] = []
    for train_index, pair in enumerate(train_pairs):
        input_grid = pair["input"]
        output_grid = pair["output"]
        if grid_shape(input_grid) != grid_shape(output_grid):
            return None, {
                "failure": "shape_mismatch",
                "train_index": train_index,
                "input_shape": list(grid_shape(input_grid)),
                "output_shape": list(grid_shape(output_grid)),
            }

        background = dominant_background(input_grid)
        separator_columns = [
            column
            for column in full_height_color_columns(input_grid)
            if column["color"] != background
        ]
        separator_colors = {column["color"] for column in separator_columns}
        if len(separator_columns) != 1 or len(separator_colors) != 1:
            return None, {
                "failure": "separator_column_not_unique",
                "train_index": train_index,
                "separator_columns": separator_columns,
                "background": background,
            }

        input_colors = {value for row in input_grid for value in row}
        output_colors = {value for row in output_grid for value in row}
        new_colors = output_colors - input_colors
        if len(new_colors) != 1:
            return None, {
                "failure": "new_target_color_not_unique",
                "train_index": train_index,
                "new_colors": sorted(new_colors),
            }

        separator_color = next(iter(separator_colors))
        movable_colors = input_colors - {background, separator_color}
        if len(movable_colors) != 1:
            return None, {
                "failure": "movable_color_not_unique",
                "train_index": train_index,
                "movable_colors": sorted(movable_colors),
                "background": background,
                "separator_color": separator_color,
            }

        separator_color_sets.append(separator_colors)
        target_color_sets.append(new_colors)
        movable_color_sets.append(movable_colors)
        records.append(
            {
                "train_index": train_index,
                "background": background,
                "separator_column": separator_columns[0]["col"],
                "separator_color": separator_color,
                "target_color": next(iter(new_colors)),
                "movable_color": next(iter(movable_colors)),
            }
        )

    separator_common = sorted(set.intersection(*separator_color_sets))
    target_common = sorted(set.intersection(*target_color_sets))
    movable_common = sorted(set.intersection(*movable_color_sets))
    if len(separator_common) != 1 or len(target_common) != 1 or len(movable_common) != 1:
        return None, {
            "failure": "train_role_colors_not_unique",
            "separator_common": separator_common,
            "target_common": target_common,
            "movable_common": movable_common,
            "records": records,
        }

    return {
        "separator_color": separator_common[0],
        "target_color": target_common[0],
        "movable_color": movable_common[0],
    }, {"records": records}

def render_separator_aligned_zero_projection(
    grid: Grid,
    separator_color: int,
    movable_color: int,
    target_color: int,
) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}

    height, width = grid_shape(grid)
    background = dominant_background(grid)
    separator_columns = [
        column["col"]
        for column in full_height_color_columns(grid)
        if column["color"] == separator_color
    ]
    if len(separator_columns) != 1:
        return None, {
            "failure": "separator_column_not_unique",
            "separator_color": separator_color,
            "separator_columns": separator_columns,
        }

    separator_col = separator_columns[0]
    components = color_components(grid, movable_color)
    if not components:
        return None, {"failure": "no_movable_components", "movable_color": movable_color}
    if any(component["bbox"][3] >= separator_col for component in components):
        return None, {
            "failure": "movable_component_not_left_of_separator",
            "separator_col": separator_col,
            "components": [frame_component_summary(component) for component in components[:8]],
        }

    output = clone_grid(grid)
    for component in components:
        for row, col in component["cells"]:
            output[row][col] = background

    moved_cells: set[Cell] = set()
    projection_rows: set[int] = set()
    component_records: list[dict[str, Any]] = []
    for component in components:
        _, col0, _, col1 = component["bbox"]
        shift_cols = (separator_col - 1) - col1
        if shift_cols < 0:
            return None, {
                "failure": "negative_shift_to_separator",
                "separator_col": separator_col,
                "component": frame_component_summary(component),
            }
        shifted_cells = {(row, col + shift_cols) for row, col in component["cells"]}
        if any(not (0 <= row < height and 0 <= col < separator_col) for row, col in shifted_cells):
            return None, {
                "failure": "shifted_cell_out_of_bounds_or_crosses_separator",
                "separator_col": separator_col,
                "component": frame_component_summary(component),
            }

        duplicate_cells = moved_cells & shifted_cells
        if duplicate_cells:
            return None, {
                "failure": "shifted_component_collision",
                "duplicate_cells": [list(cell) for cell in sorted(duplicate_cells)[:8]],
            }

        for row, col in shifted_cells:
            if output[row][col] not in {background, movable_color}:
                return None, {
                    "failure": "shifted_cell_collides_with_protected_color",
                    "cell": [row, col],
                    "existing": output[row][col],
                }
            output[row][col] = movable_color
        moved_cells.update(shifted_cells)

        shifted_cols_by_row: dict[int, list[int]] = {}
        for row, col in shifted_cells:
            shifted_cols_by_row.setdefault(row, []).append(col)
        for row, cols in shifted_cols_by_row.items():
            sorted_cols = sorted(cols)
            if separator_col - 1 not in sorted_cols:
                continue
            if sorted_cols == list(range(min(sorted_cols), separator_col)):
                continue
            for col in range(separator_col + 1, width):
                if output[row][col] not in {background, target_color}:
                    return None, {
                        "failure": "projection_collides_with_protected_color",
                        "cell": [row, col],
                        "existing": output[row][col],
                    }
                output[row][col] = target_color
            projection_rows.add(row)

        component_records.append(separator_projection_component_record(component, shift_cols))

    if output == grid:
        return None, {"failure": "identity_render"}

    return output, {
        "renderer_case": "separator_aligned_zero_projection",
        "background": background,
        "separator_color": separator_color,
        "separator_col": separator_col,
        "movable_color": movable_color,
        "target_color": target_color,
        "component_records": component_records,
        "moved_cell_count": len(moved_cells),
        "projection_row_count": len(projection_rows),
    }
