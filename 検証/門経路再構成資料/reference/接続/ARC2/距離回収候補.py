"""教師由来の純粋な距離回収候補。ファイル読取・task識別・HDS接続なし。"""
from collections import Counter, deque
from itertools import permutations, product
from 接続.ARC2.既存種境界 import NEIGHBORS_4, NEIGHBORS_8
from 接続.ARC2.既存距離層 import open_components
from 接続.ARC2.既存凡例穴対応 import clone_grid

ROLE_NAMES = ('background', 'seed', 'target', 'source', 'wall')
AXES = {
    'metric': ('C4_BFS', 'C8_BFS', 'Manhattan', 'Chebyshev', 'Euclidean_squared'),
    'origin': ('seed', 'target_all_cells'),
    'wall_passable': (False, True),
    'source_transit': (False, True),
    'ranking': ('nearest', 'farthest'),
    'capacity': ('target_area_including_seed', 'target_color_cells_preserve_seed'),
    'overflow': ('take_capacity_prefix', 'require_all_reachable'),
    'slot_order': ('row_asc_col_asc', 'row_asc_col_desc', 'row_desc_col_asc', 'row_desc_col_desc',
                   'col_asc_row_asc', 'col_asc_row_desc', 'col_desc_row_asc', 'col_desc_row_desc'),
    'source_action': ('erase_to_background', 'preserve'),
}
AXIS_COUNT = 5120


