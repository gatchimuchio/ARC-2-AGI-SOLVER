from __future__ import annotations
from typing import Any
from .既存穴充填 import _grid_shape, _dominant_color
Grid=list[list[int]]

def _periodic_marker_band_parse(
    grid: Grid,
    marker_color_hint: int | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    height, width = _grid_shape(grid)
    if height < 5 or width < 5:
        return None, {
            "failure": "periodic_marker_band_grid_too_small",
            "periodic_marker_band_input_shape": [height, width],
        }
    if any(len(row) != width for row in grid):
        return None, {"failure": "periodic_marker_band_ragged_grid"}
    background = _dominant_color(grid)
    if background is None:
        return None, {"failure": "periodic_marker_band_missing_background"}

    boundary_candidates: list[dict[str, Any]] = []
    for row_index in (0, height - 1):
        cells = [
            (col_index, int(grid[row_index][col_index]))
            for col_index in range(width)
            if int(grid[row_index][col_index]) != int(background)
        ]
        if not cells or len({color for _col, color in cells}) != 1:
            continue
        color = int(cells[0][1])
        if marker_color_hint is not None and color != int(marker_color_hint):
            continue
        col0 = min(col for col, _color in cells)
        col1 = max(col for col, _color in cells)
        if len(cells) != col1 - col0 + 1 or col1 - col0 + 1 < 2:
            continue
        boundary_candidates.append({
            "axis": "row",
            "marker_row": int(row_index),
            "marker_color": color,
            "band_col0": int(col0),
            "band_col1": int(col1),
            "direction": 1 if row_index == 0 else -1,
        })
    for col_index in (0, width - 1):
        cells = [
            (row_index, int(grid[row_index][col_index]))
            for row_index in range(height)
            if int(grid[row_index][col_index]) != int(background)
        ]
        if not cells or len({color for _row, color in cells}) != 1:
            continue
        color = int(cells[0][1])
        if marker_color_hint is not None and color != int(marker_color_hint):
            continue
        row0 = min(row for row, _color in cells)
        row1 = max(row for row, _color in cells)
        if len(cells) != row1 - row0 + 1 or row1 - row0 + 1 < 2:
            continue
        boundary_candidates.append({
            "axis": "col",
            "marker_col": int(col_index),
            "marker_color": color,
            "band_row0": int(row0),
            "band_row1": int(row1),
            "direction": 1 if col_index == 0 else -1,
        })
    if len(boundary_candidates) != 1:
        return None, {
            "failure": "periodic_marker_band_boundary_marker_not_unique",
            "periodic_marker_band_candidate_count": len(boundary_candidates),
        }
    return {
        "background": int(background),
        **boundary_candidates[0],
        "input_shape": [height, width],
    }, {}

def _periodic_marker_band_action(
    value: int,
    marker_color: int,
    background: int,
    fill_color: int,
) -> str | None:
    if value == marker_color:
        return "marker"
    if value == background:
        return "background"
    if value == fill_color:
        return "fill"
    return None

def _periodic_marker_band_render(
    grid: Grid,
    policy: dict[str, Any],
) -> tuple[Grid | None, dict[str, Any]]:
    parsed, rejection = _periodic_marker_band_parse(
        grid,
        int(policy["marker_color"]) if policy.get("marker_color") is not None else None,
    )
    if parsed is None:
        return None, rejection
    background = int(parsed["background"])
    marker_color = int(parsed["marker_color"])
    fill_color = int(policy["fill_color"])
    period = int(policy["period"])
    schedule = {
        int(residue): dict(action)
        for residue, action in policy["schedule"].items()
    }
    output = [list(row) for row in grid]
    event_count = 0
    changed_rows: list[dict[str, Any]] = []
    axis = str(parsed["axis"])
    direction = int(parsed["direction"])
    marker_axis_index = int(parsed["marker_row"] if axis == "row" else parsed["marker_col"])
    band_start = int(parsed["band_col0"] if axis == "row" else parsed["band_row0"])
    band_end = int(parsed["band_col1"] if axis == "row" else parsed["band_row1"])
    axis_length = len(grid) if axis == "row" else len(grid[0])
    for axis_index in range(axis_length):
        distance = (axis_index - marker_axis_index) * direction
        if distance < 0:
            continue
        residue = distance % period
        row_action = schedule.get(residue, {"band": "identity", "recolor": False})
        band_action = str(row_action.get("band", "identity"))
        recolor = bool(row_action.get("recolor", False))
        row_changed = 0
        if band_action != "identity":
            band_color = {
                "marker": marker_color,
                "background": background,
                "fill": fill_color,
            }.get(band_action)
            if band_color is None:
                return None, {
                    "failure": "periodic_marker_band_invalid_action",
                    "periodic_marker_band_action": band_action,
                }
            for band_index in range(band_start, band_end + 1):
                row_index, col_index = (
                    (axis_index, band_index) if axis == "row" else (band_index, axis_index)
                )
                if int(output[row_index][col_index]) != int(band_color):
                    output[row_index][col_index] = int(band_color)
                    row_changed += 1
        if recolor:
            for band_index in range(len(grid[0]) if axis == "row" else len(grid)):
                if band_start <= band_index <= band_end:
                    continue
                row_index, col_index = (
                    (axis_index, band_index) if axis == "row" else (band_index, axis_index)
                )
                value = int(grid[row_index][col_index])
                if value == background or value == marker_color:
                    continue
                if int(output[row_index][col_index]) != fill_color:
                    output[row_index][col_index] = fill_color
                    row_changed += 1
        if row_changed:
            changed_rows.append({
                "axis_index": int(axis_index),
                "distance": int(distance),
                "residue": int(residue),
                "band_action": band_action,
                "recolor": recolor,
                "changed_cell_count": int(row_changed),
            })
            event_count += row_changed
    if event_count <= 0:
        return None, {"failure": "periodic_marker_band_no_effect"}
    return output, {
        "renderer_case": "periodic_marker_band_projector",
        "periodic_marker_band_background_color": background,
        "periodic_marker_band_marker_color": marker_color,
        "periodic_marker_band_fill_color": fill_color,
        "periodic_marker_band_axis": axis,
        "periodic_marker_band_marker_axis_index": marker_axis_index,
        "periodic_marker_band_span": [band_start, band_end],
        "periodic_marker_band_period": period,
        "periodic_marker_band_schedule": schedule,
        "periodic_marker_band_event_count": event_count,
        "periodic_marker_band_changed_rows": changed_rows,
    }

def _periodic_marker_band_fit_schedule(
    train_pairs: list[dict[str, Any]],
    fill_color: int,
    period: int,
    marker_color_hint: int | None = None,
) -> dict[int, dict[str, Any]] | None:
    schedule: dict[int, dict[str, Any]] = {}
    for pair in train_pairs:
        parsed, rejection = _periodic_marker_band_parse(
            pair["input"], marker_color_hint
        )
        if parsed is None:
            return None
        if _grid_shape(pair["input"]) != _grid_shape(pair["output"]):
            return None
        background = int(parsed["background"])
        marker_color = int(parsed["marker_color"])
        axis = str(parsed["axis"])
        direction = int(parsed["direction"])
        marker_axis_index = int(
            parsed["marker_row"] if axis == "row" else parsed["marker_col"]
        )
        band_start = int(
            parsed["band_col0"] if axis == "row" else parsed["band_row0"]
        )
        band_end = int(
            parsed["band_col1"] if axis == "row" else parsed["band_row1"]
        )
        axis_length = len(pair["input"]) if axis == "row" else len(pair["input"][0])
        span_length = len(pair["input"][0]) if axis == "row" else len(pair["input"])
        for axis_index in range(axis_length):
            distance = (axis_index - marker_axis_index) * direction
            if distance < 0:
                continue
            residue = distance % period
            output_band = {
                int(
                    pair["output"][axis_index][band_index]
                    if axis == "row"
                    else pair["output"][band_index][axis_index]
                )
                for band_index in range(band_start, band_end + 1)
            }
            if len(output_band) != 1:
                return None
            band_color = next(iter(output_band))
            band_action = _periodic_marker_band_action(
                band_color, marker_color, background, fill_color
            )
            if band_action is None:
                return None
            changed_outside_band = any(
                (
                    int(pair["output"][axis_index][band_index])
                    != int(pair["input"][axis_index][band_index])
                    if axis == "row"
                    else int(pair["output"][band_index][axis_index])
                    != int(pair["input"][band_index][axis_index])
                )
                for band_index in range(span_length)
                if not band_start <= band_index <= band_end
            )
            has_source_outside_band = any(
                (
                    int(pair["input"][axis_index][band_index])
                    if axis == "row"
                    else int(pair["input"][band_index][axis_index])
                ) not in {background, marker_color}
                for band_index in range(span_length)
                if not band_start <= band_index <= band_end
            )
            recolor: bool | None = changed_outside_band if changed_outside_band else (
                False if has_source_outside_band else None
            )
            if changed_outside_band:
                for band_index in range(span_length):
                    if band_start <= band_index <= band_end:
                        continue
                    input_value = int(
                        pair["input"][axis_index][band_index]
                        if axis == "row"
                        else pair["input"][band_index][axis_index]
                    )
                    output_value = int(
                        pair["output"][axis_index][band_index]
                        if axis == "row"
                        else pair["output"][band_index][axis_index]
                    )
                    if input_value == background or input_value == marker_color:
                        if output_value != input_value:
                            return None
                    elif output_value != fill_color:
                        return None
            record = {"band": band_action, "recolor": recolor}
            previous = schedule.get(residue)
            if previous is not None:
                if previous.get("band") != record["band"]:
                    return None
                previous_recolor = previous.get("recolor")
                current_recolor = record.get("recolor")
                if (
                    previous_recolor is not None
                    and current_recolor is not None
                    and previous_recolor != current_recolor
                ):
                    return None
                if previous_recolor is None:
                    previous["recolor"] = current_recolor
                schedule[residue] = previous
            else:
                schedule[residue] = record
    for record in schedule.values():
        if record.get("recolor") is None:
            record["recolor"] = False
    return schedule
