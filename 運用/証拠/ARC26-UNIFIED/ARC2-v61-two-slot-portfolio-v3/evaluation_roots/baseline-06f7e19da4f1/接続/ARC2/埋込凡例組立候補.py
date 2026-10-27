"""Embedded corner-palette view over the accepted whole-piece C4 assembler.

No source or target task identifiers. The only new relation is an embedded 2x2
palette assigning colors to the four corner-owning pieces of a full rectangle.
All host bbox corner / final canvas rotation alternatives survive teacher fit
when compatible; rendering requires agreement of all retained full grids.
"""
from collections import Counter
from itertools import product
from math import gcd, isqrt

from 接続.ARC2.標点組立教材 import (
    WORK_LIMIT, EXTENDED_WORK_LIMIT, mixed_c8, oriented_cells, parse,
    search_assemblies, valid_grid,
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


SQUARE_PALETTE_MARKER = 10


def observe_square_palette_roles(grid):
    """Find a unique n-by-n embedded palette over n-squared assembly pieces."""
    if not valid_grid(grid):
        return []
    roles = []
    for background in sorted({v for row in grid for v in row}):
        components = mixed_c8(grid, background)
        n = isqrt(len(components))
        if n < 3 or n * n != len(components):
            continue
        hosts = [p for p in components if len(p['color_counts']) > 1]
        if len(hosts) != 1 or any(len(p['color_counts']) != 1
                                  for p in components if p is not hosts[0]):
            continue
        host = hosts[0]
        counts = host['color_counts']
        body = max(counts, key=counts.get)
        if sum(value == counts[body] for value in counts.values()) != 1:
            continue
        body_colors = {body} | {
            next(iter(p['color_counts'])) for p in components if p is not host
        }
        if len(body_colors) != n * n:
            continue
        host_cells = {(r, c) for r, c, _ in host['cells']}
        r0, c0, r1, c1 = host['bbox']
        for top in range(r0, r1 - n + 2):
            for left in range(c0, c1 - n + 2):
                palette_cells = frozenset(
                    (r, c) for r in range(top, top + n)
                    for c in range(left, left + n)
                )
                values = [grid[r][c] for r, c in sorted(palette_cells)]
                palette_colors = set(values)
                if len(palette_colors) != n * n or body in palette_colors:
                    continue
                if set(counts) - {body} != palette_colors - {background}:
                    continue
                if any(value != background and counts.get(value) != 1
                       for value in palette_colors):
                    continue
                if any(value != background and (r, c) not in host_cells
                       for (r, c), value in zip(sorted(palette_cells), values)):
                    continue
                roles.append({
                    'background': background,
                    'body': body,
                    'body_colors': frozenset(body_colors),
                    'components': components,
                    'host_component_index': host['component_index'],
                    'host_bbox': tuple(host['bbox']),
                    'host_cells': frozenset(host_cells),
                    'n': n,
                    'palette': tuple(tuple(values[r*n:(r+1)*n])
                                     for r in range(n)),
                    'palette_cells': palette_cells,
                })
    return roles


def _square_palette_view(role, anchor):
    r0, c0, r1, c1 = role['host_bbox']
    marker = ((r0, c0), (r0, c1), (r1, c0), (r1, c1))[anchor]
    if marker not in role['host_cells'] | role['palette_cells']:
        return None
    pieces = []
    for component in role['components']:
        cells = {(r, c): color for r, c, color in component['cells']}
        if component['component_index'] == role['host_component_index']:
            for r, c in role['palette_cells']:
                cells[(r, c)] = role['body']
            if marker not in cells:
                return None
            cells[marker] = SQUARE_PALETTE_MARKER
        pieces.append({
            'index': component['component_index'],
            'cells': tuple((r, c, color) for (r, c), color in sorted(cells.items())),
        })
    return {
        'role': {
            'host_component_index': role['host_component_index'],
            'marker_color': SQUARE_PALETTE_MARKER,
        },
        'pieces': tuple(pieces),
    }


def _paint_square_palette_model(assembly, parsed, role, rotation):
    """Map each assembled piece by its centroid's n-by-n canvas position."""
    grid = assembly['grid']
    height, width = len(grid), len(grid[0])
    owner = [[-1] * width for _ in range(height)]
    pieces = {piece['index']: piece for piece in parsed['pieces']}
    for piece_id, label, dr, dc in assembly['placements']:
        for r, c, _ in oriented_cells(pieces[piece_id]['cells'], label):
            r, c = r + dr, c + dc
            if not (0 <= r < height and 0 <= c < width) or owner[r][c] != -1:
                return None, {'failure': 'square_palette_ownership_invalid'}
            owner[r][c] = piece_id
    if any(piece_id == -1 for row in owner for piece_id in row):
        return None, {'failure': 'square_palette_ownership_incomplete'}

    rotation_name = ROTATION_NAMES[rotation]
    grid = transform_grid_by_name(grid, rotation_name)
    owner = transform_grid_by_name(owner, rotation_name)
    height, width = len(grid), len(grid[0])
    source_colors = {}
    for component in role['components']:
        piece_id = component['component_index']
        if piece_id == role['host_component_index']:
            source_colors[piece_id] = role['body']
        else:
            colors = {color for _, _, color in component['cells']}
            if len(colors) != 1:
                return None, {'failure': 'square_palette_piece_not_monochrome'}
            source_colors[piece_id] = next(iter(colors))
    if len(set(source_colors.values())) != role['n'] ** 2:
        return None, {'failure': 'square_palette_source_colors_not_unique'}

    assignments = {}
    for piece_id, color in source_colors.items():
        cells = [(r, c) for r, row in enumerate(owner)
                 for c, owner_id in enumerate(row) if owner_id == piece_id]
        if not cells:
            return None, {'failure': 'square_palette_piece_missing'}
        center_r = sum(r for r, _ in cells) / len(cells)
        center_c = sum(c for _, c in cells) / len(cells)
        row = min(role['n'] - 1, int((center_r + 0.5) * role['n'] / height))
        col = min(role['n'] - 1, int((center_c + 0.5) * role['n'] / width))
        assignments[color] = (row, col)
    slots = set(assignments.values())
    if (set(assignments) != set(role['body_colors'])
            or len(slots) != role['n'] ** 2):
        return None, {'failure': 'square_palette_centroid_slots_not_bijective'}

    color_map = {color: role['palette'][row][col]
                 for color, (row, col) in assignments.items()}
    restored = [[role['body'] if value == SQUARE_PALETTE_MARKER else value
                 for value in row] for row in grid]
    if any(value not in color_map for row in restored for value in row):
        return None, {'failure': 'square_palette_source_color_unmapped'}
    output = [[color_map[value] for value in row] for row in restored]
    return output, {
        'assignments': {color: list(slot) for color, slot in assignments.items()},
        'source_to_output': color_map,
        'canvas_shape': [height, width],
    }


def render_square_palette(grid, policy, *, budget=EXTENDED_WORK_LIMIT):
    """Enumerate complete larger palettes; retain at most two scoring hypotheses."""
    if policy is None:
        return None, {'failure': 'no_fitted_view'}
    roles = observe_square_palette_roles(grid)
    if len(roles) != 1:
        return None, {'failure': 'square_palette_role_not_unique', 'role_count': len(roles)}
    role = roles[0]
    outputs, searches, paint_records = set(), [], []
    for anchor, rotation in policy['models']:
        parsed = _square_palette_view(role, anchor)
        if parsed is None:
            return None, {'failure': 'square_palette_marker_not_owned', 'searches': searches}
        aspect = tuple(policy['aspect'] if rotation % 2 == 0
                       else policy['aspect'][::-1])
        _, record = search_assemblies(parsed, aspect, budget=budget)
        searches.append({
            'anchor': anchor,
            'rotation': rotation,
            'aspect': aspect,
            'work': record.get('work'),
            'physical_model_count': record.get('physical_model_count'),
            'unique_grid_count': record.get('unique_grid_count'),
            'failure': record.get('failure'),
            'complete': record.get('complete'),
        })
        if not record.get('complete'):
            if record.get('failure') in {
                'area_not_compatible_with_aspect', 'canvas_outside_arc_bounds',
            }:
                continue
            return None, {'failure': 'square_palette_search_incomplete', 'searches': searches}
        if not record.get('models'):
            return None, {'failure': 'square_palette_retained_model_missing', 'searches': searches}
        for model in record['models']:
            output, paint_record = _paint_square_palette_model(
                model, parsed, role, rotation
            )
            if output is None:
                return None, {
                    'failure': paint_record.get('failure', 'square_palette_mapping_failed'),
                    'searches': searches,
                    'paint': paint_records + [paint_record],
                }
            outputs.add(key(output))
            paint_records.append({
                'anchor': anchor,
                'rotation': rotation,
                'placements': model['placements'],
                **paint_record,
            })
    if not outputs:
        return None, {'failure': 'square_palette_no_complete_assembly', 'searches': searches}
    ordered = sorted(outputs)
    record = {
        'palette_size': role['n'],
        'palette': [list(row) for row in role['palette']],
        'searches': searches,
        'physical_candidate_count': len(paint_records),
        'unique_candidate_count': len(ordered),
    }
    if len(ordered) == 1:
        return [list(row) for row in ordered[0]], record
    if len(ordered) == 2:
        return None, {
            **record,
            'failure': 'two_complete_square_palette_hypotheses',
            'candidate_attempts': [[list(row) for row in candidate]
                                   for candidate in ordered],
        }
    return None, {**record, 'failure': 'too_many_square_palette_hypotheses'}
