"""既存のmarker反射機構を、現在の成分/範囲primitiveへ接続する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_fit_generator.py。
適格性・反射・記録・描画の4関数は原文のまま。record射影だけを共有部品で実装。
"""
from __future__ import annotations
from typing import Any
from .既存領域転写 import Grid, Cell, BBox
from .既存凡例穴対応 import clone_grid, grid_shape
from .既存物体特徴 import color_components, dominant_background_for_grid as dominant_background
from .既存色群関係 import bbox_relation_for_bboxes

POINT_MARKER_MAX_GAP = 3


def connected_components_for_colors(grid, colors):
    records = [
        {"color": part["color"], "cells": sorted(part["cells"]), "bbox": tuple(part["bbox"])}
        for color in colors for part in color_components(grid, color)
    ]
    return sorted(records, key=lambda part: part["cells"][0])


def marker_axis_components(grid, marker_color):
    records = []
    for part in connected_components_for_colors(grid, {marker_color}):
        rows = {r for r, _ in part["cells"]}
        cols = {c for _, c in part["cells"]}
        kind = ("point" if len(part["cells"]) == 1 else "horizontal" if len(rows) == 1
                else "vertical" if len(cols) == 1 else "unsupported")
        records.append({**part, "rows": rows, "cols": cols, "kind": kind})
    return records


def bbox_gap(first, second):
    relation = bbox_relation_for_bboxes(first, second)
    return relation.chebyshev_gap, relation.manhattan_gap

def eligible_marker_object_pair(
    marker: dict[str, Any],
    obj: dict[str, Any],
) -> bool:
    row0, col0, row1, col1 = obj["bbox"]
    if marker["kind"] == "point":
        return bbox_gap(marker["bbox"], obj["bbox"])[0] <= POINT_MARKER_MAX_GAP
    if marker["kind"] == "horizontal":
        axis_row = next(iter(marker["rows"]))
        min_col = min(marker["cols"])
        max_col = max(marker["cols"])
        return (row1 < axis_row or row0 > axis_row) and col1 >= min_col - 1 and col0 <= max_col + 1
    if marker["kind"] == "vertical":
        axis_col = next(iter(marker["cols"]))
        min_row = min(marker["rows"])
        max_row = max(marker["rows"])
        return (col1 < axis_col or col0 > axis_col) and row1 >= min_row - 1 and row0 <= max_row + 1
    return False

def reflection_target(marker: dict[str, Any], row: int, col: int) -> Cell | None:
    if marker["kind"] == "point":
        marker_row, marker_col = marker["cells"][0]
        return 2 * marker_row - row, 2 * marker_col - col
    if marker["kind"] == "horizontal":
        axis_row = next(iter(marker["rows"]))
        return 2 * axis_row - row, col
    if marker["kind"] == "vertical":
        axis_col = next(iter(marker["cols"]))
        return row, 2 * axis_col - col
    return None

def component_record(component: dict[str, Any]) -> dict[str, Any]:
    return {
        "color": component["color"],
        "kind": component.get("kind"),
        "bbox": list(component["bbox"]),
        "size": len(component["cells"]),
    }

def render_axis_marker_reflection_fill(grid: Grid, marker_color: int) -> tuple[Grid | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    background = dominant_background(grid)
    marker_components = marker_axis_components(grid, marker_color)
    if not marker_components:
        return None, {"failure": "no_marker_components", "marker_color": marker_color}
    unsupported = [component for component in marker_components if component["kind"] == "unsupported"]
    if unsupported:
        return None, {
            "failure": "unsupported_marker_component_shape",
            "marker_color": marker_color,
            "unsupported_components": [component_record(component) for component in unsupported],
        }

    object_colors = {
        value
        for values in grid
        for value in values
        if value not in {background, marker_color}
    }
    objects = connected_components_for_colors(grid, object_colors)

    output = clone_grid(grid)
    object_links: list[dict[str, Any]] = []
    additions: list[dict[str, Any]] = []

    for obj in objects:
        options: list[tuple[int, int, int, list[Cell], dict[str, Any]]] = []
        for marker_index, marker in enumerate(marker_components):
            if not eligible_marker_object_pair(marker, obj):
                continue
            generated_cells: list[Cell] = []
            for row, col in obj["cells"]:
                target = reflection_target(marker, row, col)
                if target is None:
                    generated_cells = []
                    break
                target_row, target_col = target
                if not (0 <= target_row < height and 0 <= target_col < width):
                    generated_cells = []
                    break
                if grid[target_row][target_col] != background:
                    generated_cells = []
                    break
                generated_cells.append((target_row, target_col))
            if not generated_cells:
                continue
            chebyshev_gap, manhattan_gap = bbox_gap(marker["bbox"], obj["bbox"])
            options.append((chebyshev_gap, manhattan_gap, marker_index, generated_cells, marker))

        if not options:
            continue
        options.sort(key=lambda item: (item[0], item[1], item[2]))
        if len(options) > 1 and options[0][:2] == options[1][:2]:
            object_links.append(
                {
                    "object": component_record(obj),
                    "decision": "ambiguous_marker_pair_rejected",
                    "candidate_count": len(options),
                }
            )
            continue

        chebyshev_gap, manhattan_gap, marker_index, generated_cells, marker = options[0]
        for target_row, target_col in generated_cells:
            if output[target_row][target_col] not in {background, obj["color"]}:
                return None, {
                    "failure": "reflection_collision",
                    "marker_color": marker_color,
                    "cell": [target_row, target_col],
                    "existing": output[target_row][target_col],
                    "incoming": obj["color"],
                }
            output[target_row][target_col] = obj["color"]
            additions.append(
                {
                    "cell": [target_row, target_col],
                    "color": obj["color"],
                    "marker_index": marker_index,
                }
            )
        object_links.append(
            {
                "object": component_record(obj),
                "marker_index": marker_index,
                "marker_kind": marker["kind"],
                "marker_bbox": list(marker["bbox"]),
                "chebyshev_gap": chebyshev_gap,
                "manhattan_gap": manhattan_gap,
                "generated_cell_count": len(generated_cells),
            }
        )

    if output == grid:
        return None, {
            "failure": "no_reflection_additions",
            "marker_color": marker_color,
            "background": background,
        }
    return output, {
        "background": background,
        "marker_color": marker_color,
        "marker_components": [component_record(component) for component in marker_components],
        "object_links": object_links,
        "addition_count": len(additions),
    }
