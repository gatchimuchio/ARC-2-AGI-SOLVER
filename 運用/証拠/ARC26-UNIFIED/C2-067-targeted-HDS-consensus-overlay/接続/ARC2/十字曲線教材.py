"""Current-task pitch/hand fitting for an infinite curve cropped by a proof bound."""
from collections import Counter

DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))
MODELS = tuple((pitch, hand) for pitch in tuple(range(1, 30)) + ('GE30',)
               for hand in ('CW', 'CCW'))


def observe_input(grid):
    shape = [len(grid), len(grid[0])] if isinstance(grid, list) and grid and isinstance(grid[0], list) else None
    result = {'shape': shape, 'raw_roles': []}
    if (not isinstance(grid, list) or not grid or
            not isinstance(grid[0], list) or not grid[0] or
            any(not isinstance(row, list) or len(row) != len(grid[0]) for row in grid) or
            any(not isinstance(cell, int) or isinstance(cell, bool) or not 0 <= cell <= 9
                for row in grid for cell in row)):
        result['failure'] = 'invalid_grid'
        return result
    counts = Counter(cell for row in grid for cell in row)
    modes = sorted(color for color, count in counts.items() if count == max(counts.values()))
    result.update(colour_counts=dict(sorted(counts.items())), background_candidates=modes)
    if len(modes) != 1:
        result['failure'] = 'background_not_unique_modal_colour'
        return result
    background = modes[0]
    foreground_colors = sorted(set(counts) - {background})
    result.update(background=background, all_foreground_colours=foreground_colors)
    if len(foreground_colors) != 1:
        result['failure'] = 'not_one_foreground_colour'
        return result
    foreground = foreground_colors[0]
    support = {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row)
               if value == foreground}
    r0, r1 = min(r for r, _ in support), max(r for r, _ in support)
    c0, c1 = min(c for _, c in support), max(c for _, c in support)
    height, width = r1 - r0 + 1, c1 - c0 + 1
    result['foreground_bbox'] = [r0, c0, r1, c1]
    if height != width or height < 3 or height % 2 != 1:
        result['failure'] = 'bbox_not_odd_square_of_positive_radius'
        return result
    radius = (height - 1) // 2
    center = ((r0 + r1) // 2, (c0 + c1) // 2)
    expected = {(center[0] + dr * distance, center[1] + dc * distance)
                for dr, dc in ((-1, 0), (0, 1), (1, 0), (0, -1))
                for distance in range(1, radius + 1)}
    result['bbox_determined_center'] = list(center)
    result['bbox_determined_radius'] = radius
    result['support_count'] = len(support)
    if grid[center[0]][center[1]] != background or support != expected:
        result['failure'] = 'whole_foreground_not_exact_four_equal_cardinal_arms'
        return result
    result['raw_roles'] = [{
        'center': list(center), 'radius': radius,
        'background': background, 'foreground_colour': foreground,
        'seed_coordinates': [list(point) for point in sorted(support)],
        'directions': ['N', 'E', 'S', 'W'],
        'whole_support_equality': True,
    }]
    result['failure'] = 'role_one'
    return result


def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30
            and type(grid[0]) is list and 1 <= len(grid[0]) <= 30
            and all(type(row) is list and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))


