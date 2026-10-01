"""旧ARCの入力色による辺対応・抽出を保守的な適用域で再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_fit_generator.py。
末尾の辺対応候補だけが新しい曖昧入力拒否guard。
"""
from __future__ import annotations
from collections import Counter
from typing import Any
from .既存領域転写 import Grid
from .既存物体特徴 import dominant_background_for_grid
from .既存凡例穴対応 import grid_shape
from .既存格子操作 import transform_grid_by_name

SIDE_TRANSFORM_MAPS: dict[str, dict[str, str]] = {
    "identity": {"top": "top", "bottom": "bottom", "left": "left", "right": "right"},
    "rot90": {"top": "right", "right": "bottom", "bottom": "left", "left": "top"},
    "rot180": {"top": "bottom", "bottom": "top", "left": "right", "right": "left"},
    "rot270": {"top": "left", "left": "bottom", "bottom": "right", "right": "top"},
    "flip_h": {"top": "top", "bottom": "bottom", "left": "right", "right": "left"},
    "flip_v": {"top": "bottom", "bottom": "top", "left": "left", "right": "right"},
    "transpose": {"top": "left", "left": "top", "bottom": "right", "right": "bottom"},
    "anti_transpose": {"top": "right", "right": "top", "bottom": "left", "left": "bottom"},
}


def dominant_background(grid: Grid) -> int:
    return dominant_background_for_grid(grid)


def outer_border_colors(grid: Grid) -> set[int]:
    height, width = grid_shape(grid)
    if height == 0 or width == 0:
        return set()
    colors = set(grid[0]) | set(grid[height - 1])
    colors.update(grid[row][0] for row in range(height))
    colors.update(grid[row][width - 1] for row in range(height))
    return colors


def infer_payload_color_bbox(grid: Grid) -> tuple[int, int, int, int] | None:
    height, width = grid_shape(grid)
    if height < 3 or width < 3:
        return None
    border_colors = outer_border_colors(grid)
    payload_cells = [
        (row, col)
        for row in range(height)
        for col in range(width)
        if grid[row][col] not in border_colors
    ]
    if not payload_cells:
        return None
    min_row = min(row for row, _ in payload_cells)
    max_row = max(row for row, _ in payload_cells) + 1
    min_col = min(col for _, col in payload_cells)
    max_col = max(col for _, col in payload_cells) + 1
    if min_row == 0 or min_col == 0 or max_row == height or max_col == width:
        return None
    return min_row, min_col, max_row, max_col


def border_side_counts_for_color(grid: Grid, color: int) -> dict[str, int]:
    height, width = grid_shape(grid)
    return {
        "top": sum(1 for col in range(width) if grid[0][col] == color),
        "bottom": sum(1 for col in range(width) if grid[height - 1][col] == color),
        "left": sum(1 for row in range(height) if grid[row][0] == color),
        "right": sum(1 for row in range(height) if grid[row][width - 1] == color),
    }


def dominant_border_side_for_color(grid: Grid, color: int) -> tuple[str | None, dict[str, int]]:
    counts = border_side_counts_for_color(grid, color)
    best_count = max(counts.values())
    if best_count <= 0:
        return None, counts
    best_sides = [side for side, count in counts.items() if count == best_count]
    if len(best_sides) != 1:
        return None, counts
    return best_sides[0], counts


def side_strip_values(grid: Grid, bbox: tuple[int, int, int, int], side: str) -> list[int]:
    height, width = grid_shape(grid)
    min_row, min_col, max_row, max_col = bbox
    if side == "top" and min_row > 0:
        return [grid[min_row - 1][col] for col in range(min_col, max_col)]
    if side == "bottom" and max_row < height:
        return [grid[max_row][col] for col in range(min_col, max_col)]
    if side == "left" and min_col > 0:
        return [grid[row][min_col - 1] for row in range(min_row, max_row)]
    if side == "right" and max_col < width:
        return [grid[row][max_col] for row in range(min_row, max_row)]
    return []


def dominant_payload_side_guide_color(
    grid: Grid,
    bbox: tuple[int, int, int, int],
    side: str,
    border_colors: set[int],
    background_color: int,
) -> int | None:
    values = side_strip_values(grid, bbox, side)
    if not values:
        return None
    counts = Counter(
        value
        for value in values
        if value in border_colors and value != background_color
    )
    if not counts:
        return None
    guide_color, guide_count = counts.most_common(1)[0]
    if guide_count * 2 < len(values):
        return None
    if sum(1 for count in counts.values() if count == guide_count) > 1:
        return None
    return guide_color


