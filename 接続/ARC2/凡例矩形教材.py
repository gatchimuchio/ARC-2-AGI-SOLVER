"""Teacher-fitted opaque table/extent interpreter; no task identifiers or stored grids."""
from __future__ import annotations
from collections import Counter
from itertools import combinations

Point = tuple[int, int]
BBox = tuple[int, int, int, int]
PROGRAMS = tuple(
    (priority, preservation, null_colour, action)
    for priority in ("FIRST", "LAST")
    for preservation in ("NONE", "ALL_SOURCE", "WHOLE_L3_COMPONENTS")
    for null_colour, action in ((None, "LITERAL"),) + tuple(
        (colour, action) for colour in range(10)
        for action in ("RESET_BACKGROUND", "KEEP_ORIGINAL_INPUT")))

def point_list(points: set[Point] | list[Point]) -> list[list[int]]:
    return [list(p) for p in sorted(points)]

def bbox(points: set[Point]) -> BBox:
    return (min(r for r, _ in points), min(c for _, c in points),
            max(r for r, _ in points), max(c for _, c in points))

def bbox_cells(box: BBox) -> set[Point]:
    t, l, b, r = box
    return {(y, x) for y in range(t, b + 1) for x in range(l, r + 1)}

def c4_components(points: set[Point]) -> list[set[Point]]:
    remaining = set(points)
    result = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        component = {start}
        pending = [start]
        while pending:
            r, c = pending.pop()
            for q in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
                if q in remaining:
                    remaining.remove(q)
                    component.add(q)
                    pending.append(q)
        result.append(component)
    return result

def strict_arc_grid_errors(grid: object) -> list[str]:
    errors = []
    if type(grid) is not list or not grid:
        return ["grid_must_be_nonempty_list"]
    if not 1 <= len(grid) <= 30:
        errors.append("height_outside_1_to_30")
    if any(type(row) is not list or not row for row in grid):
        return errors + ["every_row_must_be_nonempty_list"]
    widths = [len(row) for row in grid]
    if len(set(widths)) != 1:
        errors.append("nonrectangular_grid")
    if any(not 1 <= width <= 30 for width in widths):
        errors.append("width_outside_1_to_30")
    if any(type(value) is not int or not 0 <= value <= 9
           for row in grid for value in row):
        errors.append("cell_not_exact_integer_0_to_9")
    return errors

def component_record(component: set[Point], grid: list[list[int]], bg: int,
                     index: int) -> dict:
    box = bbox(component)
    t, l, b, r = box
    rect = bbox_cells(box)
    visible_left = [grid[y][l] for y in range(t, b + 1)]
    bbox_fg = {p for p in rect if grid[p[0]][p[1]] != bg}
    checks = {
        "whole_maximal_colour_agnostic_C4_component": True,
        "positive_row_count": b >= t,
        "visible_bbox_width_exactly_two": r - l + 1 == 2,
        "every_left_column_cell_nonbackground": all(v != bg for v in visible_left),
        "left_column_keys_pairwise_distinct": len(visible_left) == len(set(visible_left)),
        "component_equals_all_nonbackground_cells_in_its_bbox": component == bbox_fg,
    }
    failures = [name for name, passed in checks.items() if not passed]
    record = {
        "component_id": index,
        "cells": point_list(component),
        "cell_count": len(component),
        "bbox": list(box),
        "bbox_shape": [b - t + 1, r - l + 1],
        "colours": sorted({grid[y][x] for y, x in component}),
        "monochrome": len({grid[y][x] for y, x in component}) == 1,
        "bbox_values": [[grid[y][x] for x in range(l, r + 1)]
                        for y in range(t, b + 1)],
        "left_column_values": visible_left,
        "other_foreground_cells_in_bbox": point_list(bbox_fg - component),
        "raw_table_checks": checks,
        "raw_table_candidate": not failures,
        "raw_table_failure_reasons": failures,
    }
    if r - l + 1 == 2:
        record["right_column_values"] = [grid[y][r] for y in range(t, b + 1)]
    return record

