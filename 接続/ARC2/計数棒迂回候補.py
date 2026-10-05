"""Teacher-only finite counted-bar experiment. Pure input renderer, no external IO."""
from collections import Counter
from 接続.ARC2.凡例旋回教材 import valid_grid, body_components
from 接続.ARC2.既存凡例穴対応 import clone_grid
from 接続.ARC2.境界点周期候補 import DIRECTIONS, line_cells

PROGRAMS = (0, 1)


def parse(grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid', 'roles': []}
    h, w = len(grid), len(grid[0])
    counts = Counter(v for row in grid for v in row)
    modes = [c for c, n in counts.items() if n == max(counts.values())]
    record = {'counts': dict(counts), 'background_candidates': modes, 'roles': []}
    if len(modes) != 1:
        return None, dict(record, failure='background_tie')
    bg = modes[0]
    if len(counts) != 4:
        return None, dict(record, failure='palette_not_four')
    roles = []
    for seed in sorted(c for c in counts if c != bg and counts[c] == 1):
        cell = next((r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == seed)
        boundary_sides = [d for d, yes in zip(('down', 'up', 'right', 'left'),
                          (cell[0] == 0, cell[0] == h-1, cell[1] == 0, cell[1] == w-1)) if yes]
        attempt = {'seed_colour': seed, 'seed_cell': cell, 'inward_candidates': boundary_sides,
                   'bars': [], 'errors': []}
        record['roles'].append(attempt)
        if len(boundary_sides) != 1:
            attempt['errors'].append('seed_not_unique_noncorner_boundary'); continue
        direction = boundary_sides[0]
        assert direction in DIRECTIONS
        lanes = line_cells(h, w, direction)
        coordinates = {p: (u, v) for v, lane in enumerate(lanes) for u, p in enumerate(lane)}
        U, V = len(lanes[0]), len(lanes)
        colours = set(counts) - {bg, seed}
        # Reuse C4 component primitive on a colour-equivalence view. This view
        # merges the two prospective bar colours without deleting any foreground.
        representative = min(colours)
        view = [[representative if c in colours else bg for c in row] for row in grid]
        components = body_components(view, bg)
        if not components:
            attempt['errors'].append('no_bars')
        for index, comp in enumerate(components):
            cells = sorted(comp['cells'])
            uv = [coordinates[p] for p in cells]
            us, vs = {p[0] for p in uv}, {p[1] for p in uv}
            colour_counts = Counter(grid[r][c] for r, c in cells)
            bar = {'id': index, 'cells': cells, 'canonical_cells': uv,
                   'colour_counts': dict(colour_counts), 'errors': []}
            attempt['bars'].append(bar)
            if len(us) != 1 or len(cells) < 2 or max(vs)-min(vs)+1 != len(cells):
                bar['errors'].append('not_straight_perpendicular_bar'); continue
            u = next(iter(us)); left, right = min(vs), max(vs)
            anchors = [v for v in (left, right) if v in (0, V-1)]
            if len(anchors) != 1 or u in (0, U-1):
                bar['errors'].append('not_one_attached_endpoint'); continue
            if set(colour_counts) != colours:
                bar['errors'].append('bar_not_two_colours'); continue
            anchor = anchors[0]
            free = right if anchor == left else left
            count_colour = grid[lanes[anchor][u][0]][lanes[anchor][u][1]]
            normal_colour = next(iter(colours - {count_colour}))
            bar.update(axis=u, lo=left, hi=right, anchor=anchor, free=free,
                       outward=1 if free > anchor else -1,
                       count_colour=count_colour, normal_colour=normal_colour,
                       count=colour_counts[count_colour])
        if any(b['errors'] for b in attempt['bars']):
            attempt['errors'].append('bar_structural_failure')
        if not attempt['errors']:
            if len({b['count_colour'] for b in attempt['bars']}) != 1:
                attempt['errors'].append('inconsistent_boundary_counter_colour')
        attempt['direction'] = direction
        attempt['foreground_coverage'] = sum(len(b['cells']) for b in attempt['bars'])+1
        if attempt['foreground_coverage'] != h*w-counts[bg]:
            attempt['errors'].append('foreground_not_owned')
        if not attempt['errors']:
            roles.append(dict(background=bg, seed_colour=seed, seed_cell=cell,
                              seed_uv=coordinates[cell], direction=direction,
                              lanes=lanes, U=U, V=V, bars=attempt['bars']))
    record['raw_role_count'] = len(roles)
    if len(roles) != 1:
        return None, dict(record, failure='raw_role_count_not_one')
    return roles[0], record


def render(grid, program, budget=None):
    if program not in PROGRAMS or type(program) is not int:
        return None, {'failure': 'invalid_program'}
    scene, record = parse(grid)
    record = dict(record, program=program, states=[], segments=[], turns=[], paths=[], work=0)
    if scene is None:
        return None, record
    bars = sorted(scene['bars'], key=lambda b: b['axis'])
    if len({b['axis'] for b in bars}) != len(bars):
        return None, dict(record, failure='bar_axis_tie')
    U, V, lanes = scene['U'], scene['V'], scene['lanes']
    current = scene['seed_uv']
    seen_states, cells, failures = set(), [], []

    def segment(destination, owner, phase):
        nonlocal current
        du, dv = destination[0]-current[0], destination[1]-current[1]
        if du and dv:
            raise AssertionError('non-axis segment')
        direction = (0 if du == 0 else (1 if du > 0 else -1),
                     0 if dv == 0 else (1 if dv > 0 else -1))
        steps = max(abs(du), abs(dv))
        record['segments'].append({'start': current, 'end': destination, 'owner': owner, 'phase': phase})
        points = [current] if not cells else []
        points += [(current[0]+i*direction[0], current[1]+i*direction[1]) for i in range(1, steps+1)]
        for uv in points:
            record['work'] += 1
            if budget is not None and record['work'] > budget:
                failures.append('resource_incomplete'); return False
            state = (*uv, *direction, owner, phase)
            if state in seen_states:
                failures.append('finite_state_cycle'); return False
            seen_states.add(state)
            record['states'].append({'state': state, 'in_bounds': 0 <= uv[0] < U and 0 <= uv[1] < V})
            if not (0 <= uv[0] < U and 0 <= uv[1] < V):
                failures.append('trajectory_out_of_bounds'); return False
            p = lanes[uv[1]][uv[0]]
            if p in cells:
                failures.append('path_revisited_cell'); return False
            if grid[p[0]][p[1]] != scene['background'] and p != scene['seed_cell']:
                failures.append('foreground_collision'); return False
            cells.append(p)
        current = destination
        return True

    for bar in bars:
        k = bar['count']+program
        if not bar['lo'] <= current[1] <= bar['hi']:
            failures.append('next_bar_not_intersected'); break
        trigger = (bar['axis']-k, current[1])
        destination = (trigger[0], bar['free']+bar['outward']*k)
        record['turns'].append({'bar': bar['id'], 'count': bar['count'], 'clearance': k,
                                'first_turn_uv': trigger, 'second_turn_uv': destination})
        if trigger[0] < current[0]:
            failures.append('backward_trigger'); break
        if not segment(trigger, bar['id'], 'primary'):
            break
        if not segment(destination, bar['id'], 'detour'):
            break
    if not failures:
        segment((U-1, current[1]), None, 'terminal_primary')
    record['paths'] = [cells]
    record['state_space_bound'] = 4*U*V*(len(bars)+1)*3
    record['failures'] = failures
    if failures:
        return None, dict(record, failure=failures[0],
                          status='resource_incomplete' if failures[0]=='resource_incomplete' else 'HOLD')
    distances = []
    for bar in bars:
        distances.append({'bar': bar['id'], 'required': bar['count']+program,
                          'minimum': min(max(abs(a[0]-b[0]), abs(a[1]-b[1])) for a in cells for b in bar['cells'])})
    record['clearance_checks'] = distances
    if any(d['minimum'] != d['required'] for d in distances):
        return None, dict(record, failure='whole_path_clearance_failed', status='HOLD')
    output = clone_grid(grid)
    normal = bars[0]['normal_colour']
    for bar in bars:
        for r, c in bar['cells']:
            output[r][c] = normal
    for r, c in cells:
        output[r][c] = scene['seed_colour']
    path_set = set(cells)
    bar_cells = {p for bar in bars for p in bar['cells']}
    record['conservation'] = {
        'same_size': (len(output), len(output[0])) == (len(grid), len(grid[0])),
        'seed_preserved': output[scene['seed_cell'][0]][scene['seed_cell'][1]] == scene['seed_colour'],
        'all_bar_cells_normalized': all(output[r][c] == normal for r, c in bar_cells),
        'outside_owned_changes_preserved': all(output[r][c] == grid[r][c] for r in range(len(grid)) for c in range(len(grid[0])) if (r,c) not in path_set|bar_cells),
        'all_bars_own_two_turns': len(record['turns']) == len(bars),
        'path_and_bar_disjoint': not path_set & bar_cells,
    }
    if not all(record['conservation'].values()):
        return None, dict(record, failure='conservation_failure')
    record.update(status='complete', added_path_cells=len(cells)-1,
                  normalized_counter_cells=sum(b['count'] for b in bars),
                  owned_bar_cells=len(bar_cells), owned_path_cells=len(cells))
    return output, record


def fit(teachers):
    returns, retained = [], []
    for program in PROGRAMS:
        calls = []
        for i, pair in enumerate(teachers):
            output, record = render(pair['input'], program)
            calls.append({'teacher': i, 'output': output, 'record': record, 'exact': output == pair['output']})
        returns.append({'program': program, 'teachers': calls, 'all_exact': all(c['exact'] for c in calls)})
        if returns[-1]['all_exact']:
            retained.append(program)
    return tuple(retained), returns


def consensus(grid, programs, budget=None):
    returns = [{'program': p, 'output': output, 'record': record}
               for p in programs for output, record in [render(grid, p, budget=budget)]]
    if not returns:
        return None, {'failure': 'no_retained_programs', 'returns': returns}
    if any(r['output'] is None for r in returns):
        return None, {'failure': 'retained_program_failed', 'returns': returns}
    if any(r['output'] != returns[0]['output'] for r in returns):
        return None, {'failure': 'retained_program_conflict', 'returns': returns}
    return returns[0]['output'], {'returns': returns}
