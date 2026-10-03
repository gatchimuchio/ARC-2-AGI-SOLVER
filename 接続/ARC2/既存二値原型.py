"""現在課題の二値原型を照合する旧9関数。完成柄自体はコードに持たない。"""
from __future__ import annotations
from typing import Any
from collections import Counter
from .既存凡例穴対応 import grid_shape
from .既存辺対応抽出 import dominant_background
Grid=list[list[int]]
BinaryTemplate=list[list[int]]
Cell=tuple[int,int]
def two_color_values(grid: Grid) -> list[int]:
    return sorted(Counter(value for row in grid for value in row))

def binary_template_from_grid(grid: Grid, zero_color: int) -> BinaryTemplate:
    return [[0 if value == zero_color else 1 for value in row] for row in grid]

def rotate_binary_template_90(template: BinaryTemplate) -> BinaryTemplate:
    return [list(row) for row in zip(*template[::-1])]

def dihedral_binary_transforms(template: BinaryTemplate) -> list[tuple[str, BinaryTemplate]]:
    transforms: list[tuple[str, BinaryTemplate]] = []
    seen: set[tuple[tuple[int, ...], ...]] = set()
    current = [row[:] for row in template]
    for rotation_index in range(4):
        for flipped in (False, True):
            transformed = [row[::-1] for row in current] if flipped else [row[:] for row in current]
            key = tuple(tuple(row) for row in transformed)
            if key in seen:
                continue
            seen.add(key)
            name = f"rot{rotation_index * 90}{'_flip_h' if flipped else ''}"
            transforms.append((name, transformed))
        current = rotate_binary_template_90(current)
    return transforms

def colorize_binary_template(template: BinaryTemplate, zero_color: int, one_color: int) -> Grid:
    return [[zero_color if value == 0 else one_color for value in row] for row in template]

def subgrid_placements(subgrid: Grid, surface: Grid) -> list[Cell]:
    sub_height, sub_width = grid_shape(subgrid)
    surface_height, surface_width = grid_shape(surface)
    if sub_height == 0 or sub_width == 0 or sub_height > surface_height or sub_width > surface_width:
        return []
    placements: list[Cell] = []
    for row0 in range(surface_height - sub_height + 1):
        for col0 in range(surface_width - sub_width + 1):
            if all(
                subgrid[row][col] == surface[row0 + row][col0 + col]
                for row in range(sub_height)
                for col in range(sub_width)
            ):
                placements.append((row0, col0))
    return placements

def parse_dihedral_binary_template(value: Any) -> BinaryTemplate | None:
    if not isinstance(value, list) or not value:
        return None
    parsed: BinaryTemplate = []
    row_width: int | None = None
    for row in value:
        if not isinstance(row, list) or not row:
            return None
        parsed_row: list[int] = []
        for cell in row:
            if cell not in (0, 1):
                return None
            parsed_row.append(int(cell))
        if row_width is None:
            row_width = len(parsed_row)
        elif row_width != len(parsed_row):
            return None
        parsed.append(parsed_row)
    return parsed