def parse(grid, roles, expected_shape=None):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30 or
        not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30 or
        any(not isinstance(row, list) or len(row) != len(grid[0]) or
            any(type(v) is not int or not 0 <= v <= 9 for v in row) for row in grid)):
        return None, 'invalid_arc_grid'
    if set(roles) != set(ROLE_NAMES) or len(set(roles.values())) != 5:
        return None, 'roles_not_five_distinct_colors'
    colors = {v for row in grid for v in row}
    if colors - set(roles.values()):
        return None, 'unowned_input_color'
    if set(roles.values()) - colors - {roles['wall']}:
        return None, 'required_role_absent'
    cells = {name: {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row)
                    if value == color} for name, color in roles.items()}
    if len(cells['seed']) != 1:
        return None, 'seed_not_singleton'
    seed = next(iter(cells['seed']))
    ts = cells['target']
    if not ts:
        return None, 'target_absent'
    lo = min(r for r, c in ts), min(c for r, c in ts)
    hi = max(r for r, c in ts), max(c for r, c in ts)
    shape = hi[0] - lo[0] + 1, hi[1] - lo[1] + 1
    if shape[0] != shape[1] or shape[0] < 3 or shape[0] % 2 != 1:
        return None, 'target_not_odd_square'
    if expected_shape is not None and tuple(expected_shape) != shape:
        return None, 'target_shape_outside_teacher_contract'
    target = {(r, c) for r in range(lo[0], hi[0] + 1) for c in range(lo[1], hi[1] + 1)}
    if ts | cells['seed'] != target or seed != ((lo[0] + hi[0]) // 2, (lo[1] + hi[1]) // 2):
        return None, 'target_ownership_or_center_failed'
    if cells['source'] & target:
        return None, 'source_target_overlap'
    return {'cells': cells, 'target': target, 'seed': seed, 'shape': shape}, None


def source_distances(grid, parsed, p):
    origins = {parsed['seed']} if p['origin'] == 'seed' else parsed['target']
    sources = parsed['cells']['source']
    if p['metric'] in ('C4_BFS', 'C8_BFS'):
        h, w = len(grid), len(grid[0])
        offsets = NEIGHBORS_4 if p['metric'] == 'C4_BFS' else NEIGHBORS_8
        blocked = set() if p['wall_passable'] else parsed['cells']['wall']
        distance = {c: 0 for c in origins}
        queue = deque(sorted(origins))
        while queue:
            here = queue.popleft()
            if here in sources and not p['source_transit']:
                continue
            for dr, dc in offsets:
                nxt = here[0] + dr, here[1] + dc
                if (0 <= nxt[0] < h and 0 <= nxt[1] < w and
                        nxt not in blocked and nxt not in distance):
                    distance[nxt] = distance[here] + 1
                    queue.append(nxt)
        # 既存のC4全域分割を再利用して独立coverage証明。
        if p['metric'] == 'C4_BFS' and p['source_transit']:
            reached = set().union(*(c for c in open_components(grid, blocked) if c & origins))
            if reached != set(distance):
                raise AssertionError('existing_C4_partition_disagrees')
        return {c: distance[c] for c in sources if c in distance}
    def metric(a, b):
        dr, dc = abs(a[0]-b[0]), abs(a[1]-b[1])
        if p['metric'] == 'Manhattan': return dr + dc
        if p['metric'] == 'Chebyshev': return max(dr, dc)
        if p['metric'] == 'Euclidean_squared': return dr*dr + dc*dc
        raise ValueError('unknown_metric')
    return {c: min(metric(c, origin) for origin in origins) for c in sources}


def ordered_slots(parsed, p):
    cells = parsed['target'] if p['capacity'] == 'target_area_including_seed' else parsed['cells']['target']
    parts = p['slot_order'].split('_')
    i, j = (0, 1) if parts[0] == 'row' else (1, 0)
    si, sj = (1 if parts[1] == 'asc' else -1), (1 if parts[3] == 'asc' else -1)
    return sorted(cells, key=lambda c: (si*c[i], sj*c[j]))


def render(grid, roles, p, expected_shape=None):
    parsed, failure = parse(grid, roles, expected_shape)
    if failure: return None, {'failure': failure}
    ds = source_distances(grid, parsed, p)
    slots = ordered_slots(parsed, p)
    return render_prepared(grid, roles, p, parsed, ds, slots)


def render_prepared(grid, roles, p, parsed, ds, slots):
    """論理状態を一切選別せず、同一の純粋中間結果のみ再利用する。"""
    source = parsed['cells']['source']
    ordered = sorted(ds, key=lambda c: ((ds[c] if p['ranking']=='nearest' else -ds[c]), c))
    count = min(len(ds), len(slots))
    record = {'source_count': len(source), 'reachable_count': len(ds), 'capacity': len(slots),
              'source_distances': [{'cell': list(c), 'distance': ds.get(c)} for c in sorted(source)],
              'target': [list(c) for c in sorted(parsed['target'])], 'seed': list(parsed['seed'])}
    if len(ds) > len(slots):
        if p['overflow'] == 'require_all_reachable':
            return None, {**record, 'failure': 'reachable_source_overflow'}
        if ds[ordered[count - 1]] == ds[ordered[count]]:
            return None, {**record, 'failure': 'capacity_cutoff_distance_tie', 'cutoff_distance': ds[ordered[count]]}
    chosen = set(ordered[:count])
    filled = set(slots[:count])
    proposals = {c: roles['source'] for c in filled}
    if p['source_action'] == 'erase_to_background':
        for c in chosen:
            if c in proposals:
                return None, {**record, 'failure': 'source_destination_overlap'}
            proposals[c] = roles['background']
    out = clone_grid(grid)
    for (r, c), value in proposals.items(): out[r][c] = value
    untouched = {(r,c) for r,row in enumerate(grid) for c,_ in enumerate(row)} - proposals.keys()
    if any(out[r][c] != grid[r][c] for r,c in untouched):
        raise AssertionError('outside_proposals_changed')
    if any(out[r][c] != grid[r][c] for r,c in parsed['cells']['wall']):
        raise AssertionError('wall_changed')
    if any(out[r][c] != roles['source'] for r,c in source - chosen):
        raise AssertionError('unselected_source_changed')
    before = sum(v == roles['source'] for row in grid for v in row)
    after = sum(v == roles['source'] for row in out for v in row)
    if p['source_action'] == 'erase_to_background' and before != after:
        raise AssertionError('source_pixel_count_not_conserved')
    return out, {**record, 'selected': [list(c) for c in sorted(chosen)],
                 'filled': [list(c) for c in slots[:count]], 'selected_count': count,
                 'source_count_before_after': [before, after],
                 'unchanged_cells': len(untouched),
                 'seed_overwritten': parsed['seed'] in filled}


def fit(teachers):
    """全role×全axisを教師完全格子比較。否定・失敗は全て記録。"""
    if not teachers or len({tuple(map(tuple,p['input'])) for p in teachers}) != len(teachers):
        return [], {'failure': 'missing_or_duplicate_teachers'}
    colors = sorted({v for p in teachers for row in p['input'] for v in row})
    if len(colors) != 5:
        return [], {'failure': 'union_not_five_role_colors'}
    role_records, survivors, tested, signatures = [], [], 0, Counter()
    parameter_grid = [dict(zip(AXES, values)) for values in product(*AXES.values())]
    if len(parameter_grid) != AXIS_COUNT: raise AssertionError('axis_count')
    for assignment in permutations(colors):
        roles = dict(zip(ROLE_NAMES, assignment))
        checks = [parse(pair['input'], roles) for pair in teachers]
        errors = [failure for parsed, failure in checks]
        shapes = {parsed['shape'] for parsed, failure in checks if parsed is not None}
        ok = not any(errors) and len(shapes) == 1
        rr = {'roles': roles, 'teacher_structural_failure': errors,
              'shapes': [list(s) for s in sorted(shapes)], 'structural_pass': ok}
        if not ok:
            rr['logically_rejected_parameter_combinations'] = len(parameter_grid)
            role_records.append(rr)
            continue
        shape = next(iter(shapes))
        local = []
        prepared = [parsed for parsed, failure in checks]
        distance_cache = [{} for _ in teachers]
        slot_cache = [{} for _ in teachers]
        for params in parameter_grid:
            tested += 1
            results = []
            for ti, pair in enumerate(teachers):
                dk = tuple(params[k] for k in ('metric', 'origin', 'wall_passable', 'source_transit'))
                sk = tuple(params[k] for k in ('capacity', 'slot_order'))
                if dk not in distance_cache[ti]:
                    distance_cache[ti][dk] = source_distances(pair['input'], prepared[ti], params)
                if sk not in slot_cache[ti]:
                    slot_cache[ti][sk] = ordered_slots(prepared[ti], params)
                results.append(render_prepared(pair['input'], roles, params, prepared[ti],
                                               distance_cache[ti][dk], slot_cache[ti][sk]))
            signature = tuple(rec.get('failure','exact' if out == pair['output'] else 'grid_mismatch')
                              for (out, rec), pair in zip(results, teachers))
            signatures[signature] += 1
            if all(s == 'exact' for s in signature):
                model = {'roles': roles, 'shape': list(shape), 'parameters': params}
                local.append(params)
                survivors.append(model)
        rr['all_axis_evaluations'] = len(parameter_grid)
        rr['survivor_count'] = len(local)
        role_records.append(rr)
    return survivors, {'role_assignments': role_records, 'conceptual_candidates': len(role_records)*AXIS_COUNT,
                       'fully_evaluated_candidates': tested,
                       'logically_rejected_candidates': (len(role_records)-sum(r['structural_pass'] for r in role_records))*AXIS_COUNT,
                       'all_teacher_result_signatures': [{'signature': list(k), 'count':v} for k,v in sorted(signatures.items())],
                       'survivor_count': len(survivors)}


def consensus(grid, models):
    if not models: return None, {'failure': 'no_teacher_fit_model'}
    results = [render(grid, m['roles'], m['parameters'], m['shape']) for m in models]
    failures = [rec for out,rec in results if out is None]
    grids = {tuple(map(tuple, out)) for out,rec in results if out is not None}
    if failures: return None, {'failure': 'fitted_model_hold', 'models':len(models), 'failures':failures}
    if len(grids) != 1: return None, {'failure':'fitted_models_disagree', 'output_count':len(grids)}
    return [list(row) for row in next(iter(grids))], {'models':len(models),'records':[rec for out,rec in results]}
