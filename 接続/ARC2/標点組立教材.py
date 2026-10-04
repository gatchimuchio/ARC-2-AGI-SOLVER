"""標点付き全成分をC4配置し、共有縦横比の全充填格子が合意した時だけ返す。"""
from collections import Counter
from math import gcd, isqrt

WORK_LIMIT = 100000
ROTATIONS = (0, 1, 2, 3)

def mixed_c8(grid, background):
    remaining = {(r, c) for r, row in enumerate(grid) for c, color in enumerate(row)
                 if color != background}
    result = []
    while remaining:
        seed = min(remaining)
        remaining.remove(seed)
        stack, cells = [seed], {seed}
        while stack:
            r, c = stack.pop()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    if not (dr or dc):
                        continue
                    q = r+dr, c+dc
                    if q in remaining:
                        remaining.remove(q)
                        cells.add(q)
                        stack.append(q)
        ordered = sorted(cells)
        counts = Counter(grid[r][c] for r, c in cells)
        result.append({'component_index': len(result), 'area': len(cells),
                       'bbox': [min(r for r, c in cells), min(c for r, c in cells),
                                max(r for r, c in cells), max(c for r, c in cells)],
                       'color_counts': dict(sorted(counts.items())),
                       'cells': [[r, c, grid[r][c]] for r, c in ordered]})
    return result

def observe_input(grid):
    backgrounds, complete_roles = [], []
    input_counts = Counter(color for row in grid for color in row)
    for background in range(10):
        components = mixed_c8(grid, background)
        bicolored = [p['component_index'] for p in components if len(p['color_counts']) == 2]
        complex_components = [p['component_index'] for p in components if len(p['color_counts']) > 2]
        failures = []
        if len(bicolored) != 1:
            failures.append('bicolored_whole_component_count_not_one')
        if complex_components:
            failures.append('whole_component_has_three_or_more_colors')
        roles = []
        if not failures:
            host = components[bicolored[0]]
            for color, size in host['color_counts'].items():
                if size != 1:
                    continue
                body = next(v for v in host['color_counts'] if v != color)
                marker = next(cell[:2] for cell in host['cells'] if cell[2] == color)
                cells = [tuple(cell[:2]) for p in components for cell in p['cells']]
                observed = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != background}
                ownership_counts = Counter(cells)
                role = {'background': background, 'host_component_index': host['component_index'],
                        'marker_color': color, 'marker_cell': marker,
                        'body_color': body, 'host_body_area': host['color_counts'][body],
                        'host_whole_area': host['area'],
                        'whole_piece_count': len(components),
                        'all_foreground_area': sum(p['area'] for p in components),
                        'other_piece_body_colors': [next(iter(p['color_counts'])) for p in components
                                                   if p['component_index'] != host['component_index']],
                        'marker_color_occurrences_outside_host': sum(p['color_counts'].get(color, 0)
                            for p in components if p['component_index'] != host['component_index']),
                        'foreground_unowned_cells': [list(q) for q in sorted(observed-set(cells))],
                        'foreground_multiply_owned_cells': [list(q) for q, n in sorted(ownership_counts.items()) if n != 1]}
                roles.append(role)
                complete_roles.append(role)
            if not roles:
                failures.append('bicolored_host_has_no_singleton_color')
        backgrounds.append({'background': background, 'background_input_pixels': input_counts[background],
                            'foreground_area': sum(p['area'] for p in components),
                            'whole_piece_count': len(components),
                            'whole_mixed_c8_components': components,
                            'bicolored_component_indices': bicolored,
                            'three_or_more_color_component_indices': complex_components,
                            'complete_role_count': len(roles), 'complete_roles': roles,
                            'raw_rejection_reasons': failures})
    return {'input_shape': [len(grid), len(grid[0])],
            'input_color_counts': dict(sorted(input_counts.items())),
            'complete_role_count': len(complete_roles), 'complete_roles': complete_roles,
            'all_background_observations': backgrounds}

def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


