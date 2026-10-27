"""Finite whole-body contact/exit relation; prospective candidate, no HDS adapter."""
from collections import Counter, deque
from itertools import permutations, product
from 接続.ARC2.凡例旋回教材 import body_components, valid_grid
from 接続.ARC2.既存凡例穴対応 import clone_grid

DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))
PROGRAMS = tuple(product(('absorb', 'continue'), ('erase', 'preserve')))


def add(p, d):
    return p[0] + d[0], p[1] + d[1]


def in_grid(p, grid):
    return 0 <= p[0] < len(grid) and 0 <= p[1] < len(grid[0])


def parse(grid):
    if not valid_grid(grid):
        return [], {'failure': 'invalid_grid', 'all_role_trials': []}
    counts = Counter(v for row in grid for v in row)
    modes = [v for v, count in counts.items() if count == max(counts.values())]
    if len(modes) != 1:
        return [], {'failure': 'background_tie', 'modes': sorted(modes), 'all_role_trials': []}
    bg = modes[0]
    palette = sorted(set(counts) - {bg})
    if len(palette) != 4:
        return [], {'failure': 'five_role_palette_required', 'palette': sorted(counts), 'all_role_trials': []}
    locations = {v: {(r, c) for r, row in enumerate(grid) for c, x in enumerate(row) if x == v}
                 for v in palette}
    trials, roles = [], []
    for tail, head, body, port in permutations(palette):
        trial = {'background': bg, 'tail_color': tail, 'head_color': head,
                 'body_color': body, 'port_color': port, 'failure': None}
        trials.append(trial)
        if len(locations[head]) != 1:
            trial['failure'] = 'head_not_singleton'
            continue
        point = next(iter(locations[head]))
        source_directions = []
        for dr, dc in DIRECTIONS:
            expected = {(point[0] - k * dr, point[1] - k * dc)
                        for k in range(1, len(locations[tail]) + 1)}
            if locations[tail] == expected:
                source_directions.append((dr, dc))
        trial['source_directions'] = source_directions
        if not source_directions:
            trial['failure'] = 'tail_not_contiguous_axis_from_head'
            continue
        # View-only recoloring delegates whole connected ownership to the old helper.
        view = [[body if v in (body, port) else bg for v in row] for row in grid]
        components = body_components(view, bg)
        bodies, failures = [], []
        for index, component in enumerate(components):
            cells = component['cells']
            exit_cells = cells & locations[port]
            payload = cells & locations[body]
            t, l, b, r = component['bbox']
            normals = []
            for dr, dc in DIRECTIONS:
                if not exit_cells or not payload:
                    continue
                on_face = (all(x == t for x, y in exit_cells) if dr == -1 else
                           all(x == b for x, y in exit_cells) if dr == 1 else
                           all(y == l for x, y in exit_cells) if dc == -1 else
                           all(y == r for x, y in exit_cells))
                coordinates = sorted(y if dr else x for x, y in exit_cells)
                contiguous = coordinates == list(range(coordinates[0], coordinates[-1] + 1))
                if on_face and contiguous and all((x - dr, y - dc) in payload for x, y in exit_cells):
                    normals.append((dr, dc))
            record = {'id': index, 'cells': sorted(cells), 'payload': sorted(payload),
                      'exit_cells': sorted(exit_cells), 'bbox': list(component['bbox']), 'normals': normals}
            bodies.append(record)
            if not normals:
                failures.append({'body': index, 'failure': 'whole_body_exit_face_unresolved'})
        trial['bodies'] = bodies
        trial['body_failures'] = failures
        if not bodies or failures:
            trial['failure'] = 'body_role_coverage_failed'
            continue
        source_cells = locations[tail] | locations[head]
        owned = source_cells | set().union(*(set(map(tuple, x['cells'])) for x in bodies))
        foreground = set().union(*locations.values())
        if owned != foreground:
            trial['failure'] = 'foreground_not_completely_owned'
            continue
        trial['accepted_role_indices'] = []
        for direction in source_directions:
            for normal_tuple in product(*(b['normals'] for b in bodies)):
                role = {k: trial[k] for k in ('background', 'tail_color', 'head_color', 'body_color', 'port_color')}
                role.update(head=point, source_cells=sorted(source_cells), heading=direction,
                            bodies=[{**b, 'outward': normal} for b, normal in zip(bodies, normal_tuple)])
                trial['accepted_role_indices'].append(len(roles))
                roles.append(role)
    return roles, {'background': bg, 'all_role_trials': trials, 'role_count': len(roles)}


def execute(grid, role, program):
    contact_policy, inactive_policy = program
    h, w = len(grid), len(grid[0])
    body_at = {tuple(p): b['id'] for b in role['bodies'] for p in b['cells']}
    bodies = {b['id']: b for b in role['bodies']}
    head, direction = tuple(role['head']), tuple(role['heading'])
    pending = deque([(*add(head, direction), *direction)])
    visited, activated = set(), set()
    paint = set(map(tuple, role['source_cells']))
    states, exits, revisits, activations = [], [], [], []
    while pending:
        state = pending.popleft()
        r, c, dr, dc = state
        if not (0 <= r < h and 0 <= c < w):
            exits.append(state)
            continue
        if state in visited:
            revisits.append(state)
            continue
        visited.add(state)
        cell, d = (r, c), (dr, dc)
        paint.add(cell)
        hit = body_at.get(cell)
        next_states = []
        if hit is not None:
            b = bodies[hit]
            if hit not in activated:
                activated.add(hit)
                paint.update(map(tuple, b['cells']))
                outgoing = tuple(b['outward'])
                emitted = [(*add(tuple(p), outgoing), *outgoing) for p in b['exit_cells']]
                pending.extend(emitted)
                next_states.extend(emitted)
                activations.append({'body': hit, 'contact': state, 'emitted': emitted})
            if contact_policy == 'continue':
                successor = (*add(cell, d), *d)
                pending.append(successor)
                next_states.append(successor)
        else:
            successor = (*add(cell, d), *d)
            pending.append(successor)
            next_states.append(successor)
        states.append({'state': state, 'body_hit': hit, 'successors': next_states})
    output = [[role['background']] * w for _ in range(h)]
    preserved = []
    if inactive_policy == 'preserve':
        for b in role['bodies']:
            if b['id'] not in activated:
                for r, c in b['cells']:
                    output[r][c] = grid[r][c]
                    preserved.append((r, c))
    for r, c in paint:
        output[r][c] = role['tail_color']
    return output, {'role': role, 'program': program, 'states': states, 'state_count': len(visited),
                    'state_space_bound': 4*h*w, 'exits': exits, 'revisits': revisits,
                    'activations': activations, 'activated': sorted(activated),
                    'inactive': sorted(set(bodies) - activated), 'paint': sorted(paint),
                    'preserved_inactive_cells': sorted(preserved)}