def source_geometry(colour: int, cells: set[Point]) -> dict:
    """Evaluate both source types without any table map or teacher output."""
    box = bbox(cells)
    t, l, b, r = box
    rect = bbox_cells(box)
    components = c4_components(cells)
    rectangle_checks = {
        "exactly_one_whole_monochrome_C4_component": len(components) == 1,
        "whole_colour_support_fills_its_bbox": cells == rect,
    }
    corner_pair_definitions = [
        ("TL+BR", {(t, l), (t + 1, l), (t, l + 1)},
         {(b, r), (b - 1, r), (b, r - 1)}),
        ("TR+BL", {(t, r), (t + 1, r), (t, r - 1)},
         {(b, l), (b - 1, l), (b, l + 1)}),
    ]
    corner_pairs = []
    dimensions_valid = b - t + 1 >= 2 and r - l + 1 >= 2
    for name, a, z in corner_pair_definitions:
        expected = a | z
        geometric_match = dimensions_valid and cells == expected
        physical_match = (geometric_match and len(components) == 2
                          and all(len(c) == 3 for c in components)
                          and {frozenset(c) for c in components}
                          == {frozenset(a), frozenset(z)})
        checks = {
            "whole_colour_bbox_has_both_dimensions_at_least_two": dimensions_valid,
            "whole_colour_support_equals_corner_pair_union": cells == expected,
            "exactly_two_whole_monochrome_C4_components": len(components) == 2,
            "all_whole_components_have_three_cells": all(len(c) == 3 for c in components),
            "whole_components_are_the_two_declared_inward_Ls": (
                len(components) == 2
                and {frozenset(c) for c in components} == {frozenset(a), frozenset(z)}),
        }
        corner_pairs.append({
            "opposite_corners": name,
            "corner_L_cells": [point_list(a), point_list(z)],
            "expected_union_cells": point_list(expected),
            "corner_L_overlap_cells": point_list(a & z),
            "missing_support_cells": point_list(expected - cells),
            "extra_support_cells": point_list(cells - expected),
            "geometric_union_match": geometric_match,
            "two_whole_three_cell_inward_L_source_match": physical_match,
            "checks": checks,
            "failure_reasons": [k for k, passed in checks.items() if not passed],
        })
    rectangle_match = all(rectangle_checks.values())
    two_l_match = any(p["two_whole_three_cell_inward_L_source_match"] for p in corner_pairs)
    kinds = (["filled_rectangle"] if rectangle_match else []) + (
        ["two_whole_three_cell_inward_Ls"] if two_l_match else [])
    return {
        "colour": colour,
        "cells": point_list(cells),
        "cell_count": len(cells),
        "bbox": list(box),
        "bbox_shape": [b - t + 1, r - l + 1],
        "monochrome_C4_component_count": len(components),
        "monochrome_C4_components": [
            {"component_id": i, "cells": point_list(c), "cell_count": len(c),
             "bbox": list(bbox(c))}
            for i, c in enumerate(components)
        ],
        "rectangle_checks": rectangle_checks,
        "rectangle_failure_reasons": [k for k, passed in rectangle_checks.items() if not passed],
        "filled_rectangle_match": rectangle_match,
        "missing_cells_to_fill_bbox": point_list(rect - cells),
        "all_geometric_corner_explanations": corner_pairs,
        "matching_geometric_corner_explanations": [
            p["opposite_corners"] for p in corner_pairs if p["geometric_union_match"]],
        "matching_two_component_corner_explanations": [
            p["opposite_corners"] for p in corner_pairs
            if p["two_whole_three_cell_inward_L_source_match"]],
        "two_whole_three_cell_inward_L_source_match": two_l_match,
        "matching_source_kinds": kinds,
        "source_geometry_valid": bool(kinds),
        "source_geometry_failure_reasons": [] if kinds else [
            "neither_one_filled_rectangle_nor_exactly_two_whole_three_cell_inward_L_components"],
    }