def render_dihedral_binary_pattern_completion(
    grid: Grid,
    dihedral_binary_template: Any,
) -> tuple[Grid | None, dict[str, Any]]:
    template = parse_dihedral_binary_template(dihedral_binary_template)
    if template is None:
        return None, {"failure": "invalid_dihedral_binary_template"}
    template_height, template_width = grid_shape(template)
    if template_height != 20 or template_width != 20:
        return None, {
            "failure": "unsupported_dihedral_template_shape",
            "dihedral_template_shape": [template_height, template_width],
        }
    color_values = two_color_values(grid)
    if len(color_values) != 2:
        return None, {"failure": "dihedral_pattern_not_binary_input", "color_count": len(color_values)}

    candidates: list[dict[str, Any]] = []
    seen_surfaces: set[tuple[tuple[int, ...], ...]] = set()
    for transform_name, transformed in dihedral_binary_transforms(template):
        for zero_color, one_color in (tuple(color_values), tuple(reversed(color_values))):
            surface = colorize_binary_template(transformed, int(zero_color), int(one_color))
            placements = subgrid_placements(grid, surface)
            if not placements:
                continue
            key = tuple(tuple(row) for row in surface)
            if key in seen_surfaces:
                continue
            seen_surfaces.add(key)
            candidates.append(
                {
                    "transform": transform_name,
                    "zero_color": int(zero_color),
                    "one_color": int(one_color),
                    "placements": placements,
                    "surface": surface,
                }
            )

    if len(candidates) != 1:
        return None, {
            "failure": "dihedral_pattern_candidate_not_unique",
            "candidate_count": len(candidates),
            "candidate_summaries": [
                {
                    "transform": candidate["transform"],
                    "zero_color": candidate["zero_color"],
                    "one_color": candidate["one_color"],
                    "placement_count": len(candidate["placements"]),
                }
                for candidate in candidates[:8]
            ],
        }

    selected = candidates[0]
    output = selected["surface"]
    if output == grid:
        return None, {"failure": "identity_dihedral_pattern_completion"}
    observed_height, observed_width = grid_shape(grid)
    return output, {
        "renderer_case": "dihedral_binary_pattern_completion",
        "dihedral_template_shape": [template_height, template_width],
        "dihedral_transform": selected["transform"],
        "dihedral_zero_color": selected["zero_color"],
        "dihedral_one_color": selected["one_color"],
        "dihedral_placement_count": len(selected["placements"]),
        "dihedral_first_placement": list(selected["placements"][0]),
        "dihedral_observed_shape": [observed_height, observed_width],
        "dihedral_observed_cell_count": observed_height * observed_width,
        "dihedral_completed_cell_count": template_height * template_width - observed_height * observed_width,
    }

def infer_dihedral_binary_template_policy(
    train_pairs: list[dict[str, Grid]],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if len(train_pairs) < 2:
        return None, {"failure": "too_few_train_pairs_for_dihedral_binary_template"}
    output_shapes = [grid_shape(pair["output"]) for pair in train_pairs]
    if any(shape != (20, 20) for shape in output_shapes):
        return None, {"failure": "dihedral_outputs_not_20x20", "output_shapes": output_shapes}
    if any(len(two_color_values(pair["output"])) != 2 for pair in train_pairs):
        return None, {"failure": "dihedral_outputs_not_binary"}

    first_output = train_pairs[0]["output"]
    canonical_zero_color = dominant_background(first_output)
    template = binary_template_from_grid(first_output, canonical_zero_color)
    train_transform_counts: Counter[str] = Counter()
    train_placement_count = 0

    for train_index, pair in enumerate(train_pairs):
        input_colors = two_color_values(pair["input"])
        output_colors = two_color_values(pair["output"])
        if len(input_colors) != 2 or input_colors != output_colors:
            return None, {
                "failure": "dihedral_train_input_output_color_mismatch",
                "train_index": train_index,
                "input_colors": input_colors,
                "output_colors": output_colors,
            }
        matches: list[dict[str, Any]] = []
        for transform_name, transformed in dihedral_binary_transforms(template):
            for zero_color, one_color in (tuple(output_colors), tuple(reversed(output_colors))):
                surface = colorize_binary_template(transformed, int(zero_color), int(one_color))
                if surface != pair["output"]:
                    continue
                placements = subgrid_placements(pair["input"], surface)
                if not placements:
                    continue
                matches.append(
                    {
                        "transform": transform_name,
                        "zero_color": int(zero_color),
                        "one_color": int(one_color),
                        "placement_count": len(placements),
                    }
                )
        if len(matches) != 1:
            return None, {
                "failure": "dihedral_train_transform_not_unique",
                "train_index": train_index,
                "match_count": len(matches),
                "matches": matches[:8],
            }
        train_transform_counts[matches[0]["transform"]] += 1
        train_placement_count += int(matches[0]["placement_count"])

    return {
        "dihedral_binary_template": template,
        "dihedral_template_shape": [20, 20],
        "dihedral_template_one_count": sum(value for row in template for value in row),
        "dihedral_train_transform_counts": dict(sorted(train_transform_counts.items())),
        "dihedral_train_placement_count": train_placement_count,
    }, {}
