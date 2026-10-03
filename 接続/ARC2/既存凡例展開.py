"""旧top glyph・middle token・bottom paletteの積配置規約。"""
from __future__ import annotations
from typing import Any
from collections import Counter
Grid=list[list[int]]

def _grid_shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0

def _dominant_color(grid: Grid) -> int | None:
    colors = Counter(value for row in grid for value in row)
    if not colors:
        return None
    return min(colors, key=lambda color: (-colors[color], color))

def _legend_token_macro_parse(
    grid: Grid,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    height, width = _grid_shape(grid)
    if height < 6 or width < 6:
        return None, {
            "failure": "legend_token_macro_grid_too_small",
            "legend_token_macro_input_shape": [height, width],
        }
    if any(len(row) != width for row in grid):
        return None, {"failure": "legend_token_macro_ragged_grid"}

    background = _dominant_color(grid)
    if background is None:
        return None, {"failure": "legend_token_macro_missing_background"}

    def non_background_values(values: list[int]) -> list[int]:
        return [int(value) for value in values if int(value) != int(background)]

    separator_row_candidates = []
    for row_index, row in enumerate(grid):
        values = non_background_values(row)
        if values and len(set(values)) == 1 and len(values) >= 2:
            separator_row_candidates.append((row_index, values[0]))
    if not separator_row_candidates:
        return None, {"failure": "legend_token_macro_missing_separator_rows"}
    first_separator_row, separator_color = separator_row_candidates[0]
    second_separator_rows = [
        row_index
        for row_index, color in separator_row_candidates
        if row_index > first_separator_row and color == separator_color
    ]
    if not second_separator_rows:
        return None, {"failure": "legend_token_macro_missing_second_separator"}
    second_separator_row = second_separator_rows[0]
    glyph_size = int(first_separator_row)
    if second_separator_row - first_separator_row - 1 != glyph_size:
        return None, {
            "failure": "legend_token_macro_map_band_size_mismatch",
            "legend_token_macro_glyph_size": glyph_size,
            "legend_token_macro_map_height": second_separator_row - first_separator_row - 1,
        }

    top_rows = range(0, glyph_size)
    separator_columns = []
    for col_index in range(width):
        values = non_background_values(
            [int(grid[row_index][col_index]) for row_index in top_rows]
        )
        if values and len(set(values)) == 1 and values[0] == separator_color:
            separator_columns.append(col_index)

    slot_starts = [
        0,
        width - glyph_size,
        *[col + 1 for col in separator_columns],
        *[col - glyph_size for col in separator_columns],
    ]
    slot_starts = sorted(set(
        start
        for start in slot_starts
        if start + glyph_size <= width
        and any(
            int(grid[row_index][col_index]) != int(background)
            for row_index in top_rows
            for col_index in range(start, start + glyph_size)
        )
        and all(
            int(grid[row_index][col_index]) != int(separator_color)
            for row_index in top_rows
            for col_index in range(start, start + glyph_size)
        )
    ))
    if len(slot_starts) < 2:
        return None, {
            "failure": "legend_token_macro_template_slot_count_too_small",
            "legend_token_macro_slot_starts": slot_starts,
        }

    template_records: list[dict[str, Any]] = []
    for slot_start in slot_starts:
        cells = [
            (row_index, col_index)
            for row_index in top_rows
            for col_index in range(slot_start, slot_start + glyph_size)
            if int(grid[row_index][col_index]) != int(background)
        ]
        colors = sorted({int(grid[row][col]) for row, col in cells})
        if len(colors) != 1:
            return None, {
                "failure": "legend_token_macro_template_color_not_unique",
                "legend_token_macro_slot_start": slot_start,
                "legend_token_macro_colors": colors,
            }
        key_color = int(colors[0])
        pattern = tuple(
            tuple(
                int(grid[row_index][slot_start + col_index])
                if int(grid[row_index][slot_start + col_index]) != int(background)
                else int(background)
                for col_index in range(glyph_size)
            )
            for row_index in top_rows
        )
        template_records.append({
            "slot_start": int(slot_start),
            "key_color": key_color,
            "pattern": pattern,
        })
    key_colors = [int(record["key_color"]) for record in template_records]
    if len(set(key_colors)) != len(key_colors):
        return None, {
            "failure": "legend_token_macro_duplicate_template_colors",
            "legend_token_macro_template_colors": key_colors,
        }

    map_row0 = first_separator_row + 1
    map_records: list[dict[str, Any]] = []
    for slot_start in slot_starts:
        cells = [
            (row_index - map_row0, col_index - slot_start)
            for row_index in range(map_row0, second_separator_row)
            for col_index in range(slot_start, slot_start + glyph_size)
            if int(grid[row_index][col_index]) != int(background)
        ]
        colors = sorted({
            int(grid[map_row0 + row_delta][slot_start + col_delta])
            for row_delta, col_delta in cells
        })
        if not cells or len(colors) != 1 or colors[0] not in set(key_colors):
            return None, {
                "failure": "legend_token_macro_map_slot_invalid",
                "legend_token_macro_slot_start": slot_start,
                "legend_token_macro_map_colors": colors,
                "legend_token_macro_map_cell_count": len(cells),
            }
        map_records.append({
            "slot_start": int(slot_start),
            "token_color": int(colors[0]),
            "cells": tuple(sorted(cells)),
        })
    if {int(record["token_color"]) for record in map_records} != set(key_colors):
        return None, {
            "failure": "legend_token_macro_map_colors_not_bijective",
            "legend_token_macro_map_colors": sorted({
                int(record["token_color"]) for record in map_records
            }),
            "legend_token_macro_template_colors": key_colors,
        }

    marker_candidates = []
    for row_index in range(second_separator_row + 1, height):
        values = []
        marker_row_valid = True
        for slot_start in slot_starts:
            slot_values = [
                int(grid[row_index][col_index])
                for col_index in range(slot_start, slot_start + glyph_size)
                if int(grid[row_index][col_index]) != int(background)
            ]
            if not slot_values or len(set(slot_values)) != 1:
                marker_row_valid = False
                break
            values.append(slot_values[0])
        if not marker_row_valid:
            continue
        marker_candidates.append((row_index, values))
    if len(marker_candidates) != 1:
        return None, {
            "failure": "legend_token_macro_marker_row_not_unique",
            "legend_token_macro_marker_rows": [row for row, _values in marker_candidates],
        }
    marker_row, marker_values = marker_candidates[0]
    output_colors = {
        int(record["key_color"]): int(marker_values[index])
        for index, record in enumerate(template_records)
    }
    if len(set(output_colors.values())) != len(output_colors):
        return None, {
            "failure": "legend_token_macro_marker_colors_not_unique",
            "legend_token_macro_output_colors": output_colors,
        }

    templates = {
        int(record["key_color"]): record["pattern"]
        for record in template_records
    }
    return {
        "background": int(background),
        "separator_color": int(separator_color),
        "glyph_size": glyph_size,
        "template_records": template_records,
        "templates": templates,
        "output_colors": output_colors,
        "map_records": map_records,
        "marker_row": int(marker_row),
        "input_shape": [height, width],
    }, {}

def _legend_token_macro_render(
    grid: Grid,
) -> tuple[Grid | None, dict[str, Any]]:
    policy, rejection = _legend_token_macro_parse(grid)
    if policy is None:
        return None, rejection
    background = int(policy["background"])
    glyph_size = int(policy["glyph_size"])
    output = [
        [background for _ in range(glyph_size * glyph_size)]
        for _ in range(glyph_size * glyph_size)
    ]
    event_count = 0
    placement_records: list[dict[str, Any]] = []
    for map_record in policy["map_records"]:
        token_color = int(map_record["token_color"])
        output_color = int(policy["output_colors"][token_color])
        pattern = policy["templates"][token_color]
        for macro_row, macro_col in map_record["cells"]:
            row0 = int(macro_row) * glyph_size
            col0 = int(macro_col) * glyph_size
            changed = 0
            for row_delta in range(glyph_size):
                for col_delta in range(glyph_size):
                    value = int(pattern[row_delta][col_delta])
                    rendered = output_color if value != background else background
                    if output[row0 + row_delta][col0 + col_delta] != rendered:
                        output[row0 + row_delta][col0 + col_delta] = rendered
                        changed += 1
            event_count += changed
            placement_records.append({
                "token_color": token_color,
                "output_color": output_color,
                "macro_cell": [int(macro_row), int(macro_col)],
                "changed_cell_count": changed,
            })
    if event_count <= 0:
        return None, {"failure": "legend_token_macro_no_effect"}
    return output, {
        "renderer_case": "legend_token_macro_composer",
        "legend_token_macro_background_color": background,
        "legend_token_macro_separator_color": int(policy["separator_color"]),
        "legend_token_macro_glyph_size": glyph_size,
        "legend_token_macro_template_count": len(policy["templates"]),
        "legend_token_macro_map_count": len(policy["map_records"]),
        "legend_token_macro_marker_row": int(policy["marker_row"]),
        "legend_token_macro_output_shape": list(_grid_shape(output)),
        "legend_token_macro_event_count": event_count,
        "legend_token_macro_placement_records": placement_records,
    }
