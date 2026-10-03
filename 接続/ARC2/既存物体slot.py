"""旧物体slot・矩形marker・回廊の23定義を原文で再利用する。"""
from __future__ import annotations
from collections import Counter
from functools import lru_cache
from typing import Any,NamedTuple
from .既存凡例穴対応 import grid_shape,clone_grid,bbox_to_list
from .既存辺対応抽出 import dominant_background
from .既存領域転写 import Grid,GridKey,Cell,BBox,grid_key,bbox_shape_for_bbox
from .既存物体特徴 import _same_color_component_records
ComponentRecord=tuple[int,tuple[Cell,...],BBox,int]

class ComponentFeatureRecord(NamedTuple):
    color: int
    cells: tuple[Cell, ...]
    bbox: BBox
    size: int
    bbox_shape: tuple[int, int]
    bbox_area: int
    normalized_shape: tuple[Cell, ...]
    rows: tuple[int, ...]
    cols: tuple[int, ...]
    axis_kind: str
    is_singleton: bool
    is_solid_rectangle: bool
    is_bbox_perimeter: bool

def normalized_shape_for_cells(cells: set[Cell] | list[Cell] | tuple[Cell, ...]) -> tuple[Cell, ...]:
    if not cells:
        return tuple()
    row_min = min(row for row, _col in cells)
    col_min = min(col for _row, col in cells)
    return tuple(sorted((row - row_min, col - col_min) for row, col in cells))

def _component_feature_record(record: ComponentRecord) -> ComponentFeatureRecord:
    color, cells, bbox, size = record
    height, width = bbox_shape_for_bbox(bbox)
    rows = tuple(sorted({row for row, _col in cells}))
    cols = tuple(sorted({col for _row, col in cells}))
    if size == 1:
        axis_kind = "point"
    elif len(rows) == 1:
        axis_kind = "horizontal"
    elif len(cols) == 1:
        axis_kind = "vertical"
    else:
        axis_kind = "unsupported"
    bbox_area = height * width
    perimeter_size = bbox_area if height == 1 or width == 1 else 2 * height + 2 * width - 4
    return ComponentFeatureRecord(
        color=color,
        cells=cells,
        bbox=bbox,
        size=size,
        bbox_shape=(height, width),
        bbox_area=bbox_area,
        normalized_shape=normalized_shape_for_cells(cells),
        rows=rows,
        cols=cols,
        axis_kind=axis_kind,
        is_singleton=size == 1,
        is_solid_rectangle=size == bbox_area,
        is_bbox_perimeter=size == perimeter_size
        and all(
            row in {bbox[0], bbox[2]} or col in {bbox[1], bbox[3]}
            for row, col in cells
        ),
    )

@lru_cache(maxsize=8192)
def _same_color_component_feature_records(
    key: GridKey,
    color: int,
    include_diagonal: bool,
) -> tuple[ComponentFeatureRecord, ...]:
    return tuple(
        _component_feature_record(record)
        for record in _same_color_component_records(key, color, include_diagonal)
    )

@lru_cache(maxsize=8192)
def _component_feature_records_for_key(
    key: GridKey,
    colors: tuple[int, ...],
    include_diagonal: bool,
) -> tuple[ComponentFeatureRecord, ...]:
    records = tuple(
        record
        for color in colors
        for record in _same_color_component_feature_records(key, color, include_diagonal)
    )
    return tuple(sorted(records, key=lambda record: (record.bbox, record.color, record.size)))

def component_feature_index_for_grid(
    grid: Grid,
    colors: set[int],
    include_diagonal: bool = False,
) -> dict[str, Any]:
    records = _component_feature_records_for_key(
        grid_key(grid),
        tuple(sorted(int(color) for color in colors)),
        bool(include_diagonal),
    )

    def grouped(attribute: str) -> dict[Any, tuple[ComponentFeatureRecord, ...]]:
        groups: dict[Any, list[ComponentFeatureRecord]] = {}
        for record in records:
            groups.setdefault(getattr(record, attribute), []).append(record)
        return {key: tuple(value) for key, value in groups.items()}

    return {
        "records": records,
        "scan_order_records": tuple(sorted(records, key=lambda record: record.cells[0])),
        "by_color": grouped("color"),
        "by_bbox_shape": grouped("bbox_shape"),
        "by_normalized_shape": grouped("normalized_shape"),
        "by_axis_kind": grouped("axis_kind"),
    }

