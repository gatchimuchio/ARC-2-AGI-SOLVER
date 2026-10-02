"""Certify every original marker-translation candidate without ranking alternatives."""
from . import 既存標識組立 as old


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))


def guarded_render(grid, colors):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    if (not isinstance(colors, dict) or set(colors) != {'marker', 'target', 'background'}
            or any(type(v) is not int or not 0 <= v <= 9 for v in colors.values())
            or len(set(colors.values())) != 3):
        return None, {'failure': 'invalid_roles'}
    if {v for row in grid for v in row} - set(colors.values()):
        return None, {'failure': 'unknown_input_color'}
    marker, target, background = (colors[k] for k in ('marker', 'target', 'background'))
    markers = old.same_color_components(grid, marker)
    targets = old.same_color_components(grid, target)
    if len(markers) != 2 or len(targets) < 2:
        return None, {'failure': 'marker_or_target_component_count_out_of_scope'}
    normalized = [{(r - m['bbox'][0], c - m['bbox'][1]) for r, c in m['cells']} for m in markers]
    if normalized[0] != normalized[1]:
        return None, {'failure': 'marker_shapes_differ'}
    all_target = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == target}
    source_union = set().union(*(c['cells'] for c in targets))
    if source_union != all_target or sum(c['size'] for c in targets) != len(all_target):
        return None, {'failure': 'target_coverage_incomplete_or_overlapping'}
    candidates = old.marker_guided_assembly_candidates(grid, colors)
    if not candidates:
        return None, {'failure': 'no_raw_candidate'}
    outputs, records = [], []
    for candidate in candidates:
        rec = candidate['record']
        source_index, dest_index = rec['source_marker_index'], rec['dest_marker_index']
        if {source_index, dest_index} != {0, 1}:
            return None, {'failure': 'invalid_marker_pair'}
        source, dest = markers[source_index], markers[dest_index]
        dr, dc = rec['attachment_direction']
        if (dr, dc) not in old.NEIGHBORS_4:
            return None, {'failure': 'invalid_attachment_direction'}
        attached = {(r + dr, c + dc) for r, c in source['cells']}
        if not attached <= all_target:
            return None, {'failure': 'incomplete_attached_target_footprint'}
        vr, vc = rec['translation_vector']
        if (vr, vc) != (dest['bbox'][0] - source['bbox'][0] - dr,
                        dest['bbox'][1] - source['bbox'][1] - dc):
            return None, {'failure': 'translation_not_marker_derived'}
        if abs(vr) == abs(vc):
            return None, {'failure': 'dominant_translation_axis_tie'}
        if {(r + vr, c + vc) for r, c in attached} != dest['cells']:
            return None, {'failure': 'destination_marker_footprint_mismatch'}
        moving, fixed = rec['moving_component_indices'], rec['fixed_component_indices']
        if (not moving or not fixed or len(set(moving)) != len(moving)
                or len(set(fixed)) != len(fixed) or set(moving) & set(fixed)
                or set(moving) | set(fixed) != set(range(len(targets)))):
            return None, {'failure': 'target_partition_incomplete_or_overlapping'}
        expected_moving = set()
        for index, component in enumerate(targets):
            top, left, bottom, right = component['bbox']
            include = bool(component['cells'] & attached)
            if not include:
                if abs(vc) > abs(vr):
                    include = (vc < 0 and left >= source['bbox'][1]) or (vc > 0 and right <= source['bbox'][3])
                else:
                    include = (vr < 0 and top >= source['bbox'][0]) or (vr > 0 and bottom <= source['bbox'][2])
            if include:
                expected_moving.add(index)
        if set(moving) != expected_moving:
            return None, {'failure': 'source_grouping_prior_disagrees'}
        assembled = set()
        for index, component in enumerate(targets):
            cells = ({(r + vr, c + vc) for r, c in component['cells']}
                     if index in expected_moving else set(component['cells']))
            if assembled & cells:
                return None, {'failure': 'target_pixels_overlap'}
            assembled.update(cells)
        if len(assembled) != len(all_target):
            return None, {'failure': 'target_pixel_count_changed'}
        top, left, bottom, right = old.component_bbox(assembled)
        if not (1 <= bottom - top + 1 <= 30 and 1 <= right - left + 1 <= 30):
            return None, {'failure': 'raw_candidate_out_of_arc_bounds'}
        expected = [[target if (r, c) in assembled else background for c in range(left, right + 1)]
                    for r in range(top, bottom + 1)]
        if (candidate['output'] != expected or rec['output_bbox'] != [top, left, bottom, right]
                or rec['output_shape'] != [len(expected), len(expected[0])]):
            return None, {'failure': 'raw_candidate_render_disagrees'}
        outputs.append(candidate['output'])
        records.append(rec)
    if any(output != outputs[0] for output in outputs[1:]):
        return None, {'failure': 'raw_candidate_grids_disagree', 'candidate_count': len(outputs)}
    output, source_records = old.marker_guided_foreground_component_assembly(grid, colors)
    if output != outputs[0] or not source_records:
        return None, {'failure': 'source_output_disagrees'}
    return output, {'source_records': source_records, 'certificate': {
        'raw_candidates': len(outputs), 'distinct_raw_grids': 1,
        'target_components': len(targets), 'target_pixels': len(all_target),
        'all_candidate_records': records,
    }}


def fit_guarded(teachers):
    if not teachers or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return None
    colors = old.infer_marker_target_background({'train': teachers})
    if colors is None:
        return None
    if not all(old.marker_guided_foreground_component_assembly(p['input'], colors)[0] == p['output'] for p in teachers):
        return None
    if not all(guarded_render(p['input'], colors)[0] == p['output'] for p in teachers):
        return None
    return colors


class 標識組立教材:
    def __init__(self, 教師群):
        self.役割 = fit_guarded(教師群)

    def 候補(self, 格子, _policy):
        if self.役割 is None:
            return None, {'failure': '全教師を再現する標識組立なし'}
        return guarded_render(格子, self.役割)

    def 記録(self):
        return {'全教師再現': self.役割 is not None, '教師由来役割': self.役割}
