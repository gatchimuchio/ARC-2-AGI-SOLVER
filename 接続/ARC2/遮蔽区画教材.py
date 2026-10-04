"""全層順序の遮蔽区画計数と、教師から得た全色順位の受理関係。"""
from collections import Counter
from functools import lru_cache


def order_count(colours, edges):
    positions = {c: i for i, c in enumerate(colours)}
    predecessors = [0] * len(colours)
    for a, b in edges:
        predecessors[positions[b]] |= 1 << positions[a]
    full = (1 << len(colours)) - 1
    @lru_cache(None)
    def count(used):
        if used == full:
            return 1
        return sum(count(used | (1 << i)) for i, pred in enumerate(predecessors)
                   if not (used >> i) & 1 and pred & used == pred)
    return count(0)


def describe_input(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return {'failure': 'invalid_grid', 'joint_roles': []}
    counts = Counter(v for row in grid for v in row)
    modes = sorted(c for c, n in counts.items() if n == max(counts.values()))
    rec = {'shape': [len(grid), len(grid[0])], 'counts': sorted(counts.items()),
           'background_candidates': modes, 'joint_roles': []}
    if len(modes) != 1:
        return {**rec, 'failure': 'background_mode_not_unique'}
    bg = modes[0]
    colours = sorted(set(counts) - {bg})
    facts = []
    for colour in colours:
        cells = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == colour]
        r0, c0 = min(r for r, c in cells), min(c for r, c in cells)
        r1, c1 = max(r for r, c in cells), max(c for r, c in cells)
        perimeter = sorted({(r, c) for r in range(r0, r1 + 1)
                            for c in range(c0, c1 + 1)
                            if r in (r0, r1) or c in (c0, c1)})
        facts.append({'colour': colour, 'bbox': [r0, c0, r1, c1],
                      'has_interior': r1 - r0 >= 2 and c1 - c0 >= 2,
                      'perimeter_background': [[r, c] for r, c in perimeter if grid[r][c] == bg],
                      'foreign_perimeter': [[r, c, grid[r][c]] for r, c in perimeter if grid[r][c] != colour]})
    hypotheses = []
    for noise in colours:
        signals = [x for x in facts if x['colour'] != noise]
        failures = [{'colour': x['colour'], 'has_interior': x['has_interior'],
                     'background_perimeter_cells': len(x['perimeter_background'])}
                    for x in signals if not x['has_interior'] or x['perimeter_background']]
        hypothesis = {'noise': noise, 'signals': [x['colour'] for x in signals],
                      'boundary_failures': failures}
        if not signals:
            hypothesis['failure'] = 'no_signal_colour'
        elif failures:
            hypothesis['failure'] = 'signal_boundary_contract_failed'
        else:
            edges = {(x['colour'], v) for x in signals for r, c, v in x['foreign_perimeter']}
            edges.update((x['colour'], noise) for x in signals)
            n = order_count(colours, edges)
            hypothesis.update({'front_edges': [list(e) for e in sorted(edges)], 'order_count': n})
            if not n:
                hypothesis['failure'] = 'front_order_cycle'
            else:
                rec['joint_roles'].append({'noise': noise, 'signals': hypothesis['signals'],
                                           'front_edges': hypothesis['front_edges'], 'order_count': n})
        hypotheses.append(hypothesis)
    rec.update({'background': bg, 'colour_bboxes': facts, 'all_noise_hypotheses': hypotheses})
    if len(rec['joint_roles']) != 1:
        rec['failure'] = 'joint_noise_role_not_unique'
    return rec


MAX_PREFIXES = 100000


def layer_orders(colours, edges, limit=None):
    limit = MAX_PREFIXES if limit is None else limit
    colours = tuple(sorted(colours))
    before = {c: {a for a, b in edges if b == c} for c in colours}
    orders = []
    prefixes = 0
    complete = True
    def visit(prefix, used):
        nonlocal prefixes, complete
        if prefixes + 1 > limit:
            complete = False
            return
        prefixes += 1
        if len(prefix) == len(colours):
            orders.append(tuple(prefix))
            return
        for c in colours:
            if c not in used and before[c] <= used:
                visit(prefix + [c], used | {c})
                if not complete:
                    return
    visit([], set())
    record = {'complete': complete, 'prefixes': prefixes, 'discovered_orders': len(orders)}
    if not complete:
        return (), {**record, 'failure': 'layer_order_enumeration_incomplete',
                    'partial_orders_discarded': True}
    if not orders:
        return (), {**record, 'failure': 'no_layer_order'}
    return tuple(orders), record