def raw_inventory(grid: object) -> dict:
    errors = strict_arc_grid_errors(grid)
    record = {
        "strict_arc_grid": not errors,
        "strict_arc_grid_failure_reasons": errors,
        "raw_foreground_components": [],
        "raw_table_candidate_component_ids": [],
        "raw_table_candidate_count": 0,
        "source_typing_performed": False,
        "complete_input_interpretation_count": 0,
        "complete_input_interpretation": False,
    }
    if errors:
        record["interpretation_failure_reasons"] = ["strict_arc_grid_failed"]
        return record
    h, w = len(grid), len(grid[0])
    record["shape"] = [h, w]
    counts = Counter(value for row in grid for value in row)
    maximum = max(counts.values())
    modes = sorted(value for value, count in counts.items() if count == maximum)
    record["background_derivation"] = {
        "colour_histogram": dict(sorted(counts.items())),
        "modal_count": maximum,
        "modal_values": modes,
        "unique_mode": len(modes) == 1,
    }
    if len(modes) != 1:
        record["interpretation_failure_reasons"] = ["background_not_unique_mode"]
        return record
    bg = modes[0]
    record["background_derivation"]["background"] = bg
    foreground = {(r, c) for r in range(h) for c in range(w) if grid[r][c] != bg}
    components = c4_components(foreground)
    raw = [component_record(component, grid, bg, i)
           for i, component in enumerate(components)]
    candidates = [c for c in raw if c["raw_table_candidate"]]
    record.update({
        "foreground_cell_count": len(foreground),
        "raw_foreground_component_count": len(components),
        "raw_foreground_components": raw,
        "raw_components_partition_all_foreground": (
            set().union(*components) == foreground
            and sum(map(len, components)) == len(foreground)),
        "raw_table_candidate_component_ids": [c["component_id"] for c in candidates],
        "raw_table_candidate_count": len(candidates),
        "failed_raw_table_component_count": len(raw) - len(candidates),
    })
    if len(candidates) != 1:
        record["interpretation_failure_reasons"] = ["raw_table_candidate_count_is_not_one"]
        record["source_typing_not_performed_reason"] = "requires_exactly_one_raw_table_before_source_typing"
        return record
    table = candidates[0]
    table_box = tuple(table["bbox"])
    table_cells = bbox_cells(table_box)
    outside = foreground - table_cells
    groups = {colour: {p for p in outside if grid[p[0]][p[1]] == colour}
              for colour in sorted({grid[r][c] for r, c in outside})}
    # Both geometric types are evaluated for ALL colours before map lookup.
    sources = [source_geometry(colour, cells) for colour, cells in groups.items()]
    t, l, b, r = table_box
    rows = [{"row_index": y - t, "grid_row": y, "key": grid[y][l],
             "value": grid[y][r], "value_is_background": grid[y][r] == bg,
             "self_map": grid[y][l] == grid[y][r]} for y in range(t, b + 1)]
    mapping = {row["key"]: row["value"] for row in rows}
    for source in sources:
        source_cells = {tuple(p) for p in source["cells"]}
        source_box_cells = bbox_cells(tuple(source["bbox"]))
        collision = source_box_cells & table_cells
        source.update({
            "mapped_by_table_key": source["colour"] in mapping,
            "table_value": mapping.get(source["colour"]),
            "source_bbox_intersects_table_bbox": bool(collision),
            "source_bbox_table_intersection_cells": point_list(collision),
            "all_colour_cells_outside_table_used": source_cells == groups[source["colour"]],
        })
    pairwise = []
    for a, z in combinations(sources, 2):
        overlap = bbox_cells(tuple(a["bbox"])) & bbox_cells(tuple(z["bbox"]))
        pairwise.append({
            "colours": [a["colour"], z["colour"]],
            "mapped_status": [a["mapped_by_table_key"], z["mapped_by_table_key"]],
            "bbox_intersection_cells": point_list(overlap),
            "bbox_intersection_count": len(overlap),
            "bboxes_overlap": bool(overlap),
            "used_as_rejection_criterion": False,
        })
    failed_geometry = [s["colour"] for s in sources if not s["source_geometry_valid"]]
    table_intersections = [s["colour"] for s in sources if s["source_bbox_intersects_table_bbox"]]
    failures = []
    if failed_geometry:
        failures.append("one_or_more_remaining_colours_fail_both_source_types")
    if table_intersections:
        failures.append("one_or_more_source_bboxes_intersect_table_bbox")
    record.update({
        "source_typing_performed": True,
        "unique_raw_table": {
            "component_id": table["component_id"], "bbox": list(table_box),
            "full_table_bbox_cells": point_list(table_cells),
            "rows_top_to_bottom": rows,
            "right_column_values_unrestricted": True,
        },
        "remaining_foreground_cells_outside_full_table_bbox": point_list(outside),
        "remaining_foreground_colours": sorted(groups),
        "sources": sources,
        "source_count": len(sources),
        "source_groups_partition_all_remaining_foreground": (
            set().union(*(set(map(tuple, s["cells"])) for s in sources)) == outside
            and sum(s["cell_count"] for s in sources) == len(outside)),
        "all_remaining_colours_typed_without_local_skip": len(sources) == len(groups),
        "failed_source_geometry_colours": failed_geometry,
        "source_bbox_table_intersection_colours": table_intersections,
        "mapped_source_colours": [s["colour"] for s in sources if s["mapped_by_table_key"]],
        "unmapped_source_colours": [s["colour"] for s in sources if not s["mapped_by_table_key"]],
        "unused_table_keys": [row["key"] for row in rows if row["key"] not in groups],
        "all_pairwise_source_bbox_overlaps_including_empty": pairwise,
        "complete_input_interpretation": not failures,
        "complete_input_interpretation_count": int(not failures),
        "interpretation_failure_reasons": failures,
    })
    return record


