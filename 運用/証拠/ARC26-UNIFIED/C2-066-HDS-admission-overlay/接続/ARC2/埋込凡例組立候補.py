"""Embedded corner-palette view over the accepted whole-piece C4 assembler.

No source or target task identifiers. The only new relation is an embedded 2x2
palette assigning colors to the four corner-owning pieces of a full rectangle.
All host bbox corner / final canvas rotation alternatives survive teacher fit
when compatible; rendering requires agreement of all retained full grids.
"""
from collections import Counter
from itertools import product
from math import gcd

from 接続.ARC2.標点組立教材 import (
    WORK_LIMIT, mixed_c8, parse, search_assemblies, valid_grid,
)
from 接続.ARC2.既存格子操作 import transform_grid_by_name

ROTATION_NAMES = ('identity', 'rot90', 'rot180', 'rot270')
CORNER_NAMES = ('top_left', 'top_right', 'bottom_left', 'bottom_right')


class AssemblyIncomplete(RuntimeError):
    """Resource or runtime failure is not an empty hypothesis set."""
    def __init__(self, record):
        super().__init__(str(record.get('failure', 'incomplete_existing_assembly')))
        self.record = record


def key(grid):
    return tuple(map(tuple, grid))


def corner_cells(bbox):
    r0, c0, r1, c1 = bbox
    return ((r0, c0), (r0, c1), (r1, c0), (r1, c1))


def observe_roles(grid):
    if not valid_grid(grid):
        return []
    roles = []
    for background in sorted({v for row in grid for v in row}):
        components = mixed_c8(grid, background)
        if len(components) != 4:
            continue
        for host in components:
            others = [p for p in components if p is not host]
            if len(host['color_counts']) != 5 or any(len(p['color_counts']) != 1 for p in others):
                continue
            for body in host['color_counts']:
                palette_cells = [(r, c, v) for r, c, v in host['cells'] if v != body]
                if len(palette_cells) != 4 or len({v for r, c, v in palette_cells}) != 4:
                    continue
                r0 = min(r for r, c, v in palette_cells)
                c0 = min(c for r, c, v in palette_cells)
                square = {(r0+r, c0+c) for r in range(2) for c in range(2)}
                if {(r, c) for r, c, v in palette_cells} != square:
                    continue
                bodies = {body} | {next(iter(p['color_counts'])) for p in others}
                palette_colors = {v for r, c, v in palette_cells}
                if len(bodies) != 4 or bodies & palette_colors:
                    continue
                cells = [(r, c) for p in components for r, c, v in p['cells']]
                foreground = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row)
                              if v != background}
                if set(cells) != foreground or len(cells) != len(foreground):
                    raise ValueError('input_ownership_failed')
                palette = tuple(tuple(grid[r0+r][c0+c] for c in range(2)) for r in range(2))
                roles.append({'background': background, 'body': body,
                    'host': host['component_index'], 'host_bbox': tuple(host['bbox']),
                    'host_cells': frozenset((r, c) for r, c, v in host['cells']),
                    'palette_cells': tuple(palette_cells), 'palette': palette,
                    'body_colors': frozenset(bodies), 'components': components,
                    'source_area': len(foreground)})
    return roles


def marker_view(grid, role, anchor):
    position = corner_cells(role['host_bbox'])[anchor]
    if position not in role['host_cells']:
        return None
    view = [row[:] for row in grid]
    for r, c, _ in role['palette_cells']:
        view[r][c] = role['body']
    marker = role['palette'][0][0]
    view[position[0]][position[1]] = marker
    parsed, _ = parse(view)
    if parsed is None:
        return None
    actual = parsed['role']
    if (actual['background'], actual['body_color'], actual['marker_color'],
        tuple(actual['marker_cell'])) != (role['background'], role['body'], marker, position):
        raise ValueError('view_marker_role_changed')
    if sum(len(p['cells']) for p in parsed['pieces']) != role['source_area']:
        raise ValueError('view_changed_source_ownership')
    return parsed


def paint_corners(grid, role):
    marker = role['palette'][0][0]
    restored = [[role['body'] if v == marker else v for v in row] for row in grid]
    h, w = len(restored), len(restored[0])
    corners = [restored[r][c] for r, c in corner_cells((0, 0, h-1, w-1))]
    if len(set(corners)) != 4 or set(corners) != role['body_colors']:
        return None
    color_map = dict(zip(corners, sum(role['palette'], ())))
    expected = Counter()
    for p in role['components']:
        color = role['body'] if p['component_index'] == role['host'] else next(iter(p['color_counts']))
        expected[color_map[color]] += p['area']
    output = [[color_map[v] for v in row] for row in restored]
    if h*w != role['source_area'] or Counter(v for row in output for v in row) != expected:
        raise ValueError('output_ownership_failed')
    return output


