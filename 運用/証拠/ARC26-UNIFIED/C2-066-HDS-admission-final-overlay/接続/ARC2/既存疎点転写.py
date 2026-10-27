"""既存の色別疎点graph/端点転写と教師規則推定。"""
from __future__ import annotations
from collections import defaultdict
from typing import Any
import math
from .既存凡例穴対応 import grid_shape
from .既存辺対応抽出 import dominant_background
Grid=list[list[int]]
Cell=tuple[int,int]

def sparse_point_color_points(grid: Grid, background_color: int) -> dict[int, set[Cell]]:
    points: dict[int, set[Cell]] = defaultdict(set)
    for row_index, row in enumerate(grid):
        for col_index, value in enumerate(row):
            if value != background_color:
                points[int(value)].add((row_index, col_index))
    return dict(points)

def active_cell_count(grid: Grid, background_color: int) -> int:
    return sum(1 for row in grid for value in row if value != background_color)

def straight_octilinear_segment(first: Cell, second: Cell) -> set[Cell] | None:
    row0, col0 = first
    row1, col1 = second
    row_delta = row1 - row0
    col_delta = col1 - col0
    if not (row_delta == 0 or col_delta == 0 or abs(row_delta) == abs(col_delta)):
        return None
    row_step = (row_delta > 0) - (row_delta < 0)
    col_step = (col_delta > 0) - (col_delta < 0)
    step_count = max(abs(row_delta), abs(col_delta))
    return {
        (row0 + row_step * step_index, col0 + col_step * step_index)
        for step_index in range(step_count + 1)
    }

def sparse_point_graph_edges(points: set[Cell]) -> list[tuple[Cell, Cell, set[Cell]]]:
    ordered_points = sorted(points)
    edges: list[tuple[Cell, Cell, set[Cell]]] = []
    for index, first in enumerate(ordered_points):
        for second in ordered_points[index + 1 :]:
            segment = straight_octilinear_segment(first, second)
            if segment is not None:
                edges.append((first, second, segment))
    return edges

def sparse_point_graph_connected(points: set[Cell], edges: list[tuple[Cell, Cell, set[Cell]]]) -> bool:
    if not points:
        return False
    adjacency: dict[Cell, set[Cell]] = {point: set() for point in points}
    for first, second, _segment in edges:
        adjacency[first].add(second)
        adjacency[second].add(first)
    seen = {next(iter(points))}
    stack = list(seen)
    while stack:
        point = stack.pop()
        for neighbor in adjacency[point]:
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return seen == points

def sparse_point_closed_cycle_edges(points: set[Cell]) -> list[tuple[Cell, Cell, set[Cell]]] | None:
    if len(points) < 3:
        return None
    center_row = sum(row for row, _col in points) / len(points)
    center_col = sum(col for _row, col in points) / len(points)
    ordered_points = sorted(
        points,
        key=lambda point: (
            math.atan2(point[0] - center_row, point[1] - center_col),
            point[0],
            point[1],
        ),
    )
    edges: list[tuple[Cell, Cell, set[Cell]]] = []
    for index, first in enumerate(ordered_points):
        second = ordered_points[(index + 1) % len(ordered_points)]
        segment = straight_octilinear_segment(first, second)
        if segment is None:
            return None
        edges.append((first, second, segment))
    if len({row for row, _col in ordered_points}) == 1 or len({col for _row, col in ordered_points}) == 1:
        return None
    return edges

def sparse_point_base_shape(points: set[Cell]) -> tuple[set[Cell], dict[str, Any]]:
    if len(points) == 1:
        return set(points), {"kind": "singleton", "edges": []}
    cycle_edges = sparse_point_closed_cycle_edges(points)
    if cycle_edges is not None:
        mask: set[Cell] = set()
        for _first, _second, segment in cycle_edges:
            mask.update(segment)
        return mask, {"kind": "closed_cycle", "edges": cycle_edges}

    graph_edges = sparse_point_graph_edges(points)
    if not graph_edges or not sparse_point_graph_connected(points, graph_edges):
        return set(points), {"kind": "disconnected", "edges": graph_edges}
    mask = set()
    for _first, _second, segment in graph_edges:
        mask.update(segment)
    return mask, {"kind": "edge_graph", "edges": graph_edges}