def parse_input(grid):
    record = raw_inventory(grid)
    if not record['complete_input_interpretation']:
        return None, record
    rows = record['unique_raw_table']['rows_top_to_bottom']
    row_by_key = {row['key']: row for row in rows}
    sources = []
    for source in record['sources']:
        annotations = set()
        for component in source['monochrome_C4_components']:
            t, l, b, r = component['bbox']
            if component['cell_count'] == 3 and b - t == 1 and r - l == 1:
                annotations.update(map(tuple, component['cells']))
        key = source['colour']
        sources.append({
            'colour': key,
            'cells': frozenset(map(tuple, source['cells'])),
            'bbox': tuple(source['bbox']),
            'bbox_cells': frozenset(bbox_cells(tuple(source['bbox']))),
            'annotations': frozenset(annotations),
            'mapped': key in row_by_key,
            'row_index': row_by_key[key]['row_index'] if key in row_by_key else None,
            'value': row_by_key[key]['value'] if key in row_by_key else None,
        })
    payload = {
        'grid': tuple(tuple(row) for row in grid),
        'background': record['background_derivation']['background'],
        'table_cells': frozenset(map(tuple, record['unique_raw_table']['full_table_bbox_cells'])),
        'sources': tuple(sources),
    }
    return payload, record


def valid_program(program):
    return (type(program) is tuple and len(program) == 4
            and program[0] in ('FIRST', 'LAST')
            and program[1] in ('NONE', 'ALL_SOURCE', 'WHOLE_L3_COMPONENTS')
            and ((program[2] is None and program[3] == 'LITERAL')
                 or (type(program[2]) is int and 0 <= program[2] <= 9
                     and program[3] in ('RESET_BACKGROUND', 'KEEP_ORIGINAL_INPUT'))))


def render_program(payload, program):
    if not valid_program(program):
        return None, {'failure': 'invalid_program'}
    priority, preservation, null_colour, null_action = program
    original = payload['grid']
    h, w = len(original), len(original[0])
    output = [list(row) for row in original]
    mapped = sorted((s for s in payload['sources'] if s['mapped']),
                    key=lambda s: s['row_index'], reverse=priority == 'LAST')
    owners = [[None for _ in range(w)] for _ in range(h)]
    action_cells = {'preserve_source': [], 'literal': [],
                    'reset_background': [], 'keep_original_input': []}
    layer_counts = {s['colour']: {'won': 0, 'preserved_source': 0, 'body': 0}
                    for s in mapped}
    for r in range(h):
        for c in range(w):
            p = (r, c)
            covering = [s for s in mapped if p in s['bbox_cells']]
            if not covering:
                continue
            winner = covering[0]
            colour = winner['colour']
            owners[r][c] = colour
            layer_counts[colour]['won'] += 1
            preserve = ((preservation == 'ALL_SOURCE' and p in winner['cells'])
                        or (preservation == 'WHOLE_L3_COMPONENTS' and p in winner['annotations']))
            if preserve:
                value = colour
                action = 'preserve_source'
                layer_counts[colour]['preserved_source'] += 1
            else:
                layer_counts[colour]['body'] += 1
                if null_colour is not None and winner['value'] == null_colour:
                    if null_action == 'RESET_BACKGROUND':
                        value = payload['background']
                        action = 'reset_background'
                    else:
                        value = original[r][c]
                        action = 'keep_original_input'
                else:
                    value = winner['value']
                    action = 'literal'
            output[r][c] = value
            action_cells[action].append([r, c])
    protected = set().union(*(s['bbox_cells'] for s in payload['sources'] if not s['mapped']))
    violations = [[r, c] for r, c in sorted(protected) if output[r][c] != original[r][c]]
    changed = [[r, c] for r in range(h) for c in range(w) if output[r][c] != original[r][c]]
    record = {
        'program': list(program),
        'shape': [h, w],
        'winner_colours': owners,
        'actions': action_cells,
        'layer_counts': layer_counts,
        'mapped_union_cell_count': sum(v['won'] for v in layer_counts.values()),
        'unmapped_protected_cells': point_list(protected),
        'unmapped_protection_violations': violations,
        'table_preserved': all(output[r][c] == original[r][c] for r, c in payload['table_cells']),
        'outside_mapped_union_preserved': all(output[r][c] == original[r][c]
                                             for r in range(h) for c in range(w)
                                             if owners[r][c] is None),
        'changed_cells': changed,
        'changed_cell_count': len(changed),
        'input_colour_counts': dict(sorted(Counter(v for row in original for v in row).items())),
        'output_colour_counts': dict(sorted(Counter(v for row in output for v in row).items())),
    }
    if violations:
        return None, {**record, 'failure': 'unmapped_bbox_would_change'}
    return output, record


