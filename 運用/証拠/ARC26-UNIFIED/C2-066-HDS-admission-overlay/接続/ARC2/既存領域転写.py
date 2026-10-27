"""旧ARCの領域パレット転写の純粋依存閉包。候補生成のみで排出しない。
出典: gatchimuchio/ARC-Layer-0-Functional-Compliance @454670a1、
arc2_runtime_program_search/object_graph/feature_index.py の同名定義。
"""
from __future__ import annotations
from collections import Counter, deque
from functools import lru_cache
from typing import Any, NamedTuple
from .既存穴充填 import _grid_shape, _dominant_color

Grid = list[list[int]]

GridKey = tuple[tuple[int, ...], ...]

def grid_key(grid: Grid) -> GridKey:
    return tuple(tuple(int(value) for value in row) for row in grid)

Cell = tuple[int, int]

BBox = tuple[int, int, int, int]

class RegionFeatureRecord(NamedTuple):
    cells: tuple[Cell, ...]
    bbox: BBox
    size: int
    colors: tuple[int, ...]
    color_counts: tuple[tuple[int, int], ...]
    bbox_shape: tuple[int, int]
    bbox_area: int
    normalized_shape: tuple[Cell, ...]
    is_solid_rectangle: bool

ORTHOGONAL_DIRECTIONS: tuple[Cell, ...] = ((1, 0), (-1, 0), (0, 1), (0, -1))

DIAGONAL_DIRECTIONS: tuple[Cell, ...] = (
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
)

def _bbox_for_cells(cells: list[Cell]) -> BBox:
    rows = [row for row, _col in cells]
    cols = [col for _row, col in cells]
    return min(rows), min(cols), max(rows), max(cols)

def bbox_shape_for_bbox(bbox: BBox) -> tuple[int, int]:
    row0, col0, row1, col1 = bbox
    return row1 - row0 + 1, col1 - col0 + 1

def normalized_shape_for_cells(cells: set[Cell] | list[Cell] | tuple[Cell, ...]) -> tuple[Cell, ...]:
    if not cells:
        return tuple()
    row_min = min(row for row, _col in cells)
    col_min = min(col for _row, col in cells)
    return tuple(sorted((row - row_min, col - col_min) for row, col in cells))

def _region_feature_record(
    cells: list[Cell],
    color_counts: dict[int, int],
) -> RegionFeatureRecord:
    sorted_cells = tuple(sorted(cells))
    bbox = _bbox_for_cells(cells)
    bbox_shape = bbox_shape_for_bbox(bbox)
    bbox_area = bbox_shape[0] * bbox_shape[1]
    return RegionFeatureRecord(
        cells=sorted_cells,
        bbox=bbox,
        size=len(sorted_cells),
        colors=tuple(sorted(int(color) for color in color_counts)),
        color_counts=tuple(
            sorted((int(color), int(count)) for color, count in color_counts.items())
        ),
        bbox_shape=bbox_shape,
        bbox_area=bbox_area,
        normalized_shape=normalized_shape_for_cells(sorted_cells),
        is_solid_rectangle=len(sorted_cells) == bbox_area,
    )

@lru_cache(maxsize=8192)
def _mixed_region_feature_records(
    key: GridKey,
    background_color: int,
    include_diagonal: bool,
) -> tuple[RegionFeatureRecord, ...]:
    height = len(key)
    width = len(key[0]) if key else 0
    directions = ORTHOGONAL_DIRECTIONS + (DIAGONAL_DIRECTIONS if include_diagonal else tuple())
    seen: set[Cell] = set()
    records: list[RegionFeatureRecord] = []

    for row in range(height):
        for col in range(width):
            if (row, col) in seen or int(key[row][col]) == int(background_color):
                continue
            queue: deque[Cell] = deque([(row, col)])
            seen.add((row, col))
            cells: list[Cell] = []
            color_counts: dict[int, int] = {}
            while queue:
                current_row, current_col = queue.popleft()
                cells.append((current_row, current_col))
                color = int(key[current_row][current_col])
                color_counts[color] = color_counts.get(color, 0) + 1
                for row_delta, col_delta in directions:
                    next_row = current_row + row_delta
                    next_col = current_col + col_delta
                    next_cell = (next_row, next_col)
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if next_cell in seen or int(key[next_row][next_col]) == int(background_color):
                        continue
                    seen.add(next_cell)
                    queue.append(next_cell)
            records.append(_region_feature_record(cells, color_counts))

    return tuple(sorted(records, key=lambda record: (record.bbox, record.size)))

