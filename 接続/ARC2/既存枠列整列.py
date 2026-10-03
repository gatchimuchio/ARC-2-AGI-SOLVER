"""旧同形枠tileの縦区間制約と左右二列配置の純粋関数。"""
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

def _framed_tile_inventory(
    grid: Grid,
    tile_shape: tuple[int, int],
) -> tuple[int, list[dict[str, Any]]] | tuple[None, dict[str, Any]]:
    height, width = _grid_shape(grid)
    tile_height, tile_width = tile_shape
    if (
        not grid
        or any(len(row) != width for row in grid)
        or tile_height < 3
        or tile_width < 3
        or tile_height > height
        or tile_width > width
    ):
        return None, {"failure": "framed_tile_inventory_invalid_shape"}
    background = _dominant_color(grid)
    if background is None:
        return None, {"failure": "framed_tile_inventory_missing_background"}

    candidates: list[dict[str, Any]] = []
    for row in range(height - tile_height + 1):
        for col in range(width - tile_width + 1):
            border = [
                *grid[row][col : col + tile_width],
                *grid[row + tile_height - 1][col : col + tile_width],
                *[
                    grid[row + offset][col]
                    for offset in range(1, tile_height - 1)
                ],
                *[
                    grid[row + offset][col + tile_width - 1]
                    for offset in range(1, tile_height - 1)
                ],
            ]
            interior = [
                grid[row + row_offset][col + col_offset]
                for row_offset in range(1, tile_height - 1)
                for col_offset in range(1, tile_width - 1)
            ]
            if not border or not interior:
                continue
            if len(set(border)) != 1 or len(set(interior)) != 1:
                continue
            outer_color = int(border[0])
            inner_color = int(interior[0])
            if (
                outer_color == inner_color
                or outer_color == background
                or inner_color == background
            ):
                continue
            candidates.append(
                {
                    "row": row,
                    "col": col,
                    "outer_color": outer_color,
                    "inner_color": inner_color,
                    "cells": {
                        (row + row_offset, col + col_offset)
                        for row_offset in range(tile_height)
                        for col_offset in range(tile_width)
                    },
                }
            )
    if not candidates:
        return None, {"failure": "framed_tile_inventory_no_tiles"}

    occupied: set[tuple[int, int]] = set()
    for tile in candidates:
        cells = set(tile["cells"])
        if occupied.intersection(cells):
            return None, {
                "failure": "framed_tile_inventory_overlapping_tiles",
                "candidate_count": len(candidates),
            }
        occupied.update(cells)
    nonbackground = {
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if int(value) != int(background)
    }
    if occupied != nonbackground:
        return None, {
            "failure": "framed_tile_inventory_uncovered_cells",
            "tile_cell_count": len(occupied),
            "nonbackground_cell_count": len(nonbackground),
        }
    return int(background), candidates

def _framed_tile_lane_assignments(
    tiles: list[dict[str, Any]],
    side: str,
    tile_height: int,
) -> list[int] | None:
    ordered = sorted(tiles, key=lambda tile: (int(tile["row"]), int(tile["col"])))
    lanes: list[int | None] = [None] * len(ordered)
    for left_index, left in enumerate(ordered):
        for right_index in range(left_index + 1, len(ordered)):
            right = ordered[right_index]
            if int(right["row"]) > int(left["row"]) + tile_height - 1:
                continue
            if int(left["col"]) == int(right["col"]):
                return None
            left_lane, right_lane = (
                (0, 1)
                if int(left["col"]) < int(right["col"])
                else (1, 0)
            )
            if side == "R":
                left_lane, right_lane = 1 - left_lane, 1 - right_lane
            for index, lane in (
                (left_index, left_lane),
                (right_index, right_lane),
            ):
                if lanes[index] is not None and lanes[index] != lane:
                    return None
                lanes[index] = lane
    return [0 if lane is None else int(lane) for lane in lanes]