def connected_component_dict_from_feature_record(
    record: ComponentFeatureRecord,
) -> dict[str, Any]:
    return {
        "color": int(record.color),
        "cells": list(record.cells),
        "bbox": record.bbox,
    }

def aligned_bbox_directions(first: BBox, second: BBox) -> list[str]:
    first_row0, first_col0, first_row1, first_col1 = first
    second_row0, second_col0, second_row1, second_col1 = second
    directions: list[str] = []
    if first_row0 == second_row0 and first_row1 == second_row1:
        if second_col1 < first_col0:
            directions.append("L")
        if second_col0 > first_col1:
            directions.append("R")
    if first_col0 == second_col0 and first_col1 == second_col1:
        if second_row1 < first_row0:
            directions.append("U")
        if second_row0 > first_row1:
            directions.append("D")
    return directions

def object_slot_components_for_color(grid: Grid, color: int) -> list[dict[str, Any]]:
    feature_index = component_feature_index_for_grid(grid, {int(color)}, include_diagonal=True)
    return [
        {
            **connected_component_dict_from_feature_record(record),
            "size": int(record.size),
        }
        for record in feature_index["records"]
    ]

def object_slot_component_shape(component: dict[str, Any]) -> tuple[int, int]:
    return bbox_shape_for_bbox(component["bbox"])

def object_slot_full_rectangle(component: dict[str, Any]) -> bool:
    height, width = object_slot_component_shape(component)
    return int(len(component["cells"])) == height * width

def object_slot_rect_cells(bbox: BBox) -> list[Cell]:
    row0, col0, row1, col1 = bbox
    return [(row, col) for row in range(row0, row1 + 1) for col in range(col0, col1 + 1)]

def object_slot_aligned_directions(slot_bbox: BBox, marker_bbox: BBox) -> list[str]:
    return aligned_bbox_directions(slot_bbox, marker_bbox)

def object_slot_path_cells(slot_bbox: BBox, marker_bbox: BBox, direction: str) -> list[Cell]:
    slot_row0, slot_col0, slot_row1, slot_col1 = slot_bbox
    marker_row0, marker_col0, marker_row1, marker_col1 = marker_bbox
    cells: list[Cell] = []
    if direction == "L":
        for row in range(slot_row0, slot_row1 + 1):
            for col in range(marker_col1 + 1, slot_col0):
                cells.append((row, col))
    elif direction == "R":
        for row in range(slot_row0, slot_row1 + 1):
            for col in range(slot_col1 + 1, marker_col0):
                cells.append((row, col))
    elif direction == "U":
        for row in range(marker_row1 + 1, slot_row0):
            for col in range(slot_col0, slot_col1 + 1):
                cells.append((row, col))
    elif direction == "D":
        for row in range(slot_row1 + 1, marker_row0):
            for col in range(slot_col0, slot_col1 + 1):
                cells.append((row, col))
    return cells

def object_slot_opposite_direction(direction: str) -> str:
    return {"L": "R", "R": "L", "U": "D", "D": "U"}[direction]

def object_slot_perpendicular_directions(direction: str) -> tuple[str, str]:
    if direction in {"L", "R"}:
        return ("U", "D")
    return ("L", "R")