def mixed_region_dict_from_feature_record(
    record: RegionFeatureRecord,
) -> dict[str, Any]:
    return {
        "cells": list(record.cells),
        "bbox": record.bbox,
        "colors": list(record.colors),
        "color_counts": dict(record.color_counts),
        "size": int(record.size),
    }

def mixed_region_dicts_for_grid(
    grid: Grid,
    background_color: int,
    include_diagonal: bool = True,
) -> list[dict[str, Any]]:
    return [
        mixed_region_dict_from_feature_record(record)
        for record in _mixed_region_feature_records(
            grid_key(grid),
            int(background_color),
            bool(include_diagonal),
        )
    ]



def _enclosed_non_wall_regions(
    crop: Grid,
    wall_color: int,
) -> list[list[tuple[int, int]]]:
    height, width = _grid_shape(crop)
    seen: set[tuple[int, int]] = set()
    holes: list[list[tuple[int, int]]] = []
    for row in range(height):
        for col in range(width):
            cell = (row, col)
            if cell in seen or int(crop[row][col]) == int(wall_color):
                continue
            queue = [cell]
            seen.add(cell)
            cells: list[tuple[int, int]] = []
            touches_bbox = False
            for current_row, current_col in queue:
                cells.append((current_row, current_col))
                touches_bbox = touches_bbox or current_row in (0, height - 1) or current_col in (0, width - 1)
                for row_delta, col_delta in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    next_row = current_row + row_delta
                    next_col = current_col + col_delta
                    next_cell = (next_row, next_col)
                    if not (0 <= next_row < height and 0 <= next_col < width):
                        continue
                    if next_cell in seen or int(crop[next_row][next_col]) == int(wall_color):
                        continue
                    seen.add(next_cell)
                    queue.append(next_cell)
            if not touches_bbox:
                holes.append(cells)
    return holes

def _normalized_centroid(
    cells: list[tuple[int, int]],
    shape: tuple[int, int],
) -> tuple[float, float]:
    height, width = shape
    return (
        sum(row for row, _ in cells) / len(cells) / height,
        sum(col for _, col in cells) / len(cells) / width,
    )

def _minimum_centroid_assignment(
    template_holes: list[list[tuple[int, int]]],
    colored_holes: list[list[tuple[int, int]]],
    template_shape: tuple[int, int],
    colored_shape: tuple[int, int],
) -> list[list[tuple[int, int]]] | None:
    if len(template_holes) != len(colored_holes) or not template_holes:
        return None
    if len(template_holes) > 12:
        return None
    template_centroids = [
        _normalized_centroid(cells, template_shape)
        for cells in template_holes
    ]
    colored_centroids = [
        _normalized_centroid(cells, colored_shape)
        for cells in colored_holes
    ]
    costs = [
        [
            (template_centroids[index][0] - colored_centroids[colored_index][0]) ** 2
            + (template_centroids[index][1] - colored_centroids[colored_index][1]) ** 2
            for colored_index in range(len(colored_holes))
        ]
        for index in range(len(template_holes))
    ]

    @lru_cache(maxsize=None)
    def search(
        template_index: int,
        used_mask: int,
    ) -> tuple[float, tuple[int, ...], int] | None:
        if template_index == len(template_holes):
            return 0.0, (), 1
        best: tuple[float, tuple[int, ...], int] | None = None
        for colored_index in range(len(colored_holes)):
            if used_mask & (1 << colored_index):
                continue
            suffix = search(template_index + 1, used_mask | (1 << colored_index))
            if suffix is None:
                continue
            candidate = (
                costs[template_index][colored_index] + suffix[0],
                (colored_index, *suffix[1]),
                suffix[2],
            )
            if best is None or candidate[0] < best[0]:
                best = candidate
            elif candidate[0] == best[0]:
                best = (best[0], best[1], min(2, best[2] + candidate[2]))
        return best

    assignment = search(0, 0)
    if assignment is None or assignment[2] != 1:
        return None
    return [colored_holes[index] for index in assignment[1]]