def _framed_tile_group_relinearization_render(
    grid: Grid,
    policy: dict[str, Any],
) -> tuple[Grid | None, dict[str, Any]]:
    shape = policy.get("tile_shape")
    if not isinstance(shape, list) or len(shape) != 2:
        return None, {"failure": "framed_tile_relinearization_missing_tile_shape"}
    tile_height, tile_width = int(shape[0]), int(shape[1])
    if tile_height != tile_width:
        return None, {"failure": "framed_tile_relinearization_requires_square_tiles"}
    parsed, parse_record = _framed_tile_inventory(grid, (tile_height, tile_width))
    if parsed is None:
        return None, parse_record
    background, tiles = parsed, parse_record
    side_by_outer = policy.get("side_by_outer")
    if not isinstance(side_by_outer, dict):
        return None, {"failure": "framed_tile_relinearization_missing_side_map"}
    outer_colors = {int(tile["outer_color"]) for tile in tiles}
    if set(side_by_outer) != {str(color) for color in outer_colors}:
        return None, {
            "failure": "framed_tile_relinearization_unexpected_outer_colors",
            "outer_colors": sorted(outer_colors),
        }
    sides = [str(side_by_outer[str(color)]) for color in sorted(outer_colors)]
    if sorted(sides) != ["L", "R"]:
        return None, {"failure": "framed_tile_relinearization_side_map_not_bipartite"}

    height, width = _grid_shape(grid)
    edge_offset = int(policy.get("lane_edge_offset", 0))
    left_outer_col = edge_offset
    right_outer_col = width - tile_width - edge_offset
    left_inner_col = left_outer_col + tile_width
    right_inner_col = right_outer_col - tile_width
    if (
        left_outer_col < 0
        or left_inner_col + tile_width > width
        or right_inner_col < 0
        or right_outer_col + tile_width > width
        or left_inner_col + tile_width > right_inner_col
    ):
        return None, {"failure": "framed_tile_relinearization_lane_bounds"}

    output = [[int(background) for _ in range(width)] for _ in range(height)]
    event_count = 0
    changed_cell_count = 0
    lane_records: list[dict[str, Any]] = []
    for outer_color in sorted(outer_colors):
        side = str(side_by_outer[str(outer_color)])
        group = sorted(
            [tile for tile in tiles if int(tile["outer_color"]) == outer_color],
            key=lambda tile: (int(tile["row"]), int(tile["col"])),
        )
        lanes = _framed_tile_lane_assignments(group, side, tile_height)
        if lanes is None:
            return None, {
                "failure": "framed_tile_relinearization_lane_constraints_ambiguous",
                "outer_color": outer_color,
            }
        for tile, lane in zip(group, lanes):
            target_col = (
                left_outer_col
                if side == "L" and lane == 0
                else left_inner_col
                if side == "L"
                else right_outer_col
                if lane == 0
                else right_inner_col
            )
            source_row = int(tile["row"])
            source_col = int(tile["col"])
            for row_offset in range(tile_height):
                for col_offset in range(tile_width):
                    value = int(grid[source_row + row_offset][source_col + col_offset])
                    target_row = source_row + row_offset
                    target_cell_col = target_col + col_offset
                    if output[target_row][target_cell_col] != int(background):
                        return None, {
                            "failure": "framed_tile_relinearization_target_collision",
                        }
                    output[target_row][target_cell_col] = value
                    changed_cell_count += value != int(
                        grid[target_row][target_cell_col]
                    )
            event_count += 1
            lane_records.append(
                {
                    "outer_color": outer_color,
                    "inner_color": int(tile["inner_color"]),
                    "source_anchor": [source_row, source_col],
                    "target_anchor": [source_row, target_col],
                    "lane": lane,
                }
            )
    if event_count == 0:
        return None, {"failure": "framed_tile_relinearization_no_events"}
    return output, {
        "renderer_case": "framed_tile_group_relinearization",
        "framed_tile_relinearization_background": int(background),
        "framed_tile_relinearization_tile_shape": [tile_height, tile_width],
        "framed_tile_relinearization_event_count": event_count,
        "framed_tile_relinearization_changed_cell_count": changed_cell_count,
        "framed_tile_relinearization_lane_records": lane_records,
        "framed_tile_relinearization_input_shape": list(_grid_shape(grid)),
        "framed_tile_relinearization_output_shape": list(_grid_shape(output)),
    }