def enumerate_models(grid, aspect, *, budget=WORK_LIMIT):
    """Enumerate this view's complete physical alternatives without target pixels."""
    roles = observe_roles(grid)
    outputs = {model: set() for model in product(range(4), range(4))}
    reports = []
    physical_counts = Counter()
    for role_index, role in enumerate(roles):
        for anchor in range(4):
            parsed = marker_view(grid, role, anchor)
            if parsed is None:
                continue
            searches = {}
            for rotation in range(4):
                search_aspect = tuple(aspect if rotation % 2 == 0 else aspect[::-1])
                if search_aspect not in searches:
                    _, record = search_assemblies(parsed, search_aspect, budget=budget)
                    if not record['complete']:
                        # Aspect/area mismatch is a completed empty relation. Runtime
                        # and resource failures in the old API are raised to callers.
                        if record.get('failure') in {
                            'area_not_compatible_with_aspect', 'canvas_outside_arc_bounds'}:
                            searches[search_aspect] = []
                            continue
                        raise AssemblyIncomplete(record)
                    searches[search_aspect] = record['models']
                    reports.append({'role': role_index, 'anchor': anchor,
                        'aspect': search_aspect, 'work': record['work'],
                        'physical_models': record['physical_model_count'],
                        'complete': record['complete']})
                for assembly in searches[search_aspect]:
                    moved = transform_grid_by_name(assembly['grid'], ROTATION_NAMES[rotation])
                    output = paint_corners(moved, role)
                    if output is not None:
                        model = (anchor, rotation)
                        outputs[model].add(key(output))
                        physical_counts[model] += 1
    return outputs, {'role_count': len(roles), 'searches': reports,
        'physical_counts': dict(physical_counts),
        'output_counts': {model: len(values) for model, values in outputs.items()}}


def fit_teachers(pairs, *, budget=WORK_LIMIT):
    if not isinstance(pairs, (list, tuple)) or len(pairs) < 2:
        return None, {'failure': 'fewer_than_two_teachers'}
    if any(not isinstance(p, dict) or not valid_grid(p.get('input')) or
           not valid_grid(p.get('output')) for p in pairs):
        return None, {'failure': 'invalid_teacher'}
    if len({key(p['input']) for p in pairs}) < 2:
        return None, {'failure': 'fewer_than_two_distinct_inputs'}
    aspects = []
    for p in pairs:
        h, w = len(p['output']), len(p['output'][0])
        divisor = gcd(h, w)
        aspects.append((w//divisor, h//divisor))
    if len(set(aspects)) != 1:
        return None, {'failure': 'teacher_aspects_disagree'}
    aspect = aspects[0]
    # Finish every input-side enumeration before consulting output cell values.
    enumerated = [enumerate_models(p['input'], aspect, budget=budget) for p in pairs]
    retained = tuple(model for model in product(range(4), range(4))
                     if all(candidates[model] == {key(p['output'])}
                            for p, (candidates, _) in zip(pairs, enumerated)))
    record = {'aspect': aspect, 'retained_models': retained,
        'teacher_records': [r for _, r in enumerated]}
    if not retained:
        return None, {**record, 'failure': 'no_teacher_compatible_view'}
    # As in the accepted assembler, each retained model must give an exact,
    # agreed teacher grid. Verify the retained union reproduces each teacher too.
    teacher_surfaces = [set().union(*(candidates[model] for model in retained))
                        for candidates, _ in enumerated]
    record['teacher_full_grid_counts'] = [len(surfaces) for surfaces in teacher_surfaces]
    record['teacher_consensus_matches'] = [surfaces == {key(pair['output'])}
        for surfaces, pair in zip(teacher_surfaces, pairs)]
    if not all(record['teacher_consensus_matches']):
        return None, {**record, 'failure': 'teacher_full_grids_disagree'}
    policy = {'aspect': aspect, 'models': retained}
    return policy, record


def render(grid, policy, *, budget=WORK_LIMIT):
    if policy is None:
        return None, {'failure': 'no_fitted_view'}
    candidates, record = enumerate_models(grid, policy['aspect'], budget=budget)
    missing = [tuple(model) for model in policy['models'] if not candidates[tuple(model)]]
    record.update(retained_models=policy['models'], missing_retained_models=missing)
    if missing:
        return None, {**record, 'failure': 'retained_model_has_no_full_grid'}
    surfaces = set().union(*(candidates[tuple(model)] for model in policy['models']))
    record['full_grid_count'] = len(surfaces)
    if len(surfaces) != 1:
        return None, {**record, 'failure': 'no_full_grid' if not surfaces else 'full_grids_disagree'}
    return [list(row) for row in next(iter(surfaces))], record
