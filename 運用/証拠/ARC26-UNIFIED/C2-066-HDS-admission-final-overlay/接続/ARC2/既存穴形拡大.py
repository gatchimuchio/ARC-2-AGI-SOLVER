"""旧ARCの穴形状と拡大glyph対応をそのまま再利用する。
出典: ARC-Layer-0-Functional-Compliance@454670a1 / arc2_runtime_program_search。
5関数は原文のまま。shape/backgroundの2関数は既採用の同一定義を共有。
"""
from __future__ import annotations
from typing import Any
from .既存領域転写 import Grid
from .既存穴充填 import _grid_shape,_dominant_color

def _hole_scale_components(
    grid: Grid,
    color: int,
    excluded_bbox: tuple[int, int, int, int] | None = None,
) -> list[set[tuple[int, int]]]:
    height, width = _grid_shape(grid)
    remaining = {
        (row, col)
        for row in range(height)
        for col in range(width)
        if int(grid[row][col]) == int(color)
        and not (
            excluded_bbox is not None
            and excluded_bbox[0] <= row <= excluded_bbox[2]
            and excluded_bbox[1] <= col <= excluded_bbox[3]
        )
    }
    components: list[set[tuple[int, int]]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = [start]
        component = {start}
        while queue:
            row, col = queue.pop()
            for row_delta, col_delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor = (row + row_delta, col + col_delta)
                if neighbor not in remaining:
                    continue
                remaining.remove(neighbor)
                component.add(neighbor)
                queue.append(neighbor)
        components.append(component)
    return components

def _hole_scale_bbox(cells: set[tuple[int, int]]) -> tuple[int, int, int, int]:
    rows = [row for row, _col in cells]
    cols = [col for _row, col in cells]
    return min(rows), min(cols), max(rows), max(cols)

def _hole_scale_shape_variants(
    cells: set[tuple[int, int]],
) -> set[tuple[tuple[int, int], ...]]:
    row0, col0, row1, col1 = _hole_scale_bbox(cells)
    height = row1 - row0 + 1
    width = col1 - col0 + 1
    local = {(row - row0, col - col0) for row, col in cells}
    variants: set[tuple[tuple[int, int], ...]] = set()
    for rotation in range(4):
        for reflect in (False, True):
            transformed: set[tuple[int, int]] = set()
            for row, col in local:
                next_row, next_col = row, col
                current_height, current_width = height, width
                for _ in range(rotation):
                    next_row, next_col = next_col, current_height - 1 - next_row
                    current_height, current_width = current_width, current_height
                if reflect:
                    next_col = current_width - 1 - next_col
                transformed.add((next_row, next_col))
            min_row = min(row for row, _col in transformed)
            min_col = min(col for _row, col in transformed)
            normalized = tuple(sorted(
                (row - min_row, col - min_col)
                for row, col in transformed
            ))
            variants.add(normalized)
    return variants

def _hole_scale_map_candidate(
    grid: Grid,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    height, width = _grid_shape(grid)
    if height < 6 or width < 6 or any(len(row) != width for row in grid):
        return None, {"failure": "hole_scale_invalid_grid"}
    background = _dominant_color(grid)
    if background is None:
        return None, {"failure": "hole_scale_missing_background"}
    colors = sorted({int(value) for row in grid for value in row if int(value) != background})
    components_by_color = {
        color: _hole_scale_components(grid, color)
        for color in colors
    }
    map_candidates: list[tuple[int, int, int, set[tuple[int, int]]]] = []
    for color, components in components_by_color.items():
        for component in components:
            row0, col0, row1, col1 = _hole_scale_bbox(component)
            box_area = (row1 - row0 + 1) * (col1 - col0 + 1)
            if box_area < 16:
                continue
            hole_count = sum(
                int(grid[row][col]) == int(background)
                for row in range(row0, row1 + 1)
                for col in range(col0, col1 + 1)
            )
            if hole_count < 2:
                continue
            map_candidates.append((box_area, len(component), color, component))
    if not map_candidates:
        return None, {"failure": "hole_scale_missing_container_map"}
    map_candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    _box_area, _component_size, map_color, map_component = map_candidates[0]
    map_bbox = _hole_scale_bbox(map_component)
    map_row0, map_col0, map_row1, map_col1 = map_bbox
    map_height = map_row1 - map_row0 + 1
    map_width = map_col1 - map_col0 + 1

    holes = {
        (row, col)
        for row in range(map_row0, map_row1 + 1)
        for col in range(map_col0, map_col1 + 1)
        if int(grid[row][col]) == int(background)
    }
    hole_components: list[set[tuple[int, int]]] = []
    while holes:
        start = min(holes)
        holes.remove(start)
        queue = [start]
        component = {start}
        while queue:
            row, col = queue.pop()
            for row_delta, col_delta in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbor = (row + row_delta, col + col_delta)
                if neighbor not in holes:
                    continue
                holes.remove(neighbor)
                component.add(neighbor)
                queue.append(neighbor)
        if not (
            any(row == map_row0 or row == map_row1 for row, _col in component)
            or any(col == map_col0 or col == map_col1 for _row, col in component)
        ):
            hole_components.append(component)
    if not hole_components:
        return None, {"failure": "hole_scale_missing_internal_holes"}

    template_candidates_by_scale: dict[int, dict[tuple[tuple[int, int], ...], int]] = {}
    for scale in range(2, 7):
        templates: dict[tuple[tuple[int, int], ...], int] = {}
        valid_template_count = 0
        scale_conflict = False
        for color, components in components_by_color.items():
            for component in components:
                component_bbox = _hole_scale_bbox(component)
                if (
                    component_bbox[0] >= map_bbox[0]
                    and component_bbox[2] <= map_bbox[2]
                    and component_bbox[1] >= map_bbox[1]
                    and component_bbox[3] <= map_bbox[3]
                ):
                    continue
                component_height = component_bbox[2] - component_bbox[0] + 1
                component_width = component_bbox[3] - component_bbox[1] + 1
                if len(component) < scale * scale:
                    continue
                if component_height % scale or component_width % scale:
                    continue
                block_mask: set[tuple[int, int]] = set()
                complete = True
                for block_row in range(component_height // scale):
                    for block_col in range(component_width // scale):
                        block_cells = {
                            (row, col)
                            for row in range(
                                component_bbox[0] + block_row * scale,
                                component_bbox[0] + (block_row + 1) * scale,
                            )
                            for col in range(
                                component_bbox[1] + block_col * scale,
                                component_bbox[1] + (block_col + 1) * scale,
                            )
                        }
                        occupied = block_cells & component
                        if occupied and len(occupied) != scale * scale:
                            complete = False
                            break
                        if occupied:
                            block_mask.add((block_row, block_col))
                    if not complete:
                        break
                if not complete or not block_mask:
                    continue
                normalized = min(_hole_scale_shape_variants(block_mask))
                previous_color = templates.get(normalized)
                if previous_color is not None and previous_color != color:
                    scale_conflict = True
                    break
                templates[normalized] = int(color)
                valid_template_count += 1
            if scale_conflict:
                break
        if not scale_conflict and valid_template_count >= 2:
            template_candidates_by_scale[scale] = templates
    if not template_candidates_by_scale:
        return None, {"failure": "hole_scale_missing_block_complete_templates"}

    render_candidates: list[tuple[int, dict[str, Any]]] = []
    for scale, templates in sorted(template_candidates_by_scale.items()):
        assignments: dict[tuple[int, int], int] = {}
        valid = True
        for component in hole_components:
            local = {
                (row - map_row0, col - map_col0)
                for row, col in component
            }
            normalized = min(_hole_scale_shape_variants(local))
            matched = templates.get(normalized)
            if matched is None:
                valid = False
                break
            for cell in component:
                assignments[cell] = int(matched)
        if not valid:
            continue
        output = [
            [int(map_color) for _ in range(map_width * scale)]
            for _ in range(map_height * scale)
        ]
        for (row, col), output_color in assignments.items():
            row0 = (row - map_row0) * scale
            col0 = (col - map_col0) * scale
            for row_delta in range(scale):
                for col_delta in range(scale):
                    output[row0 + row_delta][col0 + col_delta] = output_color
        render_candidates.append((scale, {
            "background": int(background),
            "map_color": int(map_color),
            "map_bbox": list(map_bbox),
            "scale": int(scale),
            "template_count": len(templates),
            "hole_component_count": len(hole_components),
            "assignments": assignments,
            "output": output,
        }))
    if len(render_candidates) != 1:
        return None, {
            "failure": "hole_scale_render_candidate_not_unique",
            "hole_scale_candidate_scales": [scale for scale, _candidate in render_candidates],
            "hole_scale_template_scales": sorted(template_candidates_by_scale),
            "hole_scale_hole_shapes": [
                min(_hole_scale_shape_variants({
                    (row - map_row0, col - map_col0)
                    for row, col in component
                }))
                for component in hole_components
            ],
            "hole_scale_template_shapes": {
                str(scale): [list(shape) for shape in templates]
                for scale, templates in template_candidates_by_scale.items()
            },
        }
    return render_candidates[0][1], {}

def _hole_scale_render(grid: Grid) -> tuple[Grid | None, dict[str, Any]]:
    policy, rejection = _hole_scale_map_candidate(grid)
    if policy is None:
        return None, rejection
    output = policy.pop("output")
    if output == grid:
        return None, {"failure": "hole_scale_identity_render"}
    return output, {
        "renderer_case": "hole_shape_scale_composer",
        "hole_scale_background_color": int(policy["background"]),
        "hole_scale_map_color": int(policy["map_color"]),
        "hole_scale_map_bbox": policy["map_bbox"],
        "hole_scale_factor": int(policy["scale"]),
        "hole_scale_template_count": int(policy["template_count"]),
        "hole_scale_hole_component_count": int(policy["hole_component_count"]),
        "hole_scale_assignment_count": len(policy["assignments"]),
        "hole_scale_output_shape": list(_grid_shape(output)),
        "hole_scale_event_count": sum(
            1
            for row in output
            for value in row
            if int(value) != int(policy["map_color"])
        ),
    }