def sparse_point_incident_shape(source_info: dict[str, Any], anchor: Cell) -> set[Cell]:
    mask: set[Cell] = set()
    for first, second, segment in source_info.get("edges", []):
        if first == anchor or second == anchor:
            mask.update(segment)
    return mask or {anchor}

def shifted_sparse_point_mask(mask: set[Cell], row_delta: int, col_delta: int, height: int, width: int) -> set[Cell] | None:
    shifted: set[Cell] = set()
    for row, col in mask:
        shifted_row = row + row_delta
        shifted_col = col + col_delta
        if not (0 <= shifted_row < height and 0 <= shifted_col < width):
            return None
        shifted.add((shifted_row, shifted_col))
    return shifted

def sparse_point_copy_candidates(
    color: int,
    singleton: Cell,
    color_points: dict[int, set[Cell]],
    base_masks: dict[int, set[Cell]],
    shape_infos: dict[int, dict[str, Any]],
    occupied_base: set[Cell],
    height: int,
    width: int,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source_color, source_points in sorted(color_points.items()):
        if source_color == color or len(source_points) < 2 or source_color not in base_masks:
            continue
        source_info = shape_infos[source_color]
        for anchor in sorted(source_points):
            row_delta = singleton[0] - anchor[0]
            col_delta = singleton[1] - anchor[1]
            if max(abs(row_delta), abs(col_delta)) > 1:
                continue
            raw_candidates = (
                ("full", base_masks[source_color]),
                ("incident", sparse_point_incident_shape(source_info, anchor)),
            )
            for copy_type, raw_mask in raw_candidates:
                shifted = shifted_sparse_point_mask(raw_mask, row_delta, col_delta, height, width)
                if shifted is None:
                    continue
                mask = set(shifted - occupied_base)
                mask.add(singleton)
                candidates.append(
                    {
                        "type": copy_type,
                        "source_color": int(source_color),
                        "anchor": list(anchor),
                        "offset": [row_delta, col_delta],
                        "source_kind": source_info.get("kind"),
                        "mask": mask,
                    }
                )
    return candidates

def sparse_point_rule_key(row_delta: int, col_delta: int, source_kind: str) -> str:
    return f"{row_delta},{col_delta},{source_kind}"

def sparse_point_copy_defaults(copy_rules: Any) -> dict[str, str]:
    """Collapse consistent offset rules into a source-graph policy."""
    if not isinstance(copy_rules, dict):
        return {}
    by_kind: dict[str, set[str]] = defaultdict(set)
    for key, copy_type in copy_rules.items():
        if not isinstance(key, str) or not isinstance(copy_type, str):
            continue
        parts = key.split(",", 2)
        if len(parts) != 3:
            continue
        by_kind[parts[2]].add(copy_type)
    return {
        source_kind: next(iter(copy_types))
        for source_kind, copy_types in sorted(by_kind.items())
        if len(copy_types) == 1
    }

def render_sparse_octilinear_point_graph_completion(
    grid: Grid,
    sparse_point_copy_rules: Any | None = None,
    *,
    sparse_point_copy_defaults: Any | None = None,
    learning_target: Grid | None = None,
) -> tuple[Grid | None, dict[str, Any]]:
    height, width = grid_shape(grid)
    if height == 0 or width == 0:
        return None, {"failure": "empty_sparse_point_grid"}
    background_color = dominant_background(grid)
    point_sets = sparse_point_color_points(grid, background_color)
    if not point_sets:
        return None, {"failure": "no_sparse_point_colors"}
    input_active_cell_count = active_cell_count(grid, background_color)
    if input_active_cell_count > 25:
        return None, {
            "failure": "sparse_point_input_too_dense",
            "sparse_point_input_cell_count": input_active_cell_count,
        }

    copy_rules = sparse_point_copy_rules if isinstance(sparse_point_copy_rules, dict) else {}
    copy_defaults = (
        sparse_point_copy_defaults
        if isinstance(sparse_point_copy_defaults, dict)
        else {}
    )
    target_points = sparse_point_color_points(learning_target, background_color) if learning_target is not None else {}

    base_masks: dict[int, set[Cell]] = {}
    shape_infos: dict[int, dict[str, Any]] = {}
    for color, points in point_sets.items():
        if len(points) < 2:
            continue
        mask, info = sparse_point_base_shape(points)
        base_masks[color] = mask
        shape_infos[color] = info
    if not base_masks:
        return None, {"failure": "no_sparse_point_source_color"}

    occupied_base = set().union(*base_masks.values())
    output = [[background_color for _col in range(width)] for _row in range(height)]
    for color, mask in base_masks.items():
        for row, col in mask:
            output[row][col] = color

    singleton_records: list[dict[str, Any]] = []
    rule_observations: list[dict[str, Any]] = []
    singleton_copy_count = 0
    for color, points in sorted(point_sets.items()):
        if len(points) != 1:
            continue
        singleton = next(iter(points))
        candidates = sparse_point_copy_candidates(
            color,
            singleton,
            point_sets,
            base_masks,
            shape_infos,
            occupied_base,
            height,
            width,
        )
        selected: dict[str, Any] | None = None

        rule_matches: list[dict[str, Any]] = []
        for candidate in candidates:
            row_delta, col_delta = candidate["offset"]
            source_kind = str(candidate["source_kind"])
            if copy_rules.get(sparse_point_rule_key(row_delta, col_delta, source_kind)) == candidate["type"]:
                rule_matches.append(candidate)
        unique_candidate_masks = {frozenset(candidate["mask"]) for candidate in candidates}
        if len(rule_matches) == 1:
            selected = rule_matches[0]
        elif len(unique_candidate_masks) == 1 and candidates:
            selected = candidates[0]
        else:
            default_copy_type = copy_defaults.get(str(candidates[0]["source_kind"])) if candidates else None
            default_candidates = [
                candidate
                for candidate in candidates
                if candidate["type"] == default_copy_type
            ]
            default_masks = {
                frozenset(candidate["mask"]) for candidate in default_candidates
            }
            if default_copy_type is not None and len(default_masks) == 1 and default_candidates:
                selected = sorted(
                    default_candidates,
                    key=lambda candidate: (
                        candidate["offset"][0],
                        candidate["offset"][1],
                        str(candidate["source_kind"]),
                        int(candidate["source_color"]),
                        candidate["anchor"],
                    ),
                )[0]
            if selected is None and learning_target is not None:
                target_mask = target_points.get(color, set())
                exact_candidates = [candidate for candidate in candidates if candidate["mask"] == target_mask]
                if exact_candidates:
                    selected = sorted(
                        exact_candidates,
                        key=lambda candidate: (
                            candidate["offset"][0],
                            candidate["offset"][1],
                            str(candidate["source_kind"]),
                            str(candidate["type"]),
                            int(candidate["source_color"]),
                            candidate["anchor"],
                        ),
                    )[0]

        if selected is None:
            selected_mask = {singleton}
            singleton_records.append(
                {
                    "color": int(color),
                    "copy_type": "self",
                    "source_color": None,
                    "source_kind": "self",
                    "offset": [0, 0],
                    "cell_count": 1,
                }
            )
        else:
            selected_mask = selected["mask"]
            if selected["type"] != "self":
                singleton_copy_count += 1
                row_delta, col_delta = selected["offset"]
                source_kind = str(selected["source_kind"])
                rule_key = sparse_point_rule_key(row_delta, col_delta, source_kind)
                rule_observations.append({"rule_key": rule_key, "copy_type": selected["type"]})
            singleton_records.append(
                {
                    "color": int(color),
                    "copy_type": selected["type"],
                    "source_color": selected["source_color"],
                    "source_kind": selected["source_kind"],
                    "offset": selected["offset"],
                    "cell_count": len(selected_mask),
                }
            )
        for row, col in selected_mask:
            if output[row][col] == background_color:
                output[row][col] = color

    if output == grid:
        return None, {"failure": "identity_sparse_point_graph_completion"}

    output_active_cell_count = active_cell_count(output, background_color)
    return output, {
        "renderer_case": "sparse_octilinear_point_graph_completion",
        "sparse_point_background_color": background_color,
        "sparse_point_color_count": len(point_sets),
        "sparse_point_source_color_count": len(base_masks),
        "sparse_point_rule_observations": rule_observations,
        "sparse_point_singleton_records": singleton_records,
        "sparse_point_singleton_copy_count": singleton_copy_count,
        "sparse_point_edge_cell_count": sum(len(mask) for mask in base_masks.values()),
        "sparse_point_completed_cell_count": output_active_cell_count - input_active_cell_count,
    }

def infer_sparse_octilinear_point_graph_policy(
    train_pairs: list[dict[str, Grid]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if len(train_pairs) < 2:
        return None, {"failure": "too_few_train_pairs_for_sparse_point_graph"}
    copy_rules: dict[str, str] = {}
    train_rule_records: list[dict[str, Any]] = []
    for train_index, pair in enumerate(train_pairs):
        input_grid = pair["input"]
        output_grid = pair["output"]
        if grid_shape(input_grid) != grid_shape(output_grid):
            return None, {
                "failure": "sparse_point_shape_change",
                "train_index": train_index,
                "input_shape": grid_shape(input_grid),
                "output_shape": grid_shape(output_grid),
            }
        background_color = dominant_background(input_grid)
        if dominant_background(output_grid) != background_color:
            return None, {
                "failure": "sparse_point_background_changed",
                "train_index": train_index,
            }
        input_active_count = active_cell_count(input_grid, background_color)
        output_active_count = active_cell_count(output_grid, background_color)
        if input_active_count > 25:
            return None, {
                "failure": "sparse_point_train_input_too_dense",
                "train_index": train_index,
                "input_active_cell_count": input_active_count,
            }
        if output_active_count <= input_active_count:
            return None, {
                "failure": "sparse_point_train_not_expansive",
                "train_index": train_index,
                "input_active_cell_count": input_active_count,
                "output_active_cell_count": output_active_count,
            }

        rendered, record = render_sparse_octilinear_point_graph_completion(
            input_grid,
            copy_rules,
            sparse_point_copy_defaults=sparse_point_copy_defaults(copy_rules),
            learning_target=output_grid,
        )
        if rendered is None:
            return None, {
                "failure": record.get("failure", "sparse_point_learning_render_failed"),
                "train_index": train_index,
                "render_record": record,
            }
        for observation in record.get("sparse_point_rule_observations", []):
            if not isinstance(observation, dict):
                continue
            rule_key = observation.get("rule_key")
            copy_type = observation.get("copy_type")
            if not isinstance(rule_key, str) or not isinstance(copy_type, str):
                continue
            previous = copy_rules.get(rule_key)
            if previous is not None and previous != copy_type:
                return None, {
                    "failure": "sparse_point_copy_rule_conflict",
                    "train_index": train_index,
                    "rule_key": rule_key,
                    "previous_copy_type": previous,
                    "copy_type": copy_type,
                }
            copy_rules[rule_key] = copy_type
            train_rule_records.append({"train_index": train_index, "rule_key": rule_key, "copy_type": copy_type})

    return {
        "sparse_point_copy_rules": dict(sorted(copy_rules.items())),
        "sparse_point_copy_defaults": sparse_point_copy_defaults(copy_rules),
        "sparse_point_rule_count": len(copy_rules),
        "sparse_point_train_rule_records": train_rule_records,
    }, {}