def fit_teachers(teachers):
    if (not isinstance(teachers, (list, tuple)) or not teachers
            or any(not isinstance(pair, dict) or 'input' not in pair or 'output' not in pair
                   for pair in teachers)):
        return None, {'failure': 'invalid_teachers'}
    parsed = [parse_input(pair['input']) for pair in teachers]
    input_records = [record for payload, record in parsed]
    if any(payload is None for payload, record in parsed):
        return None, {'failure': 'teacher_input_not_interpretable', 'input_records': input_records,
                      'programs_explored': 0}
    distinct = len({payload['grid'] for payload, record in parsed})
    if distinct < 2:
        return None, {'failure': 'requires_two_distinct_teacher_inputs',
                      'input_records': input_records, 'distinct_inputs': distinct,
                      'programs_explored': 0}
    target_errors = [strict_arc_grid_errors(pair['output']) for pair in teachers]
    if any(target_errors):
        return None, {'failure': 'invalid_teacher_target', 'input_records': input_records,
                      'target_errors': target_errors, 'programs_explored': 0}
    models = []
    comparisons = []
    try:
        for program in PROGRAMS:
            rendered = [render_program(payload, program) for payload, record in parsed]
            equal = [out is not None and out == pair['output']
                     for (out, record), pair in zip(rendered, teachers)]
            comparisons.append({'program': list(program), 'teacher_equal': equal,
                                'render_records': [record for out, record in rendered]})
            if all(equal):
                models.append(program)
    except Exception as error:
        return None, {'failure': 'program_comparison_incomplete', 'error_type': type(error).__name__,
                      'input_records': input_records, 'completed_programs': len(comparisons),
                      'partial_models_discarded': True}
    record = {'input_records': input_records, 'distinct_inputs': distinct,
              'programs_explored': len(comparisons), 'program_comparisons': comparisons,
              'model_count': len(models), 'models': [list(p) for p in models],
              'complete': len(comparisons) == len(PROGRAMS)}
    if not models:
        return None, {**record, 'failure': 'no_shared_program'}
    return tuple(models), record


def predict(grid, models):
    if (not isinstance(models, tuple) or not models
            or any(not valid_program(program) for program in models)
            or len(set(models)) != len(models)):
        return None, {'failure': 'invalid_retained_programs'}
    payload, input_record = parse_input(grid)
    if payload is None:
        return None, {'failure': 'input_not_interpretable', 'input_record': input_record}
    try:
        rendered = [render_program(payload, program) for program in models]
    except Exception as error:
        return None, {'failure': 'prediction_incomplete', 'error_type': type(error).__name__,
                      'input_record': input_record, 'partial_answers_discarded': True}
    record = {'input_record': input_record, 'models': [list(p) for p in models],
              'render_records': [rec for out, rec in rendered],
              'model_count': len(models), 'all_models_evaluated': True}
    if any(out is None for out, rec in rendered):
        return None, {**record, 'failure': 'retained_program_failed'}
    if any(out != rendered[0][0] for out, rec in rendered):
        return None, {**record, 'failure': 'retained_program_grids_disagree'}
    return rendered[0][0], {**record, 'all_program_grids_agree': True}


class 凡例矩形教材:
    def __init__(self, 教師群):
        self.共有規則, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.共有規則 is None:
            return None, {"failure": "全教師を再現する凡例矩形規則なし"}
        return predict(格子, self.共有規則)

    def 記録(self):
        return {"適合": self.共有規則 is not None, "共有規則": self.共有規則}
