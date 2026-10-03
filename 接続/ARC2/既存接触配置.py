"""旧D4反射色交換・最大接触slot配置の純粋関数。"""
from __future__ import annotations
from typing import Any
from collections import Counter
from itertools import permutations,product
from .既存領域転写 import mixed_region_dicts_for_grid
Grid=list[list[int]]

def _grid_shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0]) if grid else 0

def _dominant_color(grid: Grid) -> int | None:
    colors = Counter(value for row in grid for value in row)
    if not colors:
        return None
    return min(colors, key=lambda color: (-colors[color], color))

def _chiral_payload_bbox(cells: set[tuple[int, int]]) -> tuple[int, int, int, int]:
    rows = [row for row, _ in cells]
    cols = [col for _, col in cells]
    return min(rows), min(cols), max(rows), max(cols)

def _chiral_payload_slot_groups(
    grid: Grid,
) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]] | None:
    background = _dominant_color(grid)
    if background is None:
        return None
    regions = mixed_region_dicts_for_grid(grid, background, True)
    payloads = [
        {
            "cells": set(region["cells"]),
            "bbox": tuple(int(value) for value in region["bbox"]),
            "colors": tuple(sorted(int(color) for color in region["colors"])),
            "color_counts": {
                int(color): int(count)
                for color, count in region["color_counts"].items()
            },
        }
        for region in regions
        if len(region["colors"]) == 2
        and min(int(count) for count in region["color_counts"].values()) >= 2
    ]
    slots = [
        {
            "cells": set(region["cells"]),
            "bbox": tuple(int(value) for value in region["bbox"]),
            "color": int(region["colors"][0]),
        }
        for region in regions
        if len(region["colors"]) == 1
    ]
    if not payloads or not slots:
        return None

    groups: list[dict[str, Any] | None] = [
        {
            "color": slot["color"],
            "cells": set(slot["cells"]),
            "regions": [slot],
        }
        for slot in slots
    ]
    merged = True
    while merged:
        merged = False
        for left_index, left in enumerate(groups):
            if left is None:
                continue
            for right_index in range(left_index + 1, len(groups)):
                right = groups[right_index]
                if right is None or left["color"] != right["color"]:
                    continue
                left_box = _chiral_payload_bbox(left["cells"])
                right_box = _chiral_payload_bbox(right["cells"])
                row_gap = max(
                    left_box[0] - right_box[2] - 1,
                    right_box[0] - left_box[2] - 1,
                    0,
                )
                col_gap = max(
                    left_box[1] - right_box[3] - 1,
                    right_box[1] - left_box[3] - 1,
                    0,
                )
                if max(row_gap, col_gap) > 1:
                    continue
                left["cells"].update(right["cells"])
                left["regions"].extend(right["regions"])
                groups[right_index] = None
                merged = True
                break
            if merged:
                break
    slot_groups = [group for group in groups if group is not None]
    if len(payloads) != len(slot_groups):
        return None
    return int(background), payloads, slot_groups

def _chiral_payload_candidates(
    grid: Grid,
    payload: dict[str, Any],
    slot: dict[str, Any],
    background: int,
) -> list[dict[str, Any]]:
    height, width = _grid_shape(grid)
    source_cells = set(payload["cells"])
    row0, col0, row1, col1 = payload["bbox"]
    source_height = row1 - row0 + 1
    source_width = col1 - col0 + 1
    local_cells = [
        (row - row0, col - col0, int(grid[row][col]))
        for row, col in sorted(source_cells)
    ]
    colors = tuple(int(color) for color in payload["colors"])
    slot_cells = set(slot["cells"])
    candidates: list[dict[str, Any]] = []
    for transform_index in range(8):
        transformed: list[tuple[int, int, int]] = []
        for row, col, color in local_cells:
            if transform_index == 0:
                transformed_row, transformed_col = row, col
            elif transform_index == 1:
                transformed_row, transformed_col = col, source_height - 1 - row
            elif transform_index == 2:
                transformed_row, transformed_col = (
                    source_height - 1 - row,
                    source_width - 1 - col,
                )
            elif transform_index == 3:
                transformed_row, transformed_col = source_width - 1 - col, row
            elif transform_index == 4:
                transformed_row, transformed_col = row, source_width - 1 - col
            elif transform_index == 5:
                transformed_row, transformed_col = source_height - 1 - row, col
            elif transform_index == 6:
                transformed_row, transformed_col = col, row
            else:
                transformed_row, transformed_col = (
                    source_width - 1 - col,
                    source_height - 1 - row,
                )
            transformed.append((transformed_row, transformed_col, color))
        transformed_height = max(row for row, _, _ in transformed) + 1
        transformed_width = max(col for _, col, _ in transformed) + 1
        if transformed_height > height or transformed_width > width:
            continue
        color_maps = (
            {colors[0]: colors[1], colors[1]: colors[0]}
            if transform_index >= 4
            else {colors[0]: colors[0], colors[1]: colors[1]},
        )
        for color_map in color_maps:
            for target_row in range(height - transformed_height + 1):
                for target_col in range(width - transformed_width + 1):
                    mapped = {
                        (target_row + row, target_col + col): color_map[color]
                        for row, col, color in transformed
                    }
                    mapped_cells = set(mapped)
                    if mapped_cells & slot_cells:
                        continue
                    if any(
                        grid[row][col] != background
                        and (row, col) not in source_cells
                        and (row, col) not in slot_cells
                        for row, col in mapped_cells
                    ):
                        continue
                    contact_count = sum(
                        (row + row_delta, col + col_delta) in slot_cells
                        for row, col in mapped_cells
                        for row_delta, col_delta in (
                            (1, 0),
                            (-1, 0),
                            (0, 1),
                            (0, -1),
                        )
                    )
                    if contact_count <= 0:
                        continue
                    candidates.append(
                        {
                            "transform_index": transform_index,
                            "target_origin": (target_row, target_col),
                            "mapped": mapped,
                            "cells": mapped_cells,
                            "contact_count": contact_count,
                            "reflection_role_swap": transform_index >= 4,
                        }
                    )
    return candidates

