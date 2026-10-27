"""Input-only boundary color relation; six semantic functions AST-identical to frozen prototype."""
from __future__ import annotations
from 接続.ARC2 import 凡例旋回教材 as turn
from 接続.ARC2.既存凡例穴対応 import clone_grid
DIRECTIONS = ((-1, 0), (0, 1), (1, 0), (0, -1))
PHASES = ('continuous', 'contact_tick', 'reset_after_turn')

def within(p, h, w):
    return 0 <= p[0] < h and 0 <= p[1] < w


def add(p, q):
    return p[0] + q[0], p[1] + q[1]


def dot(p, q):
    return p[0] * q[0] + p[1] * q[1]


def serial(component):
    return {**component, 'cells': sorted(component['cells'])}


def parse(grid):
    if not turn.valid_grid(grid):
        return [], {'failure': 'invalid_arc_grid'}
    h, w = len(grid), len(grid[0])
    palette = sorted({v for row in grid for v in row})
    roles, trials = [], []
    for wall in palette:
        components = turn.body_components(grid, wall)
        for travel in palette:
            if wall == travel:
                continue
            special = [x for x in components if x['color'] != travel]
            squares, seeds, reason = [], [], None
            for x in special:
                r, c, b, e = x['bbox']
                if len(x['cells']) == 1:
                    seeds.append(x)
                elif b-r == e-c and b-r >= 1 and len(x['cells']) == (b-r+1)**2:
                    exterior = {add(p, d) for p in x['cells'] for d in DIRECTIONS} - x['cells']
                    if any(not within(p, h, w) or grid[p[0]][p[1]] != wall for p in exterior):
                        reason = 'square_not_enclosed_by_wall'
                        break
                    squares.append(x)
                else:
                    reason = 'unowned_special_component'
                    break
            if not reason and (not seeds or len(squares) < 3):
                reason = 'missing_seeds_or_token_inventory'
            if not reason and len({x['bbox'][2]-x['bbox'][0]+1 for x in squares}) != 1:
                reason = 'unequal_square_sizes'
            if reason:
                trials.append({'wall': wall, 'travel': travel, 'failure': reason})
                continue
            for d in DIRECTIONS:
                seed_cells = [next(iter(x['cells'])) for x in seeds]
                if any(within(add(p, (-d[0], -d[1])), h, w) or
                       not within(add(p, d), h, w) or
                       grid[p[0]+d[0]][p[1]+d[1]] != travel for p in seed_cells):
                    trials.append({'wall': wall, 'travel': travel, 'heading': d, 'failure': 'seed_edge_or_entry'})
                    continue
                v = (-d[1], d[0])
                for marker in squares:
                    legend = [x for x in squares if x is not marker]
                    legend.sort(key=lambda x: min(dot(p, d) for p in x['cells']))
                    bounds = [(min(dot(p, d) for p in x['cells']), max(dot(p, d) for p in x['cells']),
                               min(dot(p, v) for p in x['cells']), max(dot(p, v) for p in x['cells'])) for x in legend]
                    gaps = [b[0]-a[1]-1 for a, b in zip(bounds, bounds[1:])]
                    failure = None
                    if len({b[2:] for b in bounds}) != 1 or not gaps or min(gaps) <= 0 or len(set(gaps)) != 1:
                        failure = 'legend_not_regular_collinear_strip'
                    word = [x['color'] for x in legend]
                    if marker['color'] in word:
                        failure = 'contact_color_legend_alias'
                    if any(x['color'] != word[0] for x in seeds):
                        failure = 'seed_color_not_legend_start'
                    lo, hi = bounds[0][2:]
                    if all(dot(p, v) < lo for p in seed_cells):
                        second = v
                    elif all(dot(p, v) > hi for p in seed_cells):
                        second = (-v[0], -v[1])
                    else:
                        second = None
                        failure = 'seed_legend_side_unresolved'
                    trial = {'wall': wall, 'travel': travel, 'heading': d, 'marker': serial(marker)}
                    if failure:
                        trials.append({**trial, 'failure': failure})
                    else:
                        role = {**trial, 'second_heading': second, 'word': word,
                                'legend': [serial(x) for x in legend], 'seeds': sorted(seed_cells),
                                'square_size': squares[0]['bbox'][2]-squares[0]['bbox'][0]+1,
                                'gap': gaps[0]}
                        roles.append(role)
                        trials.append({**trial, 'accepted_role_index': len(roles)-1})
    return roles, {'all_role_trials': trials, 'raw_role_count': len(roles)}


def render(grid, phase_semantics):
    roles, record = parse(grid)
    if len(roles) != 1:
        return None, {**record, 'failure': 'raw_role_not_unique'}
    role = roles[0]
    h, w = len(grid), len(grid[0])
    terrain = clone_grid(grid)
    erased = set()
    for obj in role['legend'] + [role['marker']]:
        for p in obj['cells']:
            p = tuple(p)
            terrain[p[0]][p[1]] = role['wall']
            erased.add(p)
    proposal, traces, conflict = {}, [], []
    directions = (role['heading'], role['second_heading'])
    def put(p, value, owner):
        if p in proposal and proposal[p]['value'] != value:
            conflict.append({'cell': p, 'existing': proposal[p], 'new': {'value': value, 'owner': owner}})
        else:
            proposal.setdefault(p, {'value': value, 'owners': []})['owners'].append(owner)
    for seed_index, seed in enumerate(role['seeds']):
        p, index, phase = tuple(seed), 0, 0
        states, contacts, termination = [], [], None
        for _ in range(h+w-1):
            value = role['word'][phase % len(role['word'])]
            states.append({'cell': p, 'heading': directions[index], 'phase': phase,
                           'word_index': phase % len(role['word']), 'color': value})
            put(p, value, {'kind': 'path', 'seed_index': seed_index, 'step': len(states)-1})
            q = add(p, directions[index])
            if not within(q, h, w):
                termination = {'kind': 'canvas_exit', 'next': q}
                break
            if terrain[q[0]][q[1]] == role['travel']:
                p, phase = q, phase+1
                continue
            if terrain[q[0]][q[1]] != role['wall']:
                termination = {'kind': 'failure', 'failure': 'unexpected_path_object', 'next': q}
                break
            put(q, role['marker']['color'], {'kind': 'contact', 'seed_index': seed_index, 'event': len(contacts)})
            index = 1-index
            after = add(p, directions[index])
            contacts.append({'from': p, 'wall_cell': q, 'color': role['marker']['color'],
                             'heading_after': directions[index], 'next_after_turn': after})
            if not within(after, h, w) or terrain[after[0]][after[1]] != role['travel']:
                termination = {'kind': 'turn_cannot_advance', 'next': after}
                break
            p = after
            phase = 0 if phase_semantics == 'reset_after_turn' else phase+1+(phase_semantics == 'contact_tick')
        if termination is None:
            termination = {'kind': 'failure', 'failure': 'monotone_state_bound_exhausted'}
        traces.append({'seed': seed, 'states': states, 'contacts': contacts, 'termination': termination,
                       'state_bound': h+w-1})
    output = clone_grid(terrain)
    for (r, c), entry in proposal.items():
        output[r][c] = entry['value']
    detail = {**record, 'role': role, 'phase_semantics': phase_semantics, 'erased': sorted(erased),
              'traces': traces, 'proposals': [{'cell': p, **v} for p, v in sorted(proposal.items())],
              'conflicts': conflict}
    failures = [t['termination'] for t in traces if t['termination']['kind'] == 'failure']
    if conflict or failures:
        return None, {**detail, 'failure': 'conflict_or_trace_failure', 'partial_grid': output}
    return output, detail