def object_slot_immediate_sides(grid: Grid, slot_bbox: BBox, object_color: int) -> set[str]:
    height, width = grid_shape(grid)
    sides: set[str] = set()
    for row, col in object_slot_rect_cells(slot_bbox):
        for side, (row_delta, col_delta) in {
            "U": (-1, 0),
            "D": (1, 0),
            "L": (0, -1),
            "R": (0, 1),
        }.items():
            next_row = row + row_delta
            next_col = col + col_delta
            if 0 <= next_row < height and 0 <= next_col < width and grid[next_row][next_col] == object_color:
                sides.add(side)
    return sides

def object_slot_enclosure_sides(grid: Grid, slot_bbox: BBox, object_color: int) -> set[str]:
    height, width = grid_shape(grid)
    row0, col0, row1, col1 = slot_bbox
    sides: set[str] = set()
    for row in range(row0, row1 + 1):
        if any(grid[row][col] == object_color for col in range(0, col0)):
            sides.add("L")
        if any(grid[row][col] == object_color for col in range(col1 + 1, width)):
            sides.add("R")
    for col in range(col0, col1 + 1):
        if any(grid[row][col] == object_color for row in range(0, row0)):
            sides.add("U")
        if any(grid[row][col] == object_color for row in range(row1 + 1, height)):
            sides.add("D")
    return sides

def object_slot_supported(grid: Grid, slot_bbox: BBox, object_color: int, direction: str) -> bool:
    immediate_sides = object_slot_immediate_sides(grid, slot_bbox, object_color)
    enclosure_sides = object_slot_enclosure_sides(grid, slot_bbox, object_color)
    opposite = object_slot_opposite_direction(direction)
    if opposite not in immediate_sides or opposite not in enclosure_sides:
        return False
    return all(side in enclosure_sides for side in object_slot_perpendicular_directions(direction))