def infer_edge_guided_payload_transform(
    grid: Grid,
    bbox: tuple[int, int, int, int],
) -> tuple[str | None, dict[str, Any]]:
    border_colors = outer_border_colors(grid)
    background_color = dominant_background(grid)
    constraints: dict[str, str] = {}
    side_records: dict[str, Any] = {}
    for side in ("top", "bottom", "left", "right"):
        guide_color = dominant_payload_side_guide_color(
            grid,
            bbox,
            side,
            border_colors,
            background_color,
        )
        if guide_color is None:
            continue
        target_side, side_counts = dominant_border_side_for_color(grid, guide_color)
        side_records[side] = {
            "guide_color": guide_color,
            "target_side": target_side,
            "border_side_counts": side_counts,
        }
        if target_side is not None:
            constraints[side] = target_side

    if len(constraints) < 2:
        return None, {
            "failure": "too_few_edge_payload_side_constraints",
            "side_constraints": constraints,
            "side_records": side_records,
        }

    matching_transforms = [
        transform_name
        for transform_name, side_map in SIDE_TRANSFORM_MAPS.items()
        if all(side_map.get(source_side) == target_side for source_side, target_side in constraints.items())
    ]
    if len(matching_transforms) != 1:
        return None, {
            "failure": "ambiguous_edge_payload_transform",
            "side_constraints": constraints,
            "matching_transforms": matching_transforms,
            "side_records": side_records,
        }
    return matching_transforms[0], {
        "side_constraints": constraints,
        "side_records": side_records,
    }


def render_edge_guided_payload_crop_normalizer(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    if not grid or not grid[0]:
        return None, {"failure": "empty_grid"}
    bbox = infer_payload_color_bbox(grid)
    if bbox is None:
        return None, {"failure": "no_edge_guided_payload_bbox"}

    transform_name, transform_record = infer_edge_guided_payload_transform(grid, bbox)
    if transform_name is None:
        return None, transform_record

    min_row, min_col, max_row, max_col = bbox
    crop = [row[min_col:max_col] for row in grid[min_row:max_row]]
    output = transform_grid_by_name(crop, transform_name)
    if output is None:
        return None, {"failure": "unsupported_payload_transform", "transform": transform_name}
    if output == grid:
        return None, {"failure": "identity_render"}

    payload_colors = sorted(
        {
            grid[row][col]
            for row in range(min_row, max_row)
            for col in range(min_col, max_col)
            if grid[row][col] not in outer_border_colors(grid)
        }
    )
    return output, {
        "renderer_case": "edge_guided_payload_crop_normalizer",
        "payload_bbox": [min_row, min_col, max_row, max_col],
        "payload_surface_shape": [max_row - min_row, max_col - min_col],
        "payload_cell_count": (max_row - min_row) * (max_col - min_col),
        "payload_transform": transform_name,
        "payload_colors": payload_colors,
        "border_colors": sorted(outer_border_colors(grid)),
        **transform_record,
    }


def 辺対応候補(格子, _policy):
    """弱い/競合するguideを無視して残りの辺だけで断定しない。"""
    if not 格子 or not 格子[0]:
        return None, {'failure': '空格子'}
    個数 = Counter(v for row in 格子 for v in row)
    最大数 = max(個数.values())
    if sum(n == 最大数 for n in 個数.values()) != 1:
        return None, {'failure': '背景頻度が同率'}
    背景 = dominant_background(格子)
    範囲 = infer_payload_color_bbox(格子)
    if 範囲 is None:
        return None, {'failure': 'payload境界が未確定'}
    外周色群 = outer_border_colors(格子)
    for 辺 in ('top', 'bottom', 'left', 'right'):
        値群 = side_strip_values(格子, 範囲, 辺)
        if not 値群 or len(set(値群)) != 1:
            return None, {'failure': 'guide帯が非一様又は空', 'side': 辺}
        if 値群[0] == 背景:
            continue
        guide = dominant_payload_side_guide_color(格子, 範囲, 辺, 外周色群, 背景)
        if guide is None:
            return None, {'failure': 'eligible guideが未確定', 'side': 辺}
        向先, _ = dominant_border_side_for_color(格子, guide)
        if 向先 is None:
            return None, {'failure': 'guideの外周辺が未確定', 'side': 辺}
    出力, 詳細 = render_edge_guided_payload_crop_normalizer(格子)
    if 出力 is not None and not (1 <= len(出力) <= 30 and 1 <= len(出力[0]) <= 30):
        return None, {'failure': '出力寸法範囲外'}
    return 出力, 詳細
