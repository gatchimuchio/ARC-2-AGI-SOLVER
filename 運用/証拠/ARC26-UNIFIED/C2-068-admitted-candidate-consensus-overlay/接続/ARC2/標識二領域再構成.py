"""NEW teacher/prior-informed reconstruction; never recovered historical source.

The layout, straight-line inventory and finite action vocabulary are explicit new
hypotheses. Runtime accepts grids and action identities only. It has no task,
path, hash, query loader, answer table, HDS, or publication input.
"""
from __future__ import annotations

from itertools import product
from .既存格子操作 import separator_lattice_segments
from .既存凡例穴対応 import clone_grid
from .既存物体特徴 import color_component_dicts_for_grid
from .既存領域転写 import mixed_region_dicts_for_grid
from .四欄反復教材 import valid_grid

# NEW four-action vocabulary, not the unavailable historical twelve identities.
# Both source-side orders crossed with both nonblank wall-overlay priorities.
WALL_POLICIES = ('first_nonblank', 'second_nonblank')
ACTIONS = tuple(product((0, 1), WALL_POLICIES))


def points(cells):
    return [list(cell) for cell in sorted(cells)]


def parse_layout(grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid', 'complete': True}
    h, w = len(grid), len(grid[0])
    # The accepted detect_separator_lattice requires at least 2x2 fields, so it
    # cannot represent this NEW 1x4/4x1 composition. Reuse its pure segmentation
    # primitive after a complete monochrome-line inventory; no heuristic crop.
    row_lines = [(r, row[0]) for r, row in enumerate(grid) if len(set(row)) == 1]
    col_lines = [(c, grid[0][c]) for c in range(w)
                 if len({grid[r][c] for r in range(h)}) == 1]
    colors = {color for _i, color in row_lines + col_lines}
    rec = {'complete': True, 'row_lines': row_lines, 'column_lines': col_lines}
    if not row_lines or not col_lines or len(colors) != 1:
        return None, {**rec, 'failure': 'no_single_color_separator_inventory'}
    separator = next(iter(colors))
    separator_rows = [r for r, _color in row_lines]
    separator_cols = [c for c, _color in col_lines]
    layout = {'separator_color': separator,
              'separator_rows': separator_rows, 'separator_cols': separator_cols,
              'row_segments': separator_lattice_segments(h, separator_rows),
              'col_segments': separator_lattice_segments(w, separator_cols)}
    rec['lattice'] = layout
    rows, cols = layout['row_segments'], layout['col_segments']
    if (len(rows), len(cols)) not in ((1, 4), (4, 1)):
        return None, {**rec, 'failure': 'not_four_collinear_fields'}
    boxes = [(r0, c0, r1, c1) for r0, r1 in rows for c0, c1 in cols]
    shapes = {(r1 - r0 + 1, c1 - c0 + 1) for r0, c0, r1, c1 in boxes}
    if len(shapes) != 1:
        return None, {**rec, 'failure': 'field_shapes_differ'}
    fields = [[[grid[r][c] for c in range(c0, c1 + 1)]
               for r in range(r0, r1 + 1)] for r0, c0, r1, c1 in boxes]
    palettes = [set(v for row in field for v in row) for field in fields]
    if len(palettes[3]) != 1:
        return None, {**rec, 'failure': 'destination_not_uniform'}
    blank = next(iter(palettes[3]))
    if len(palettes[0]) != 2 or blank not in palettes[0]:
        return None, {**rec, 'failure': 'control_not_binary_with_destination_blank'}
    ink = next(iter(palettes[0] - {blank}))
    if any(not (palette - {blank}) for palette in palettes[1:3]):
        return None, {**rec, 'failure': 'empty_source'}
    separator = layout['separator_color']
    fixed = {(r, c) for r in range(h) for c in range(w)
             if r in layout['separator_rows'] or c in layout['separator_cols']}
    field_cells = [{(r, c) for r in range(r0, r1 + 1)
                    for c in range(c0, c1 + 1)} for r0, c0, r1, c1 in boxes]
    owned = set(fixed)
    for cells in field_cells:
        if owned & cells:
            return None, {**rec, 'failure': 'input_ownership_overlap'}
        owned.update(cells)
    if owned != {(r, c) for r in range(h) for c in range(w)}:
        return None, {**rec, 'failure': 'input_ownership_incomplete'}
    if any(grid[r][c] != separator for r, c in fixed):
        return None, {**rec, 'failure': 'separator_ownership_incomplete'}
    rec.update(field_boxes=[list(box) for box in boxes], blank=blank,
               control_ink=ink, field_shape=list(next(iter(shapes))),
               fixed_cells=points(fixed), field_cells=[points(c) for c in field_cells],
               input_owned_count=len(owned))
    return {'fields': fields, 'blank': blank, 'control_ink': ink,
            'destination_box': boxes[3], 'destination_cells': field_cells[3]}, rec


def straight_inventory(control, ink):
    """NEW inventory: every complete row/column/unit diagonal in control ink.

    Inventory cardinality is decided before a wall component or region extractor
    is consulted. Thus failed/partial extraction cannot enable regional fallback.
    """
    h, w = len(control), len(control[0])
    cells = {(r, c) for r in range(h) for c in range(w)}
    ink_cells = {p for p in cells if control[p[0]][p[1]] == ink}
    specs = [('row', k, lambda r, c: r) for k in range(h)]
    specs += [('column', k, lambda r, c: c) for k in range(w)]
    specs += [('diagonal', k, lambda r, c: r - c) for k in range(1 - w, h)]
    specs += [('antidiagonal', k, lambda r, c: r + c) for k in range(h + w - 1)]
    raw = []
    for kind, intercept, coordinate in specs:
        wall = {p for p in cells if coordinate(*p) == intercept}
        low = {p for p in cells if coordinate(*p) < intercept}
        high = cells - wall - low
        remainder = ink_cells - wall
        if wall and low and high and wall <= ink_cells:
            raw.append({'kind': kind, 'intercept': intercept, 'wall': points(wall),
                        'off_wall_control': points(remainder),
                        'marker': list(next(iter(remainder))) if len(remainder) == 1 else None})
    return raw


def interpretation(control, ink, marker):
    """Certify one full C8 wall and its complete two-region C4 complement."""
    h, w = len(control), len(control[0])
    canvas = {(r, c) for r in range(h) for c in range(w)}
    marker = tuple(marker)
    ink_cells = {p for p in canvas if control[p[0]][p[1]] == ink}
    rec = {'marker': list(marker), 'complete': True, 'control_cells': points(ink_cells)}
    if marker not in ink_cells:
        return None, {**rec, 'failure': 'marker_not_control_ink'}
    wall = ink_cells - {marker}
    mask = [[int((r, c) in wall) for c in range(w)] for r in range(h)]
    parts = color_component_dicts_for_grid(mask, 1, include_diagonal=True)
    rec.update(wall_cells=points(wall), wall_component_count=len(parts))
    wall_owned = set()
    for part in parts:
        cells = set(map(tuple, part['cells']))
        if (not cells or cells & wall_owned or not cells <= wall
                or len(part['cells']) != len(cells) or part['size'] != len(cells)):
            return None, {**rec, 'complete': False, 'failure': 'invalid_wall_component_ownership'}
        wall_owned.update(cells)
    if wall_owned != wall:
        return None, {**rec, 'complete': False, 'failure': 'incomplete_wall_component_inventory'}
    if not wall or len(parts) != 1:
        return None, {**rec, 'failure': 'wall_not_one_complete_C8_component'}
    raw_regions = mixed_region_dicts_for_grid(mask, 1, include_diagonal=False)
    regions, owned = [], set()
    for part in raw_regions:
        cells = set(map(tuple, part['cells']))
        if (not cells or owned & cells or cells & wall or not cells <= canvas
                or len(part['cells']) != len(cells) or part['size'] != len(cells)):
            return None, {**rec, 'complete': False, 'failure': 'invalid_C4_region_ownership'}
        regions.append(cells)
        owned.update(cells)
    rec.update(regions=[points(cells) for cells in regions], region_count=len(regions))
    if owned != canvas - wall:
        return None, {**rec, 'complete': False, 'failure': 'incomplete_C4_region_inventory'}
    if len(regions) != 2:
        return None, {**rec, 'failure': 'not_exactly_two_complete_C4_regions'}
    marked = [i for i, cells in enumerate(regions) if marker in cells]
    if len(marked) != 1:
        return None, {**rec, 'failure': 'marker_region_not_unique'}
    ownership_groups = [{marker}, wall] + [cells - {marker} for cells in regions]
    if (set().union(*ownership_groups) != canvas
            or sum(map(len, ownership_groups)) != len(canvas)):
        return None, {**rec, 'failure': 'marker_wall_region_ownership_incomplete'}
    rec.update(marked_region=marked[0], owned_count=len(canvas),
               disjoint_ownership=[points(cells) for cells in ownership_groups])
    return {'wall': wall, 'regions': regions, 'marked_region': marked[0]}, rec


def views(control, ink):
    straight = straight_inventory(control, ink)
    rec = {'straight_inventory': straight, 'complete': True, 'interpretations': []}
    if len(straight) > 1:
        return (), {**rec, 'failure': 'multiple_straight_dividers', 'view': 'straight'}
    if straight:
        if straight[0]['marker'] is None:
            return (), {**rec, 'failure': 'straight_requires_one_off_wall_marker', 'view': 'straight'}
        view, detail = interpretation(control, ink, straight[0]['marker'])
        rec.update(view='straight', interpretations=[detail], complete=detail['complete'])
        if view is None:
            return (), {**rec, 'failure': 'straight_interpretation_failed'}
        if view['wall'] != set(map(tuple, straight[0]['wall'])):
            return (), {**rec, 'failure': 'straight_wall_ownership_disagrees'}
        return (view,), rec
    rec['view'] = 'regional'
    retained = []
    for r, row in enumerate(control):
        for c, value in enumerate(row):
            if value != ink:
                continue
            view, detail = interpretation(control, ink, (r, c))
            rec['interpretations'].append(detail)
            if view is not None:
                retained.append(view)
    rec['retained_interpretation_count'] = len(retained)
    if any(not detail['complete'] for detail in rec['interpretations']):
        return (), {**rec, 'complete': False, 'failure': 'regional_inventory_incomplete'}
    if not retained:
        rec['failure'] = 'no_complete_regional_interpretation'
    return tuple(retained), rec


def wall_value(first, second, blank, policy):
    if policy == 'first_nonblank': return first if first != blank else second
    if policy == 'second_nonblank': return second if second != blank else first
    raise ValueError('unknown wall policy')


def apply_action(grid, layout, view, action):
    marked_source, wall_policy = action
    fields, blank = layout['fields'], layout['blank']
    source = fields[1:3]
    h, w = len(fields[0]), len(fields[0][0])
    r0, c0, _r1, _c1 = layout['destination_box']
    out = clone_grid(grid)
    writes = []
    marked = view['regions'][view['marked_region']]
    for r in range(h):
        for c in range(w):
            if (r, c) in view['wall']:
                value = wall_value(source[0][r][c], source[1][r][c], blank, wall_policy)
                owner = 'wall'
            else:
                index = marked_source if (r, c) in marked else 1 - marked_source
                value = source[index][r][c]
                owner = 'marked_region' if (r, c) in marked else 'unmarked_region'
            out[r0 + r][c0 + c] = value
            writes.append({'cell': [r0 + r, c0 + c], 'value': value, 'owner': owner})
    destination = layout['destination_cells']
    if (len(writes) != len(destination)
            or {tuple(row['cell']) for row in writes} != destination
            or any(out[r][c] != grid[r][c] for r, row in enumerate(grid)
                   for c in range(len(row)) if (r, c) not in destination)):
        return None, {'failure': 'destination_only_write_certificate_failed', 'complete': True}
    return out, {'writes': writes, 'destination_only': True, 'complete': True}


def render(grid, action):
    rec = {'schema': 'NEW.marker_regions.v1', 'complete': False, 'action': list(action)}
    if action not in ACTIONS:
        return None, {**rec, 'complete': True, 'failure': 'unknown_action'}
    layout, detail = parse_layout(grid)
    rec['layout'] = detail
    if layout is None:
        return None, {**rec, 'complete': True, 'failure': 'layout_failed'}
    interpretations, detail = views(layout['fields'][0], layout['control_ink'])
    rec['view'] = detail
    rec['action_returns'] = []
    if not detail['complete']:
        return None, {**rec, 'failure': 'incomplete_view_inventory'}
    for index, view in enumerate(interpretations):
        out, certificate = apply_action(grid, layout, view, action)
        rec['action_returns'].append({'interpretation': index, 'output': out,
                                      'record': certificate})
    rec['complete'] = True
    outputs = [row['output'] for row in rec['action_returns']]
    if not outputs:
        return None, {**rec, 'failure': 'no_retained_interpretation'}
    if any(out is None for out in outputs):
        return None, {**rec, 'failure': 'retained_interpretation_action_failed'}
    if any(out != outputs[0] for out in outputs):
        return None, {**rec, 'failure': 'retained_interpretation_outputs_disagree'}
    return clone_grid(outputs[0]), rec


def fit_teachers(train):
    if not isinstance(train, list) or len(train) < 2:
        return (), {'failure': 'too_few_teachers', 'complete': True}
    if any(not isinstance(pair, dict) or not valid_grid(pair.get('input'))
           or not valid_grid(pair.get('output')) for pair in train):
        return (), {'failure': 'invalid_teachers', 'complete': True}
    keys = [tuple(map(tuple, pair['input'])) for pair in train]
    if len(set(keys)) != len(keys):
        return (), {'failure': 'duplicate_teacher_inputs', 'complete': True}
    retained, trials = [], []
    for action in ACTIONS:
        records = []
        for pair in train:
            out, detail = render(pair['input'], action)
            records.append({'exact': out == pair['output'], 'record': detail})
        if all(row['exact'] and row['record']['complete'] for row in records):
            retained.append(action)
        trials.append({'action': list(action), 'teachers': records})
    complete = all(row['record']['complete'] for trial in trials for row in trial['teachers'])
    detail = {'complete': complete, 'action_trials': trials,
              'retained_actions': [list(a) for a in retained],
              'failure': None if retained else 'teacher_mismatch'}
    if not complete:
        return (), {**detail, 'failure': 'incomplete_teacher_fit'}
    return tuple(retained), detail


def predict(grid, actions):
    records = []
    for action in actions:
        out, detail = render(grid, action)
        records.append({'action': list(action), 'output': out, 'record': detail})
    rec = {'complete': all(row['record']['complete'] for row in records),
           'action_returns': records}
    if not records or any(row['output'] is None or not row['record']['complete'] for row in records):
        return None, {**rec, 'failure': 'retained_action_failed_or_empty'}
    if any(row['output'] != records[0]['output'] for row in records):
        return None, {**rec, 'failure': 'retained_action_outputs_disagree'}
    return clone_grid(records[0]['output']), rec