def object_slot_policy(
    grid: Grid,
    marker_color: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    if height < 3 or width < 3:
        return None, {"failure": "object_slot_invalid_shape", "object_slot_input_shape": [height, width]}
    if any(len(row) != width for row in grid):
        return None, {"failure": "object_slot_ragged_grid"}

    background_color = int(dominant_background(grid))
    input_colors = {int(value) for row in grid for value in row}
    if marker_color not in input_colors:
        return None, {
            "failure": "object_slot_marker_color_missing",
            "object_slot_marker_color": marker_color,
            "object_slot_input_colors": sorted(input_colors),
        }
    object_colors = input_colors - {background_color, marker_color}
    if len(object_colors) != 1:
        return None, {
            "failure": "object_slot_object_color_not_unique",
            "object_slot_background_color": background_color,
            "object_slot_marker_color": marker_color,
            "object_slot_object_colors": sorted(object_colors),
            "object_slot_input_colors": sorted(input_colors),
        }
    object_color = next(iter(object_colors))

    marker_feature_index = component_feature_index_for_grid(grid, {int(marker_color)})
    marker_components = [
        connected_component_dict_from_feature_record(record)
        for record in marker_feature_index["scan_order_records"]
    ]
    if not marker_components:
        return None, {"failure": "object_slot_no_marker_components"}
    rectangular_markers: list[dict[str, Any]] = []
    non_rectangular_marker_count = 0
    for component in marker_components:
        component = dict(component)
        component["size"] = len(component["cells"])
        component["shape"] = object_slot_component_shape(component)
        if object_slot_full_rectangle(component):
            rectangular_markers.append(component)
        else:
            non_rectangular_marker_count += 1
    if non_rectangular_marker_count:
        return None, {
            "failure": "object_slot_non_rectangular_marker_component",
            "object_slot_non_rectangular_marker_count": non_rectangular_marker_count,
        }

    object_components = object_slot_components_for_color(grid, object_color)
    if not object_components:
        return None, {"failure": "object_slot_no_object_components", "object_slot_object_color": object_color}

    candidate_records: list[dict[str, Any]] = []
    for object_index, obj in enumerate(object_components):
        obj_row0, obj_col0, obj_row1, obj_col1 = obj["bbox"]
        for marker_index, marker in enumerate(rectangular_markers):
            marker_height, marker_width = marker["shape"]
            for slot_row0 in range(obj_row0, obj_row1 - marker_height + 2):
                for slot_col0 in range(obj_col0, obj_col1 - marker_width + 2):
                    slot_bbox = (
                        slot_row0,
                        slot_col0,
                        slot_row0 + marker_height - 1,
                        slot_col0 + marker_width - 1,
                    )
                    slot_cells = object_slot_rect_cells(slot_bbox)
                    if any(grid[row][col] != background_color for row, col in slot_cells):
                        continue
                    for direction in object_slot_aligned_directions(slot_bbox, marker["bbox"]):
                        path_cells = object_slot_path_cells(slot_bbox, marker["bbox"], direction)
                        if not path_cells:
                            continue
                        if any(grid[row][col] != background_color for row, col in path_cells):
                            continue
                        if not object_slot_supported(grid, slot_bbox, object_color, direction):
                            continue
                        candidate_records.append(
                            {
                                "object_index": object_index,
                                "marker_index": marker_index,
                                "direction": direction,
                                "object_bbox": obj["bbox"],
                                "marker_bbox": marker["bbox"],
                                "slot_bbox": slot_bbox,
                                "marker_cells": list(marker["cells"]),
                                "slot_cells": slot_cells,
                                "path_cells": path_cells,
                            }
                        )

    if not candidate_records:
        return None, {
            "failure": "object_slot_no_supported_marker_slot_pairs",
            "object_slot_marker_component_count": len(rectangular_markers),
            "object_slot_object_component_count": len(object_components),
        }

    duplicate_objects = [
        object_index
        for object_index, count in Counter(record["object_index"] for record in candidate_records).items()
        if count > 1
    ]
    duplicate_markers = [
        marker_index
        for marker_index, count in Counter(record["marker_index"] for record in candidate_records).items()
        if count > 1
    ]
    if duplicate_objects or duplicate_markers:
        return None, {
            "failure": "object_slot_ambiguous_marker_slot_pairs",
            "object_slot_duplicate_object_indexes": sorted(duplicate_objects),
            "object_slot_duplicate_marker_indexes": sorted(duplicate_markers),
            "object_slot_candidate_count": len(candidate_records),
        }

    return {
        "background_color": background_color,
        "marker_color": marker_color,
        "object_color": object_color,
        "marker_components": rectangular_markers,
        "object_components": object_components,
        "events": candidate_records,
    }, {}

def object_slot_serializable_event(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "object_index": int(record["object_index"]),
        "marker_index": int(record["marker_index"]),
        "direction": record["direction"],
        "object_bbox": bbox_to_list(record["object_bbox"]),
        "marker_bbox": bbox_to_list(record["marker_bbox"]),
        "slot_bbox": bbox_to_list(record["slot_bbox"]),
        "slot_cell_count": len(record["slot_cells"]),
        "path_cell_count": len(record["path_cells"]),
        "marker_cell_count": len(record["marker_cells"]),
    }

def render_object_slot_marker_corridor_projector(
    grid: Grid,
    marker_color: int,
    corridor_color: int,
) -> tuple[Grid | None, dict[str, Any]]:
    policy, rejection = object_slot_policy(grid, marker_color)
    if policy is None:
        return None, rejection

    background_color = int(policy["background_color"])
    object_color = int(policy["object_color"])
    if corridor_color in {background_color, marker_color, object_color}:
        return None, {
            "failure": "object_slot_corridor_color_collides",
            "object_slot_background_color": background_color,
            "object_slot_marker_color": marker_color,
            "object_slot_object_color": object_color,
            "object_slot_corridor_color": corridor_color,
        }

    output = clone_grid(grid)
    for component in policy["marker_components"]:
        for row, col in component["cells"]:
            output[row][col] = background_color

    for event in policy["events"]:
        for row, col in event["slot_cells"]:
            output[row][col] = marker_color
        for row, col in [*event["path_cells"], *event["marker_cells"]]:
            output[row][col] = corridor_color

    height, width = grid_shape(grid)
    changed_cell_count = sum(
        1
        for row in range(height)
        for col in range(width)
        if int(output[row][col]) != int(grid[row][col])
    )
    if changed_cell_count == 0:
        return None, {"failure": "object_slot_no_changed_cells"}

    event_records = [object_slot_serializable_event(event) for event in policy["events"]]
    return output, {
        "renderer_case": "object_slot_marker_corridor_projector",
        "object_slot_background_color": background_color,
        "object_slot_marker_color": marker_color,
        "object_slot_object_color": object_color,
        "object_slot_corridor_color": corridor_color,
        "object_slot_event_count": changed_cell_count,
        "object_slot_changed_cell_count": changed_cell_count,
        "object_slot_pair_count": len(policy["events"]),
        "object_slot_removed_marker_component_count": len(policy["marker_components"]) - len(policy["events"]),
        "object_slot_records": event_records,
        "object_slot_input_shape": [height, width],
        "object_slot_output_shape": [height, width],
    }

def infer_object_slot_marker_corridor_colors(
    train_pairs: list[dict[str, Any]],
) -> tuple[tuple[int, int] | None, dict[str, Any]]:
    if len(train_pairs) < 2:
        return None, {
            "failure": "object_slot_requires_at_least_two_train_pairs",
            "train_pair_count": len(train_pairs),
        }

    input_color_intersection: set[int] | None = None
    new_color_intersection: set[int] | None = None
    background_colors: set[int] = set()
    pair_records: list[dict[str, Any]] = []
    for train_index, pair in enumerate(train_pairs):
        input_grid = pair["input"]
        output_grid = pair["output"]
        if grid_shape(input_grid) != grid_shape(output_grid):
            return None, {
                "failure": "object_slot_requires_same_shape",
                "train_index": train_index,
                "input_shape": grid_shape(input_grid),
                "output_shape": grid_shape(output_grid),
            }
        input_colors = {int(value) for row in input_grid for value in row}
        output_colors = {int(value) for row in output_grid for value in row}
        if len(input_colors) != 3:
            return None, {
                "failure": "object_slot_input_color_count_not_three",
                "train_index": train_index,
                "input_colors": sorted(input_colors),
            }
        new_colors = output_colors - input_colors
        if len(new_colors) != 1:
            return None, {
                "failure": "object_slot_output_new_color_not_unique",
                "train_index": train_index,
                "input_colors": sorted(input_colors),
                "output_colors": sorted(output_colors),
                "new_colors": sorted(new_colors),
            }
        background_color = int(dominant_background(input_grid))
        background_colors.add(background_color)
        input_color_intersection = (
            set(input_colors)
            if input_color_intersection is None
            else input_color_intersection & input_colors
        )
        new_color_intersection = (
            set(new_colors)
            if new_color_intersection is None
            else new_color_intersection & new_colors
        )
        pair_records.append(
            {
                "train_index": train_index,
                "background_color": background_color,
                "input_colors": sorted(input_colors),
                "output_colors": sorted(output_colors),
                "new_colors": sorted(new_colors),
            }
        )

    if not new_color_intersection or len(new_color_intersection) != 1:
        return None, {
            "failure": "object_slot_corridor_color_not_consistent",
            "new_color_intersection": sorted(new_color_intersection or []),
            "pair_records": pair_records,
        }
    corridor_color = next(iter(new_color_intersection))
    marker_candidates = (input_color_intersection or set()) - background_colors - {corridor_color}
    if len(marker_candidates) != 1:
        return None, {
            "failure": "object_slot_marker_color_not_unique",
            "marker_candidates": sorted(marker_candidates),
            "input_color_intersection": sorted(input_color_intersection or []),
            "background_colors": sorted(background_colors),
            "corridor_color": corridor_color,
            "pair_records": pair_records,
        }
    marker_color = next(iter(marker_candidates))
    return (marker_color, corridor_color), {
        "object_slot_background_colors": sorted(background_colors),
        "object_slot_color_inference_records": pair_records,
    }
