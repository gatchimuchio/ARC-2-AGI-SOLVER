"""既存資産の固定辞書と4方向軌道。3関数本体は出典ASTと一致。"""
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

def _legend_guided_turning_corridor_render(
    grid: Grid,
) -> tuple[Grid | None, dict[str, Any]]:
    height, width = _grid_shape(grid)
    control_height = 6
    panel_width = 6
    if (
        height <= control_height
        or width < panel_width * 2
        or width % panel_width != 0
        or any(len(row) != width for row in grid)
    ):
        return None, {"failure": "legend_corridor_requires_top_panel_strip"}

    control = grid[:control_height]
    body = [row[:] for row in grid[control_height:]]
    body_height, body_width = _grid_shape(body)
    guide_candidates = Counter(value for row in control for value in row)
    guide_color = min(guide_candidates, key=lambda color: (-guide_candidates[color], color))
    turn_by_color: dict[int, str] = {}
    panel_records: list[dict[str, Any]] = []
    for panel_start in range(0, width, panel_width):
        panel = [row[panel_start : panel_start + panel_width] for row in control]
        if any(panel[0][col] != guide_color for col in range(panel_width)) or any(
            panel[-1][col] != guide_color for col in range(panel_width)
        ):
            return None, {"failure": "legend_corridor_panel_border_mismatch"}
        if any(panel[row][0] != guide_color or panel[row][-1] != guide_color for row in range(control_height)):
            return None, {"failure": "legend_corridor_panel_side_border_mismatch"}
        marker_cells = [
            (row, col, int(panel[row][col]))
            for row in range(1, control_height - 1)
            for col in range(1, panel_width - 1)
            if int(panel[row][col]) != 0
        ]
        marker_colors = {color for _row, _col, color in marker_cells}
        marker_columns = {col for _row, col, _color in marker_cells}
        if len(marker_colors) != 1 or len(marker_columns) != 1 or len(marker_cells) != 4:
            return None, {"failure": "legend_corridor_marker_not_single_vertical_bar"}
        marker_color = next(iter(marker_colors))
        marker_column = next(iter(marker_columns))
        if marker_column not in (1, panel_width - 2) or marker_color == guide_color:
            return None, {"failure": "legend_corridor_marker_side_ambiguous"}
        if marker_color in turn_by_color:
            return None, {"failure": "legend_corridor_duplicate_marker_color"}
        turn_by_color[marker_color] = "left" if marker_column == 1 else "right"
        panel_records.append(
            {
                "panel_start": panel_start,
                "marker_color": marker_color,
                "marker_column": marker_column,
                "turn": turn_by_color[marker_color],
            }
        )

    background = _dominant_color(body)
    if background is None:
        return None, {"failure": "legend_corridor_missing_body_background"}
    body_cells = {
        (row, col)
        for row in range(body_height)
        for col in range(body_width)
        if int(body[row][col]) != int(background)
    }
    if not body_cells:
        return None, {"failure": "legend_corridor_empty_body"}

    def component_from(start: tuple[int, int], remaining: set[tuple[int, int]]) -> set[tuple[int, int]]:
        component = {start}
        stack = [start]
        while stack:
            row, col = stack.pop()
            for row_delta, col_delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                next_cell = (row + row_delta, col + col_delta)
                if next_cell not in remaining or next_cell in component:
                    continue
                component.add(next_cell)
                stack.append(next_cell)
        return component

    components: list[tuple[int, int, set[tuple[int, int]]]] = []
    for color in sorted({int(body[row][col]) for row, col in body_cells}):
        remaining = {
            (row, col)
            for row, col in body_cells
            if int(body[row][col]) == color
        }
        while remaining:
            start = min(remaining)
            component = component_from(start, remaining)
            remaining.difference_update(component)
            components.append((color, len(component), component))

    seed_records: list[tuple[int, int, int, set[tuple[int, int]]]] = []
    obstacle_cells: dict[tuple[int, int], int] = {}
    for color, size, cells in components:
        rows = [row for row, _col in cells]
        cols = [col for _row, col in cells]
        row0, row1 = min(rows), max(rows)
        col0, col1 = min(cols), max(cols)
        bbox_area = (row1 - row0 + 1) * (col1 - col0 + 1)
        if color not in turn_by_color:
            component_height = row1 - row0 + 1
            component_width = col1 - col0 + 1
            if size == bbox_area and component_height == component_width and component_height >= 2:
                seed_records.append((row0, col0, component_height, cells))
                continue
        if color not in turn_by_color or size != bbox_area:
            return None, {
                "failure": "legend_corridor_body_component_not_keyed_rectangle",
                "component_color": color,
                "component_size": size,
                "component_bbox_area": bbox_area,
            }
        for cell in cells:
            obstacle_cells[cell] = color

    if len(seed_records) != 1:
        return None, {
            "failure": "legend_corridor_seed_not_unique",
            "seed_candidate_count": len(seed_records),
        }
    seed_row, seed_col, seed_height, seed_cells = seed_records[0]
    seed_width = len({col for _row, col in seed_cells})
    seed_color = int(body[seed_row][seed_col])
    if seed_height != seed_width or seed_height < 2:
        return None, {"failure": "legend_corridor_seed_requires_square"}
    if len(obstacle_cells) == 0 or not set(obstacle_cells.values()).issubset(turn_by_color):
        return None, {"failure": "legend_corridor_missing_keyed_obstacles"}

    output = [row[:] for row in body]
    directions = ((-1, 0), (0, 1), (1, 0), (0, -1))
    initial_states = (
        (0, seed_row - seed_height, seed_col),
        (1, seed_row, seed_col + seed_width),
        (2, seed_row + seed_height, seed_col),
        (3, seed_row, seed_col - seed_width),
    )
    beam_event_count = 0
    turn_records: list[dict[str, Any]] = []
    for direction, row, col in initial_states:
        seen_states: set[tuple[int, int, int]] = set()
        for _step in range(body_height * body_width * 4):
            state = (direction, row, col)
            if state in seen_states:
                return None, {"failure": "legend_corridor_beam_cycle"}
            seen_states.add(state)
            if not (
                0 <= row < body_height
                and 0 <= col < body_width
                and row + seed_height <= body_height
                and col + seed_width <= body_width
            ):
                break
            for paint_row in range(row, row + seed_height):
                for paint_col in range(col, col + seed_width):
                    if int(body[paint_row][paint_col]) == int(background):
                        if int(output[paint_row][paint_col]) != seed_color:
                            output[paint_row][paint_col] = seed_color
                            beam_event_count += 1

            row_delta, col_delta = directions[direction]
            next_row = row + row_delta
            next_col = col + col_delta
            if not (
                0 <= next_row < body_height
                and 0 <= next_col < body_width
                and next_row + seed_height <= body_height
                and next_col + seed_width <= body_width
            ):
                break
            hit_colors = {
                obstacle_cells[(hit_row, hit_col)]
                for hit_row in range(next_row, next_row + seed_height)
                for hit_col in range(next_col, next_col + seed_width)
                if (hit_row, hit_col) in obstacle_cells
            }
            if hit_colors:
                if len(hit_colors) != 1:
                    return None, {"failure": "legend_corridor_multi_color_collision"}
                hit_color = next(iter(hit_colors))
                turn = turn_by_color.get(hit_color)
                if turn is None:
                    return None, {"failure": "legend_corridor_collision_without_turn_rule"}
                direction = (direction - 1) % 4 if turn == "left" else (direction + 1) % 4
                turn_records.append(
                    {
                        "hit_color": hit_color,
                        "turn": turn,
                        "row": row,
                        "col": col,
                        "direction_after_turn": direction,
                    }
                )
                continue
            row, col = next_row, next_col
        else:
            return None, {"failure": "legend_corridor_beam_step_limit"}

    if beam_event_count == 0:
        return None, {"failure": "legend_corridor_no_path_events"}
    return output, {
        "renderer_case": "legend_guided_turning_corridor",
        "legend_corridor_guide_color": int(guide_color),
        "legend_corridor_panel_records": panel_records,
        "legend_corridor_background_color": int(background),
        "legend_corridor_seed_color": int(seed_color),
        "legend_corridor_seed_bbox": [seed_row, seed_col, seed_row + seed_height - 1, seed_col + seed_width - 1],
        "legend_corridor_obstacle_colors": sorted(set(obstacle_cells.values())),
        "legend_corridor_turn_records": turn_records,
        "legend_corridor_event_count": int(beam_event_count),
        "legend_corridor_input_shape": [height, width],
        "legend_corridor_output_shape": [body_height, body_width],
    }