def _framed_tile_group_relinearization_policy(
    train_pairs: list[dict[str, Grid]],
    tile_shape: tuple[int, int],
) -> dict[str, Any] | None:
    tile_height, tile_width = tile_shape
    side_by_outer: dict[str, str] = {}
    edge_offsets: set[int] = set()
    for pair in train_pairs:
        input_parsed, input_record = _framed_tile_inventory(
            pair["input"], tile_shape
        )
        output_parsed, output_record = _framed_tile_inventory(
            pair["output"], tile_shape
        )
        if input_parsed is None or output_parsed is None:
            return None
        input_background, input_tiles = input_parsed, input_record
        output_background, output_tiles = output_parsed, output_record
        if input_background != output_background:
            return None
        if _grid_shape(pair["input"]) != _grid_shape(pair["output"]):
            return None
        input_inventory = sorted(
            (int(tile["outer_color"]), int(tile["inner_color"]))
            for tile in input_tiles
        )
        output_inventory = sorted(
            (int(tile["outer_color"]), int(tile["inner_color"]))
            for tile in output_tiles
        )
        if input_inventory != output_inventory:
            return None
        outer_colors = sorted({int(tile["outer_color"]) for tile in input_tiles})
        if len(outer_colors) != 2:
            return None
        local_sides: dict[str, str] = {}
        for outer_color in outer_colors:
            input_group = sorted(
                [
                    tile
                    for tile in input_tiles
                    if int(tile["outer_color"]) == outer_color
                ],
                key=lambda tile: (int(tile["row"]), int(tile["col"])),
            )
            output_group = sorted(
                [
                    tile
                    for tile in output_tiles
                    if int(tile["outer_color"]) == outer_color
                ],
                key=lambda tile: (int(tile["row"]), int(tile["col"])),
            )
            if len(input_group) != len(output_group):
                return None
            if [
                (int(tile["inner_color"]), int(tile["row"]))
                for tile in input_group
            ] != [
                (int(tile["inner_color"]), int(tile["row"]))
                for tile in output_group
            ]:
                return None
            output_columns = [int(tile["col"]) for tile in output_group]
            if len(set(output_columns)) != 2:
                return None
            output_width = _grid_shape(pair["output"])[1]
            side = "L" if max(output_columns) < output_width / 2 else "R"
            outer_col = min(output_columns) if side == "L" else max(output_columns)
            inner_col = (
                outer_col + tile_width
                if side == "L"
                else outer_col - tile_width
            )
            if set(output_columns) != {outer_col, inner_col}:
                return None
            if side == "L":
                edge_offset = outer_col
            else:
                edge_offset = output_width - tile_width - outer_col
            if edge_offset < 0:
                return None
            edge_offsets.add(edge_offset)
            lanes = _framed_tile_lane_assignments(
                input_group,
                side,
                tile_height,
            )
            if lanes is None:
                return None
            observed_lanes = [
                0 if int(tile["col"]) == outer_col else 1
                for tile in output_group
            ]
            if observed_lanes != lanes:
                return None
            for input_tile, output_tile in zip(input_group, output_group):
                for row_offset in range(tile_height):
                    for col_offset in range(tile_width):
                        if int(
                            pair["input"][
                                int(input_tile["row"]) + row_offset
                            ][int(input_tile["col"]) + col_offset]
                        ) != int(
                            pair["output"][
                                int(output_tile["row"]) + row_offset
                            ][int(output_tile["col"]) + col_offset]
                        ):
                            return None
            local_sides[str(outer_color)] = side
        if sorted(local_sides.values()) != ["L", "R"]:
            return None
        for color, side in local_sides.items():
            if color in side_by_outer and side_by_outer[color] != side:
                return None
            side_by_outer[color] = side
    if len(edge_offsets) != 1:
        return None
    return {
        "grammar": "typed_program_search",
        "program": "framed_tile_group_relinearization",
        "selector": "two_outer_color_groups_with_vertical_overlap_lane_constraints",
        "object_scope": "same_shape_framed_tile_inventory",
        "tile_shape": [tile_height, tile_width],
        "side_by_outer": side_by_outer,
        "lane_edge_offset": next(iter(edge_offsets)),
        "lane_order": "source_column_preserving_outer_to_inner",
        "overlap_mode": "vertical_interval_touch",
        "source_order": "row_then_column",
    }