def parse_input(grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    raw = observe_input(grid)
    if len(raw['raw_roles']) != 1:
        return None, {'failure': 'whole_cross_role_not_unique', 'raw': raw}
    role = raw['raw_roles'][0]
    center = tuple(role['center'])
    height, width = len(grid), len(grid[0])
    payload = {'shape': (height, width), 'center': center, 'radius': role['radius'],
               'background': role['background'], 'foreground': role['foreground_colour'],
               'seeds': frozenset(map(tuple, role['seed_coordinates'])),
               'canvas_radius': max(center[0], height - 1 - center[0],
                                    center[1], width - 1 - center[1])}
    return payload, {'raw': raw, 'strict_arc_domain': True,
                     'canvas_radius': payload['canvas_radius']}


def valid_model(model):
    return (type(model) is tuple and len(model) == 2
            and ((type(model[0]) is int and 1 <= model[0] <= 29)
                 or (type(model[0]) is str and model[0] == 'GE30'))
            and type(model[1]) is str and model[1] in ('CW', 'CCW'))


def quarter_turn(vector, hand):
    r, c = vector
    return (c, -r) if hand == 'CW' else (-c, r)


def clipped_segment(start, end, height, width):
    r0, c0 = start
    r1, c1 = end
    if r0 == r1:
        return ([(r0, c) for c in range(max(0, min(c0, c1)), min(width - 1, max(c0, c1)) + 1)]
                if 0 <= r0 < height else [])
    if c0 == c1:
        return ([(r, c0) for r in range(max(0, min(r0, r1)), min(height - 1, max(r0, r1)) + 1)]
                if 0 <= c0 < width else [])
    raise ValueError('Declared curve segment must be axis aligned')


def render_curve(payload, model):
    if not valid_model(model):
        return None, {'failure': 'invalid_curve_model'}
    pitch_class, hand = model
    d = 30 if pitch_class == 'GE30' else pitch_class
    height, width = payload['shape']
    cr, cc = payload['center']
    radius = max(d, payload['radius'])
    phase_count = payload['canvas_radius'] // d
    union = set()
    arm_records = []
    proposal_count = 0
    for arm, u in enumerate(DIRECTIONS):
        first = (cr + u[0], cc + u[1])
        last = (cr + radius * u[0], cc + radius * u[1])
        initial = clipped_segment(first, last, height, width)
        union.update(initial)
        proposal_count += len(initial)
        phases = []
        e = u
        for k in range(phase_count):
            v = quarter_turn(e, hand)
            coordinates = ((radius + k * d, -k * d),
                           (radius + k * d, (k + 1) * d),
                           ((k + 1) * d, (k + 1) * d),
                           ((k + 1) * d, radius + (k + 1) * d))
            vertices = [(cr + a * e[0] + b * v[0], cc + a * e[1] + b * v[1])
                        for a, b in coordinates]
            segments = []
            phase_cells = set()
            for leg in range(3):
                cells = clipped_segment(vertices[leg], vertices[leg + 1], height, width)
                union.update(cells)
                phase_cells.update(cells)
                proposal_count += len(cells)
                segments.append({'leg': leg, 'start': list(vertices[leg]),
                                 'end': list(vertices[leg + 1]),
                                 'visible_cells': [list(p) for p in cells]})
            phases.append({'index': k, 'radial_lower_bound': (k + 1) * d,
                           'vertices': [list(p) for p in vertices], 'segments': segments,
                           'visible_union_count': len(phase_cells)})
            e = v
        arm_records.append({'arm': arm, 'direction': list(u),
                            'initial_start': list(first), 'initial_end': list(last),
                            'initial_cells': [list(p) for p in initial], 'phases': phases})
    if not payload['seeds'] <= union or payload['center'] in union:
        raise ValueError('Curve seed preservation or empty-center invariant failed')
    out = [[payload['background']] * width for _ in range(height)]
    for r, c in union:
        out[r][c] = payload['foreground']
    additions = union - payload['seeds']
    record = {'model': list(model), 'pitch_representative': d,
              'pitch_domain': 'all integers >=30' if pitch_class == 'GE30' else [d, d],
              'shape': [height, width], 'center': [cr, cc], 'input_radius': payload['radius'],
              'completed_radius': radius, 'canvas_radius': payload['canvas_radius'],
              'phases_per_arm': phase_count, 'all_bounded_phases_evaluated': True,
              'first_excluded_phase_lower_radius': (phase_count + 1) * d,
              'arms': arm_records, 'union_cells': [list(p) for p in sorted(union)],
              'foreground_cell_count': len(union), 'background_cell_count': height * width - len(union),
              'seed_cell_count': len(payload['seeds']), 'seed_preserved': True,
              'center_preserved_background': True, 'closed_segment_proposal_count': proposal_count,
              'added_cells': [list(p) for p in sorted(additions)], 'changed_cell_count': len(additions),
              'output_colour_counts': dict(sorted(Counter(v for row in out for v in row).items()))}
    return out, record


def fit_teachers(teachers):
    if (not isinstance(teachers, (list, tuple)) or not teachers
            or any(not isinstance(pair, dict) or 'input' not in pair or 'output' not in pair
                   for pair in teachers)):
        return None, {'failure': 'invalid_teachers'}
    parsed = [parse_input(pair['input']) for pair in teachers]
    input_records = [rec for payload, rec in parsed]
    if any(payload is None for payload, rec in parsed):
        return None, {'failure': 'teacher_input_not_interpretable', 'input_records': input_records,
                      'model_comparisons_completed': 0}
    distinct = len({tuple(tuple(row) for row in pair['input']) for pair in teachers})
    if distinct < 2:
        return None, {'failure': 'requires_two_distinct_teacher_inputs',
                      'input_records': input_records, 'distinct_inputs': distinct,
                      'model_comparisons_completed': 0}
    if any(not valid_grid(pair['output']) for pair in teachers):
        return None, {'failure': 'invalid_teacher_target', 'input_records': input_records,
                      'model_comparisons_completed': 0}
    models, comparisons = [], []
    try:
        for model in MODELS:
            rendered = [render_curve(payload, model) for payload, rec in parsed]
            if any(out is None for out, rec in rendered):
                return None, {'failure': 'curve_model_evaluation_failed',
                              'input_records': input_records, 'failed_model': list(model),
                              'failed_render_records': [rec for out, rec in rendered],
                              'completed_before_failure': len(comparisons),
                              'partial_models_discarded': True}
            equal = [out is not None and out == pair['output']
                     for (out, rec), pair in zip(rendered, teachers)]
            comparisons.append({'model': list(model), 'teacher_equal': equal,
                                'render_records': [rec for out, rec in rendered]})
            if all(equal):
                models.append(model)
    except Exception as error:
        return None, {'failure': 'curve_model_comparison_incomplete', 'error_type': type(error).__name__,
                      'input_records': input_records, 'completed_before_failure': len(comparisons),
                      'partial_models_discarded': True}
    record = {'input_records': input_records, 'distinct_inputs': distinct,
              'model_comparisons_completed': len(comparisons), 'comparisons': comparisons,
              'complete': len(comparisons) == len(MODELS), 'models': [list(m) for m in models],
              'model_count': len(models)}
    if not models:
        return None, {**record, 'failure': 'no_shared_curve_model'}
    return tuple(models), record


def predict(grid, models):
    if (type(models) is not tuple or not models or any(not valid_model(m) for m in models)
            or len(set(models)) != len(models)):
        return None, {'failure': 'invalid_retained_models'}
    payload, input_record = parse_input(grid)
    if payload is None:
        return None, {'failure': 'input_not_interpretable', 'input_record': input_record}
    try:
        rendered = [render_curve(payload, model) for model in models]
    except Exception as error:
        return None, {'failure': 'curve_prediction_incomplete', 'error_type': type(error).__name__,
                      'input_record': input_record, 'partial_answers_discarded': True}
    record = {'input_record': input_record, 'models': [list(m) for m in models],
              'render_records': [rec for out, rec in rendered], 'all_retained_models_evaluated': True}
    if any(out is None for out, rec in rendered):
        return None, {**record, 'failure': 'retained_curve_model_failed'}
    if any(out != rendered[0][0] for out, rec in rendered):
        return None, {**record, 'failure': 'retained_curve_models_disagree'}
    return rendered[0][0], {**record, 'all_model_grids_agree': True}


class 十字曲線教材:
    def __init__(self, 教師群):
        self.共有規則, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.共有規則 is None:
            return None, {"failure": "全教師を再現する十字曲線規則なし"}
        return predict(格子, self.共有規則)

    def 記録(self):
        return {"適合": self.共有規則 is not None, "共有規則": self.共有規則}