def _dual_region_hole_palette_render(
    grid: Grid,
    policy: dict[str, Any],
) -> tuple[Grid | None, dict[str, Any]]:
    height, width = _grid_shape(grid)
    if not grid or any(len(row) != width for row in grid):
        return None, {"failure": "dual_region_requires_rectangular_grid"}
    background = _dominant_color(grid)
    if background is None:
        return None, {"failure": "dual_region_missing_background"}

    regions = mixed_region_dicts_for_grid(grid, background, True)
    if len(regions) != 2:
        return None, {
            "failure": "dual_region_requires_exactly_two_foreground_regions",
            "dual_region_region_count": len(regions),
        }
    plain_regions = [region for region in regions if len(region["colors"]) == 1]
    colored_regions = [region for region in regions if len(region["colors"]) > 1]
    if len(plain_regions) != 1 or len(colored_regions) != 1:
        return None, {
            "failure": "dual_region_template_and_colored_roles_not_unique",
            "dual_region_plain_region_count": len(plain_regions),
            "dual_region_colored_region_count": len(colored_regions),
        }

    template_region = plain_regions[0]
    colored_region = colored_regions[0]
    wall_color = int(template_region["colors"][0])
    template_bbox = tuple(int(value) for value in template_region["bbox"])
    colored_bbox = tuple(int(value) for value in colored_region["bbox"])
    template_cells = {tuple(cell) for cell in template_region["cells"]}
    template_row0, template_col0, template_row1, template_col1 = template_bbox
    template = [
        [
            wall_color
            if (row, col) in template_cells
            else background
            for col in range(template_col0, template_col1 + 1)
        ]
        for row in range(template_row0, template_row1 + 1)
    ]
    colored_row0, colored_col0, colored_row1, colored_col1 = colored_bbox
    colored = [
        list(row[colored_col0 : colored_col1 + 1])
        for row in grid[colored_row0 : colored_row1 + 1]
    ]
    template_holes = _enclosed_non_wall_regions(template, wall_color)
    colored_holes = _enclosed_non_wall_regions(colored, wall_color)
    if not template_holes or len(template_holes) != len(colored_holes):
        return None, {
            "failure": "dual_region_hole_inventory_mismatch",
            "dual_region_template_hole_count": len(template_holes),
            "dual_region_colored_hole_count": len(colored_holes),
        }
    assigned_colored_holes = _minimum_centroid_assignment(
        template_holes,
        colored_holes,
        _grid_shape(template),
        _grid_shape(colored),
    )
    if assigned_colored_holes is None:
        return None, {"failure": "dual_region_hole_assignment_failed"}

    output = [list(row) for row in template]
    mapping_records: list[dict[str, Any]] = []
    for template_hole, colored_hole in zip(template_holes, assigned_colored_holes):
        payload_colors = Counter(
            int(colored[row][col])
            for row, col in colored_hole
            if int(colored[row][col]) not in (int(background), wall_color)
        )
        if len(payload_colors) != 1:
            return None, {
                "failure": "dual_region_hole_payload_color_not_unique",
                "dual_region_payload_colors": dict(payload_colors),
            }
        payload_color = int(next(iter(payload_colors)))
        for row, col in template_hole:
            output[row][col] = payload_color
        mapping_records.append(
            {
                "template_hole_size": len(template_hole),
                "colored_hole_size": len(colored_hole),
                "payload_color": payload_color,
                "template_centroid": list(
                    _normalized_centroid(template_hole, _grid_shape(template))
                ),
                "colored_centroid": list(
                    _normalized_centroid(colored_hole, _grid_shape(colored))
                ),
            }
        )
    return output, {
        "event_count": sum(len(hole) for hole in template_holes),
        "changed_cell_count": sum(
            output[row][col] != template[row][col]
            for row in range(len(template))
            for col in range(len(template[row]))
        ),
        "dual_region_background": background,
        "dual_region_wall_color": wall_color,
        "dual_region_template_bbox": list(template_bbox),
        "dual_region_colored_bbox": list(colored_bbox),
        "dual_region_template_hole_count": len(template_holes),
        "dual_region_colored_hole_count": len(colored_holes),
        "dual_region_hole_mapping": mapping_records,
        "matching_mode": policy.get("matching_mode"),
    }
