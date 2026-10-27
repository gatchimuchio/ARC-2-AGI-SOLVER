"""New teacher-fitted gate/path composition; not a recovered historical source.

The declared grammar is a centered whole odd line transformed by D4, followed
by count-preserving compaction in complete nonbranching C4 paths. No files,
task identifiers, query targets, or historical runtime results are consumed.
"""
from collections import Counter
from itertools import permutations, product

from .二軸補完教材 import valid_grid
from .既存距離層 import open_components
from .既存正方形座標 import d4_motif_transform_coord
from .既存凡例穴対応 import clone_grid
from .既存種境界 import NEIGHBORS_4
from . import 距離回収候補 as distance

ROLE_NAMES = ('wall', 'material', 'gate', 'path')
TRANSFORMS = tuple('rot' + str(a) + suffix
                   for a in (0, 90, 180, 270) for suffix in ('', '_flip_h'))
DIRECTIONS = NEIGHBORS_4
MOVE = dict(metric='C4_BFS', origin='seed', wall_passable=False,
            source_transit=True, ranking='nearest',
            overflow='require_all_reachable', source_action='erase_to_background')


def gates(grid, roles, barrier, transform):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    if (set(roles) != set(ROLE_NAMES) or len(set(roles.values())) != 4
            or type(barrier) is not int or not 0 <= barrier <= 9
            or barrier in roles.values() or transform not in TRANSFORMS):
        return None, {'failure': 'invalid_gate_path_roles_or_transform'}
    if {v for row in grid for v in row} != set(roles.values()):
        return None, {'failure': 'input_not_exact_four_role_colors'}
    all_cells = {(r, c) for r, row in enumerate(grid) for c in range(len(row))}
    gate_cells = {p for p in all_cells if grid[p[0]][p[1]] == roles['gate']}
    components = open_components(grid, all_cells - gate_cells)
    ownership, transformed, records = set(), set(), []
    for cells in components:
        r0, r1 = min(r for r, c in cells), max(r for r, c in cells)
        c0, c1 = min(c for r, c in cells), max(c for r, c in cells)
        h, w = r1 - r0 + 1, c1 - c0 + 1
        length = max(h, w)
        if (min(h, w) != 1 or length < 3 or length % 2 != 1
                or len(cells) != length):
            return None, {'failure': 'gate_not_whole_solid_odd_line'}
        center = ((r0 + r1) // 2, (c0 + c1) // 2)
        half = length // 2
        mapped = set()
        for r, c in cells:
            rr, cc = d4_motif_transform_coord(
                length, length, transform,
                r - center[0] + half, c - center[1] + half)
            mapped.add((rr + center[0] - half, cc + center[1] - half))
        if len(mapped) != len(cells) or center not in mapped:
            return None, {'failure': 'gate_transform_not_complete_centered_bijection'}
        if not mapped <= all_cells:
            return None, {'failure': 'whole_gate_transform_outside_canvas'}
        if any(p not in cells and grid[p[0]][p[1]] != roles['path'] for p in mapped):
            return None, {'failure': 'transformed_gate_cell_not_owned_by_gate_or_path'}
        footprint = cells | mapped
        if footprint & ownership:
            return None, {'failure': 'whole_gate_footprints_overlap'}
        ownership.update(footprint)
        transformed.update(mapped)
        records.append({'source': sorted(cells), 'transformed': sorted(mapped),
                        'center': center, 'length': length})
    if set().union(*(set(r['source']) for r in records)) != gate_cells:
        return None, {'failure': 'incomplete_gate_ownership'}
    out = clone_grid(grid)
    for r, c in gate_cells:
        out[r][c] = roles['path']
    for r, c in transformed:
        out[r][c] = barrier
    return out, {'gates': records, 'gate_cells': len(gate_cells),
                 'transformed_cells': len(transformed)}


def render(grid, model):
    roles, barrier = model['roles'], model['barrier']
    direction = tuple(model['direction'])
    if direction not in DIRECTIONS:
        return None, {'failure': 'invalid_direction'}
    stage, record = gates(grid, roles, barrier, model['transform'])
    if stage is None:
        return None, record
    all_cells = {(r, c) for r, row in enumerate(stage) for c in range(len(row))}
    open_cells = {p for p in all_cells if stage[p[0]][p[1]] in
                  (roles['material'], roles['path'])}
    components = open_components(stage, all_cells - open_cells)
    owned, paths = set(), []
    output = clone_grid(stage)
    for cells in components:
        if cells & owned:
            return None, {'failure': 'path_components_overlap'}
        owned.update(cells)
        neighbors = {p: {(p[0] + dr, p[1] + dc) for dr, dc in NEIGHBORS_4} & cells
                     for p in cells}
        if any(len(ns) > 2 for ns in neighbors.values()):
            return None, {'failure': 'path_branches'}
        endpoints = [p for p, ns in neighbors.items() if len(ns) <= 1]
        if len(endpoints) != (1 if len(cells) == 1 else 2):
            return None, {'failure': 'path_not_complete_open_chain'}
        material = {p for p in cells if stage[p[0]][p[1]] == roles['material']}
        if not material:
            paths.append({'cells': sorted(cells), 'material_count': 0})
            continue
        project = lambda p: p[0] * direction[0] + p[1] * direction[1]
        if len({project(p) for p in cells}) == 1:
            paths.append({'cells': sorted(cells), 'material_count': len(material),
                          'stationary': 'no_directional_extent'})
            continue
        furthest = max(map(project, endpoints))
        ends = [p for p in endpoints if project(p) == furthest]
        if len(ends) != 1:
            return None, {'failure': 'directional_endpoint_not_unique'}
        endpoint = ends[0]
        parsed = {'seed': endpoint, 'target': cells,
                  'cells': {'source': cells, 'wall': all_cells - cells}}
        distances = distance.source_distances(stage, parsed, MOVE)
        if set(distances) != cells or set(distances.values()) != set(range(len(cells))):
            return None, {'failure': 'whole_path_distance_coverage_failed'}
        ordered = sorted(cells, key=distances.__getitem__)
        if any(project(b) > project(a) for a, b in zip(ordered, ordered[1:])):
            return None, {'failure': 'path_backtracks_against_direction'}
        destination = set(ordered[:len(material)])
        moving = material - destination
        slots = [p for p in ordered if p in destination - material]
        if len(moving) != len(slots):
            return None, {'failure': 'material_slot_count_mismatch'}
        parsed['cells']['source'] = moving
        move_roles = {'background': roles['path'], 'source': roles['material'],
                      'wall': roles['wall']}
        output, moved = distance.render_prepared(
            output, move_roles, MOVE, parsed,
            {p: distances[p] for p in moving}, slots)
        if output is None:
            return None, {'failure': 'prepared_path_move_failed', 'detail': moved}
        if {p for p in cells if output[p[0]][p[1]] == roles['material']} != destination:
            return None, {'failure': 'complete_material_destination_mismatch'}
        paths.append({'cells': sorted(cells), 'endpoint': endpoint,
                      'material_count': len(material), 'move': moved})
    if owned != open_cells:
        return None, {'failure': 'incomplete_path_ownership'}
    if any(output[r][c] != stage[r][c] for r, c in all_cells - open_cells):
        return None, {'failure': 'fixed_cells_changed'}
    before = Counter(v for row in grid for v in row)
    expected = before.copy()
    expected[barrier] = expected.pop(roles['gate'])
    if Counter(v for row in output for v in row) != expected:
        return None, {'failure': 'exact_color_counts_not_preserved'}
    return output, {**record, 'paths': paths, 'complete': True}


def fit(teachers):
    if (not isinstance(teachers, list) or len(teachers) < 2
            or any(not isinstance(p, dict) or not valid_grid(p.get('input'))
                   or not valid_grid(p.get('output')) for p in teachers)):
        return [], {'failure': 'invalid_teachers'}
    if len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return [], {'failure': 'duplicate_teacher_inputs'}
    if any((len(p['input']), len(p['input'][0])) !=
           (len(p['output']), len(p['output'][0])) for p in teachers):
        return [], {'failure': 'teacher_shape_not_preserved'}
    colors = sorted({v for p in teachers for row in p['input'] for v in row})
    new_colors = {v for p in teachers for row in p['output'] for v in row} - set(colors)
    if len(colors) != 4 or len(new_colors) != 1:
        return [], {'failure': 'requires_four_input_roles_and_one_new_barrier_color'}
    barrier = next(iter(new_colors))
    retained, signatures = [], Counter()
    for assignment, transform, direction in product(permutations(colors), TRANSFORMS, DIRECTIONS):
        model = {'roles': dict(zip(ROLE_NAMES, assignment)), 'barrier': barrier,
                 'transform': transform, 'direction': list(direction)}
        results = [render(p['input'], model) for p in teachers]
        signature = tuple(rec.get('failure', 'exact' if out == p['output'] else 'grid_mismatch')
                          for p, (out, rec) in zip(teachers, results))
        signatures[signature] += 1
        if all(s == 'exact' for s in signature):
            retained.append(model)
    return retained, {'complete': True, 'candidate_count': sum(signatures.values()),
                      'retained_count': len(retained),
                      'teacher_signatures': [{'signature': list(k), 'count': n}
                                             for k, n in sorted(signatures.items())]}


def consensus(grid, models):
    if not models:
        return None, {'failure': 'no_teacher_fit_model', 'retained_results': []}
    results = [render(grid, model) for model in models]
    records = [{'model_index': i, 'candidate': out, 'detail': rec}
               for i, (out, rec) in enumerate(results)]
    if any(out is None for out, rec in results):
        return None, {'failure': 'fitted_model_hold', 'retained_results': records}
    outputs = {tuple(map(tuple, out)) for out, rec in results}
    if len(outputs) != 1:
        return None, {'failure': 'fitted_models_disagree', 'retained_results': records}
    return [list(row) for row in next(iter(outputs))], {
        'models': len(models), 'complete': True, 'retained_results': records}


def freeze(models):
    return tuple((tuple(m['roles'][k] for k in ROLE_NAMES), m['barrier'],
                  m['transform'], tuple(m['direction'])) for m in models)


def thaw(models):
    return [{'roles': dict(zip(ROLE_NAMES, roles)), 'barrier': barrier,
             'transform': transform, 'direction': list(direction)}
            for roles, barrier, transform, direction in models]