def parse(grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    raw = observe_input(grid)
    if raw['complete_role_count'] != 1:
        return None, {'failure': 'raw_role_not_unique', 'raw': raw}
    role = raw['complete_roles'][0]
    components = raw['all_background_observations'][role['background']]['whole_mixed_c8_components']
    parsed = {'role': role, 'pieces': tuple({'index': p['component_index'],
               'cells': tuple(tuple(c) for c in p['cells'])} for p in components)}
    return parsed, {'raw': raw, 'role': role}


class BudgetIncomplete(Exception):
    pass


class WorkBudget:
    def __init__(self, limit):
        self.limit = limit
        self.used = 0
        self.counts = Counter()

    def charge(self, amount, category):
        if self.used + amount > self.limit:
            raise BudgetIncomplete()
        self.used += amount
        self.counts[category] += amount


def oriented_cells(cells, label):
    transformed = []
    for r, c, color in cells:
        for _ in range(label):
            r, c = c, -r
        transformed.append((r, c, color))
    r0 = min(r for r, c, color in transformed)
    c0 = min(c for r, c, color in transformed)
    return tuple(sorted((r-r0, c-c0, color) for r, c, color in transformed))


def search_assemblies(parsed, aspect, *, budget=WORK_LIMIT):
    record = {'aspect': list(aspect) if isinstance(aspect, (list, tuple)) else aspect,
              'budget': budget, 'work': 0, 'complete': False, 'models': [],
              'models_seen': 0, 'physical_model_count': 0, 'unique_grid_count': 0}
    if (type(budget) is not int or not 1 <= budget <= WORK_LIMIT
            or not isinstance(aspect, (list, tuple)) or len(aspect) != 2
            or any(type(v) is not int or v < 1 for v in aspect)
            or gcd(*aspect) != 1):
        return None, {**record, 'failure': 'invalid_aspect_or_budget'}
    p, q = aspect
    pieces = parsed['pieces']
    role = parsed['role']
    area = sum(len(piece['cells']) for piece in pieces)
    record['foreground_area'] = area
    if not area or area % (p*q):
        return None, {**record, 'failure': 'area_not_compatible_with_aspect'}
    k = isqrt(area // (p*q))
    if k*k*p*q != area:
        return None, {**record, 'failure': 'area_not_compatible_with_aspect'}
    height, width = k*q, k*p
    record['canvas_shape'] = [height, width]
    if not (1 <= height <= 30 and 1 <= width <= 30):
        return None, {**record, 'failure': 'canvas_outside_arc_bounds'}
    meter = WorkBudget(budget)
    models, unique_grids = [], set()
    node_count = 0
    attempted_placements = 0
    source_counts = Counter(v for piece in pieces for r, c, v in piece['cells'])
    record['source_color_counts'] = dict(sorted(source_counts.items()))
    orientation_table = {}
    full_mask = (1 << area) - 1
    host = role['host_component_index']
    ids = tuple(piece['index'] for piece in pieces)
    if len(set(ids)) != len(ids) or host not in ids:
        return None, {**record, 'failure': 'invalid_parsed_piece_identity'}

    def candidate(piece_id, label, dr, dc, occupied):
        nonlocal attempted_placements
        cells = orientation_table[piece_id][label]
        meter.charge(1+len(cells), 'placements')
        attempted_placements += 1
        moved = tuple((r+dr, c+dc, v) for r, c, v in cells)
        if any(not (0 <= r < height and 0 <= c < width) for r, c, v in moved):
            return None
        mask = sum(1 << (r*width+c) for r, c, v in moved)
        if mask.bit_count() != len(moved) or mask & occupied:
            return None
        return mask, moved

    def visit(occupied, remaining, placements, paints):
        nonlocal node_count
        meter.charge(1, 'nodes')
        node_count += 1
        if not remaining:
            if occupied != full_mask:
                raise ValueError('terminal_coverage_not_complete')
            meter.charge(1+len(pieces)+area, 'solutions')
            flat = [None] * area
            for moved in paints:
                for r, c, v in moved:
                    if flat[r*width+c] is not None:
                        raise ValueError('terminal_overlap')
                    flat[r*width+c] = v
            if any(v is None for v in flat) or Counter(flat) != source_counts:
                raise ValueError('terminal_ownership_or_color_count')
            frozen = tuple(tuple(flat[r*width:(r+1)*width]) for r in range(height))
            models.append({'placements': [list(x) for x in sorted(placements)],
                           'grid': [list(row) for row in frozen]})
            unique_grids.add(frozen)
            return
        empty = full_mask ^ occupied
        first = (empty & -empty).bit_length()-1
        fr, fc = divmod(first, width)
        for piece_id in remaining:
            rest = tuple(i for i in remaining if i != piece_id)
            for label in ROTATIONS:
                r0, c0, _ = orientation_table[piece_id][label][0]
                dr, dc = fr-r0, fc-c0
                checked = candidate(piece_id, label, dr, dc, occupied)
                if checked is not None:
                    mask, moved = checked
                    visit(occupied | mask, rest,
                          placements+((piece_id, label, dr, dc),), paints+(moved,))

    try:
        for piece in pieces:
            labels = {}
            for label in ROTATIONS:
                meter.charge(1+len(piece['cells']), 'orientations')
                labels[label] = oriented_cells(piece['cells'], label)
            orientation_table[piece['index']] = labels
        meter.charge(1, 'nodes')
        node_count += 1
        remaining = tuple(i for i in ids if i != host)
        for label in ROTATIONS:
            markers = [(r, c) for r, c, v in orientation_table[host][label]
                       if v == role['marker_color']]
            if len(markers) != 1:
                raise ValueError('host_marker_ownership')
            mr, mc = markers[0]
            checked = candidate(host, label, -mr, -mc, 0)
            if checked is not None:
                mask, moved = checked
                visit(mask, remaining, ((host, label, -mr, -mc),), (moved,))
    except Exception as error:
        record.update(work=meter.used, work_categories=dict(sorted(meter.counts.items())),
                      node_count=node_count, attempted_placements=attempted_placements,
                      models_seen=len(models), models=[], physical_model_count=0,
                      unique_grid_count=0, complete=False,
                      failure='search_budget_incomplete' if isinstance(error, BudgetIncomplete)
                              else 'search_exception')
        if not isinstance(error, BudgetIncomplete):
            record['exception_type'] = type(error).__name__
        return None, record
    models.sort(key=lambda m: tuple(tuple(x) for x in m['placements']))
    record.update(work=meter.used, work_categories=dict(sorted(meter.counts.items())),
                  node_count=node_count, attempted_placements=attempted_placements,
                  models_seen=len(models), physical_model_count=len(models), models=models,
                  unique_grid_count=len(unique_grids), complete=True)
    if not models:
        return None, {**record, 'failure': 'no_complete_assembly'}
    if len(unique_grids) != 1:
        return None, {**record, 'failure': 'complete_grids_disagree'}
    grid = [list(row) for row in next(iter(unique_grids))]
    record['output_color_counts'] = dict(sorted(Counter(v for row in grid for v in row).items()))
    return grid, record


def render(grid, aspect, *, budget=WORK_LIMIT):
    try:
        parsed, raw_record = parse(grid)
    except Exception as error:
        return None, {'failure': 'parse_exception', 'exception_type': type(error).__name__}
    if parsed is None:
        return None, raw_record
    try:
        output, assembly = search_assemblies(parsed, aspect, budget=budget)
    except Exception as error:
        output, assembly = None, {'failure': 'search_exception',
            'exception_type': type(error).__name__, 'models': [],
            'physical_model_count': 0, 'complete': False}
    record = {'parse': raw_record, 'assembly': assembly}
    if output is None:
        record['failure'] = assembly['failure']
    return output, record


def fit_teachers(pairs):
    if not isinstance(pairs, (list, tuple)) or len(pairs) < 2:
        return None, {'failure': 'fewer_than_two_teachers'}
    parsed_rows = []
    distinct = set()
    for pair in pairs:
        grid = pair.get('input') if isinstance(pair, dict) else None
        try:
            parsed, record = parse(grid)
        except Exception as error:
            parsed, record = None, {'failure': 'parse_exception', 'exception_type': type(error).__name__}
        parsed_rows.append((parsed, record))
        if valid_grid(grid):
            distinct.add(tuple(tuple(row) for row in grid))
    summary = {'teacher_count': len(pairs), 'distinct_input_count': len(distinct),
               'raw_records': [r for p, r in parsed_rows]}
    if len(distinct) < 2:
        return None, {**summary, 'failure': 'fewer_than_two_distinct_inputs'}
    if any(parsed is None for parsed, r in parsed_rows):
        return None, {**summary, 'failure': 'teacher_raw_role_failed'}
    aspects = []
    for pair in pairs:
        target = pair.get('output')
        if not valid_grid(target):
            return None, {**summary, 'failure': 'invalid_teacher_output'}
        h, w = len(target), len(target[0])
        divisor = gcd(w, h)
        aspects.append((w//divisor, h//divisor))
    summary['teacher_aspects'] = [list(a) for a in aspects]
    if len(set(aspects)) != 1:
        return None, {**summary, 'failure': 'teacher_aspects_disagree'}
    aspect = aspects[0]
    predictions, searches = [], []
    for parsed, _ in parsed_rows:
        try:
            output, record = search_assemblies(parsed, aspect)
        except Exception as error:
            output, record = None, {'failure': 'search_exception',
                'exception_type': type(error).__name__, 'models': [],
                'physical_model_count': 0, 'complete': False}
        predictions.append(output)
        searches.append(record)
    # Target cell values are consulted only after every input search has finished.
    matches = [out is not None and out == pair['output'] for out, pair in zip(predictions, pairs)]
    summary.update(aspect=list(aspect), searches=searches, teacher_matches=matches)
    if not all(matches):
        return None, {**summary, 'failure': 'teacher_assembly_or_equality_failed'}
    return tuple(aspect), summary


class 標点組立教材:
    def __init__(self, 教師群):
        self.共有縦横比, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.共有縦横比 is None:
            return None, {"failure": "全教師を再現する標点組立規則なし"}
        return render(格子, self.共有縦横比)

    def 記録(self):
        return {"適合": self.共有縦横比 is not None, "共有縦横比": self.共有縦横比}