def _chiral_payload_slot_render(
    grid: Grid,
) -> tuple[Grid | None, dict[str, Any]]:
    parsed = _chiral_payload_slot_groups(grid)
    if parsed is None:
        return None, {"failure": "chiral_payload_slot_scene_not_unique"}
    background, payloads, slot_groups = parsed
    pair_candidates: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for payload_index, payload in enumerate(payloads):
        for slot_index, slot in enumerate(slot_groups):
            candidates = _chiral_payload_candidates(
                grid,
                payload,
                slot,
                background,
            )
            if not candidates:
                continue
            best_contact = max(
                int(candidate["contact_count"]) for candidate in candidates
            )
            best = [
                candidate
                for candidate in candidates
                if int(candidate["contact_count"]) == best_contact
            ]
            unique: dict[tuple[Any, ...], dict[str, Any]] = {}
            for candidate in best:
                key = (
                    int(candidate["transform_index"]),
                    tuple(candidate["target_origin"]),
                    tuple(sorted(candidate["mapped"].items())),
                )
                unique.setdefault(key, candidate)
            pair_candidates[(payload_index, slot_index)] = list(unique.values())

    assignment_records: list[tuple[int, tuple[int, ...], tuple[dict[str, Any], ...]]] = []
    for slot_assignment in permutations(range(len(slot_groups))):
        options = [
            pair_candidates.get((payload_index, slot_index), [])
            for payload_index, slot_index in enumerate(slot_assignment)
        ]
        if any(not option for option in options):
            continue
        for selected in product(*options):
            occupied: set[tuple[int, int]] = set()
            if any(occupied.intersection(candidate["cells"]) for candidate in selected):
                continue
            occupied.update(
                cell
                for candidate in selected
                for cell in candidate["cells"]
            )
            assignment_records.append(
                (
                    sum(int(candidate["contact_count"]) for candidate in selected),
                    tuple(slot_assignment),
                    tuple(selected),
                )
            )
    if not assignment_records:
        return None, {"failure": "chiral_payload_slot_no_collision_free_assignment"}
    best_score = max(record[0] for record in assignment_records)
    best_assignments = [
        record for record in assignment_records if record[0] == best_score
    ]
    outputs: dict[tuple[tuple[int, ...], ...], tuple[int, tuple[int, ...], tuple[dict[str, Any], ...]]] = {}
    for record in best_assignments:
        output = [list(row) for row in grid]
        for payload in payloads:
            for row, col in payload["cells"]:
                output[row][col] = background
        for candidate in record[2]:
            for (row, col), color in candidate["mapped"].items():
                output[row][col] = int(color)
        outputs.setdefault(tuple(tuple(row) for row in output), record)
    if len(outputs) != 1:
        return None, {
            "failure": "chiral_payload_slot_assignment_ambiguous",
            "candidate_count": len(best_assignments),
            "output_count": len(outputs),
        }
    selected = next(iter(outputs.values()))
    return [list(row) for row in next(iter(outputs))], {
        "renderer_case": "chiral_payload_slot_transfer",
        "payload_count": len(payloads),
        "slot_group_count": len(slot_groups),
        "assignment_score": int(selected[0]),
        "assignment": [int(value) for value in selected[1]],
        "transform_indices": [
            int(candidate["transform_index"]) for candidate in selected[2]
        ],
        "reflection_role_swap_count": sum(
            int(candidate["reflection_role_swap"]) for candidate in selected[2]
        ),
        "event_count": sum(len(payload["cells"]) for payload in payloads),
    }