def neighbours(cell, width):
    row, col = divmod(cell, width)
    return (cell - width, cell + width) + ((cell - 1,) if col else ()) + ((cell + 1,) if col + 1 < width else ())


def components(cells, width):
    left = set(cells)
    result = []
    while left:
        start = min(left)
        left.remove(start)
        found, stack = {start}, [start]
        while stack:
            cell = stack.pop()
            for other in neighbours(cell, width):
                if other in left:
                    left.remove(other)
                    found.add(other)
                    stack.append(other)
        result.append(found)
    return result


def bridge_edges(cells, width):
    clock = 0
    times, low, bridges = {}, {}, []
    for start in sorted(cells):
        if start in times:
            continue
        times[start] = low[start] = clock
        clock += 1
        stack = [(start, None, iter(sorted(x for x in neighbours(start, width) if x in cells)))]
        while stack:
            cell, parent, iterator = stack[-1]
            try:
                other = next(iterator)
            except StopIteration:
                stack.pop()
                if parent is not None:
                    if low[cell] > times[parent]:
                        bridges.append(tuple(sorted((cell, parent))))
                    low[parent] = min(low[parent], low[cell])
                continue
            if other == parent:
                continue
            if other in times:
                low[cell] = min(low[cell], times[other])
            else:
                times[other] = low[other] = clock
                clock += 1
                stack.append((other, cell, iter(sorted(x for x in neighbours(other, width) if x in cells))))
    return sorted(bridges)


def bits(cells):
    return sum(1 << i for i in cells)


def colour_mask(grid, colour, front):
    height, width = len(grid), len(grid[0])
    original = {r * width + c for r, row in enumerate(grid) for c, v in enumerate(row) if v == colour}
    interpolated = set(original)
    allowed = set(front) | {colour}
    lines = [[r * width + c for c in range(width)] for r in range(height)]
    lines.extend([[r * width + c for r in range(height)] for c in range(width)])
    for line in lines:
        run = []
        def flush():
            witnesses = [j for j, i in enumerate(run) if grid[i // width][i % width] == colour]
            if len(witnesses) >= 2:
                interpolated.update(run[witnesses[0]:witnesses[-1] + 1])
        for cell in line:
            value = grid[cell // width][cell % width]
            if value in allowed:
                run.append(cell)
            else:
                flush()
                run = []
        flush()
    r0, r1 = min(i // width for i in original), max(i // width for i in original)
    c0, c1 = min(i % width for i in original), max(i % width for i in original)
    perimeter = {r * width + c for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)
                 if r in (r0, r1) or c in (c0, c1)}
    mask = interpolated | perimeter
    return original, interpolated, perimeter, mask, (r0, c0, r1, c1)


def inspect_mask(grid, colour, original, interpolated, perimeter, mask, bbox):
    width = len(grid[0])
    r0, c0, r1, c1 = bbox
    connected = components(mask, width)
    bridges = bridge_edges(mask, width)
    blocks = [r * width + c for r in range(r0, r1) for c in range(c0, c1)
              if {r * width + c, r * width + c + 1,
                  (r + 1) * width + c, (r + 1) * width + c + 1} <= mask]
    missing = {r * width + c for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)} - mask
    region_parts = components(missing, width)
    regions = [cells for cells in region_parts if not any(i // width in (r0, r1)
               or i % width in (c0, c1) for i in cells)]
    record = {'colour': colour, 'bbox': list(bbox),
              'original': hex(bits(original)), 'interpolated': hex(bits(interpolated)),
              'perimeter': hex(bits(perimeter)), 'perimeter_prior_added': hex(bits(perimeter - interpolated)),
              'final': hex(bits(mask)), 'mask_cell_count': len(mask),
              'component_masks': [hex(bits(c)) for c in connected],
              'bridge_edges': [list(e) for e in bridges], 'full_2x2': blocks,
              'bounded_regions': [hex(bits(c)) for c in regions], 'region_count': len(regions),
              'original_pixels_retained': original <= mask, 'perimeter_complete': perimeter <= mask}
    failures = []
    if len(connected) != 1:
        failures.append('mask_not_c4_connected')
    if bridges:
        failures.append('mask_has_bridge_edges')
    if blocks:
        failures.append('mask_has_full_2x2')
    if not regions:
        failures.append('mask_has_no_bounded_region')
    if failures:
        record['failures'] = failures
    return record


def complete_order(grid, role, order, cache=None):
    masks = []
    for colour in sorted(role['signals']):
        front = order[order.index(colour) + 1:]
        masks.append((colour, colour_mask(grid, colour, front)))
    key = tuple((colour, bits(values[1]), bits(values[3])) for colour, values in masks)
    if cache is not None and key in cache:
        return cache[key]
    records = [inspect_mask(grid, colour, *values) for colour, values in masks]
    valid = all('failures' not in rec for rec in records)
    counts = {rec['colour']: rec['region_count'] for rec in records}
    record = {'signals': records, 'counts': sorted(counts.items()), 'valid': valid}
    if not valid:
        record['failure'] = 'invalid_signal_partition'
        result = (None, record)
    elif max(counts.values()) > 30 or len(counts) > 30:
        result = (None, {**record, 'failure': 'histogram_dimension_exceeds_arc'})
    else:
        result = (counts, record)
    if cache is not None:
        cache[key] = result
    return result


def parse_input(grid):
    raw = describe_input(grid)
    if 'failure' in raw:
        return None, {'raw': raw, 'failure': raw['failure'], 'geometry_reached': False}
    role = raw['joint_roles'][0]
    colours = tuple(sorted([role['noise']] + role['signals']))
    orders, enum_rec = layer_orders(colours, role['front_edges'])
    base = {'raw': raw, 'enumeration': enum_rec, 'orders': [list(o) for o in orders]}
    if not enum_rec['complete'] or not orders:
        return None, {**base, 'failure': enum_rec['failure'], 'geometry_reached': False}
    cache, table, mapping = {}, [], []
    intern = {}
    vectors = []
    failed_orders = []
    for i, order in enumerate(orders):
        counts, rec = complete_order(grid, role, order, cache)
        identity = id(rec)
        if identity not in intern:
            intern[identity] = len(table)
            table.append(rec)
        mapping.append(intern[identity])
        if counts is None:
            failed_orders.append(i)
        else:
            vectors.append(tuple(sorted(counts.items())))
    record = {**base, 'geometry_reached': True, 'geometry_records': table,
              'order_geometry_indices': mapping, 'failed_order_indices': failed_orders,
              'completed_order_count': len(orders)}
    if failed_orders:
        return None, {**record, 'failure': 'retained_layer_order_failed'}
    if len(set(vectors)) != 1:
        return None, {**record, 'failure': 'layer_order_counts_disagree'}
    counts = dict(vectors[0])
    payload = {'background': raw['background'], 'noise': role['noise'],
               'signals': sorted(role['signals']), 'counts': counts}
    return payload, {**record, 'counts': sorted(counts.items()),
                     'all_layer_orders_count_agree': True,
                     'all_layer_orders_masks_equal': len({tuple((s['colour'], s['final']) for s in r['signals']) for r in table}) == 1}


def priority_closure(edges):
    if not isinstance(edges, (list, tuple)):
        return None
    if any(not isinstance(e, (list, tuple)) or len(e) != 2
           or any(type(v) is not int or not 0 <= v <= 9 for v in e) for e in edges):
        return None
    reach = {c: set() for c in range(10)}
    for a, b in edges:
        reach[a].add(b)
    for pivot in range(10):
        for a in range(10):
            if pivot in reach[a]:
                reach[a].update(reach[pivot])
    if any(c in reach[c] for c in reach):
        return None
    return tuple((a, b) for a in range(10) for b in sorted(reach[a]))


def unique_group_order(colours, closure):
    left = set(colours)
    answer = []
    while left:
        options = [c for c in sorted(left) if not any(a in left and b == c for a, b in closure)]
        if len(options) != 1:
            return None
        colour = options[0]
        answer.append(colour)
        left.remove(colour)
    return tuple(answer)


def render_counts(payload, edges):
    closure = priority_closure(edges)
    if closure is None:
        return None, {'failure': 'invalid_or_cyclic_priority'}
    counts = payload['counts']
    rows = []
    groups = []
    for n in sorted(set(counts.values())):
        members = sorted(c for c, value in counts.items() if value == n)
        order = unique_group_order(members, closure)
        groups.append({'count': n, 'members': members, 'unique_order': list(order) if order is not None else None})
        if order is None:
            return None, {'failure': 'unresolved_equal_count_priority', 'groups': groups,
                          'priority_closure': [list(e) for e in closure]}
        rows.extend(order)
    width = max(counts.values())
    output = [[colour] * counts[colour] + [payload['noise']] * (width - counts[colour]) for colour in rows]
    return output, {'row_colours': rows, 'groups': groups, 'shape': [len(rows), width],
                    'priority_closure': [list(e) for e in closure],
                    'signal_output_cells': sum(counts.values()),
                    'noise_padding_cells': len(rows) * width - sum(counts.values())}


def target_order(payload, target):
    height, width = len(payload['signals']), max(payload['counts'].values())
    if (not isinstance(target, list) or len(target) != height
            or any(not isinstance(row, list) or len(row) != width
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row) for row in target)):
        return None, {'failure': 'teacher_histogram_shape_or_type_mismatch'}
    colours = [row[0] for row in target]
    if sorted(colours) != sorted(payload['signals']):
        return None, {'failure': 'teacher_signal_rows_not_bijective'}
    count_order = [payload['counts'][c] for c in colours]
    if count_order != sorted(count_order):
        return None, {'failure': 'teacher_counts_not_ascending'}
    if any(row != [c] * payload['counts'][c] + [payload['noise']] * (width - payload['counts'][c])
           for row, c in zip(target, colours)):
        return None, {'failure': 'teacher_bar_or_padding_mismatch'}
    edges = [(a, b) for a, b in zip(colours, colours[1:])
             if payload['counts'][a] == payload['counts'][b]]
    return tuple(edges), {'row_colours': colours, 'tie_edges': [list(e) for e in edges]}


def fit_teachers(teachers):
    if (not isinstance(teachers, (list, tuple)) or not teachers
            or any(not isinstance(p, dict) or 'input' not in p or 'output' not in p for p in teachers)):
        return None, {'failure': 'invalid_teachers'}
    parsed = [parse_input(p['input']) for p in teachers]
    input_records = [r for payload, r in parsed]
    if any(payload is None for payload, r in parsed):
        return None, {'failure': 'teacher_input_not_interpretable', 'input_records': input_records}
    distinct = len({tuple(tuple(row) for row in p['input']) for p in teachers})
    if distinct < 2:
        return None, {'failure': 'requires_two_distinct_teacher_inputs', 'input_records': input_records,
                      'distinct_inputs': distinct}
    targets = [target_order(payload, pair['output']) for (payload, rec), pair in zip(parsed, teachers)]
    target_records = [rec for edges, rec in targets]
    if any(edges is None for edges, rec in targets):
        return None, {'failure': 'teacher_histogram_mismatch', 'input_records': input_records,
                      'target_records': target_records}
    edges = tuple(sorted({e for es, rec in targets for e in es}))
    closure = priority_closure(edges)
    if closure is None:
        return None, {'failure': 'no_shared_priority_order', 'input_records': input_records,
                      'target_records': target_records, 'observed_tie_edges': [list(e) for e in edges]}
    rendered = [render_counts(payload, edges) for payload, rec in parsed]
    equality = [out == pair['output'] for (out, rec), pair in zip(rendered, teachers)]
    record = {'input_records': input_records, 'target_records': target_records,
              'render_records': [rec for out, rec in rendered], 'teacher_equal': equality,
              'precedence_edges': [list(e) for e in edges], 'priority_closure': [list(e) for e in closure],
              'consistent_total_colour_orders': order_count(tuple(range(10)), closure),
              'distinct_inputs': distinct}
    if not all(equality):
        return None, {**record, 'failure': 'teacher_reproduction_failed'}
    return edges, record


def predict(grid, edges):
    if priority_closure(edges) is None:
        return None, {'failure': 'invalid_or_cyclic_priority'}
    payload, rec = parse_input(grid)
    if payload is None:
        return None, {'failure': 'input_not_interpretable', 'input_record': rec}
    output, render = render_counts(payload, edges)
    if output is None:
        return None, {'failure': render['failure'], 'input_record': rec, 'render_record': render}
    return output, {'input_record': rec, 'render_record': render,
                    'precedence_edges': [list(e) for e in edges], 'all_priority_orders_agree': True}


class 遮蔽区画教材:
    def __init__(self, 教師群):
        self.色順序, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.色順序 is None:
            return None, {"failure": "全教師を再現する遮蔽区画計数なし"}
        return predict(格子, self.色順序)

    def 記録(self):
        return {"適合": self.色順序 is not None, "色順序": self.色順序}
