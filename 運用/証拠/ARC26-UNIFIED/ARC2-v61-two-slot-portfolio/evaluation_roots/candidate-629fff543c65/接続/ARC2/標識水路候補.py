"""Frozen finite boundary-channel endpoint relation. No data or file access."""
from collections import Counter
from copy import deepcopy
from 接続.ARC2.境界点周期候補 import valid_grid, line_cells, DIRECTIONS, merge_proposals
from 接続.ARC2.凡例旋回教材 import body_components
from 接続.ARC2.境界色経路候補 import add, within

PROGRAMS = ('initial_color', 'refreshed_color', 'any_color')
DELTAS = {'right': (0, 1), 'left': (0, -1), 'down': (1, 0), 'up': (-1, 0)}
RESOURCE_ERRORS = (MemoryError, RecursionError, TimeoutError)


def emit(observer, kind, **values):
    if observer is not None:
        observer(deepcopy({'kind': kind, **values}))


def parse(grid):
    record = {'role_trials': []}
    if not valid_grid(grid):
        return None, dict(record, failure='invalid_arc_grid')
    h, w = len(grid), len(grid[0])
    counts = Counter(v for row in grid for v in row)
    modes = sorted(v for v, n in counts.items() if n == max(counts.values()))
    record.update(counts=dict(counts), background_candidates=modes)
    if len(modes) != 1:
        return None, dict(record, failure='background_not_unique_mode')
    bg = modes[0]
    roles = []
    for direction in DIRECTIONS:
        lanes = line_cells(h, w, direction)
        rail = [lane[0] for lane in lanes]
        colors = {grid[r][c] for r, c in rail}
        trial = {'direction': direction, 'rail': rail, 'rail_colors': sorted(colors), 'errors': []}
        record['role_trials'].append(trial)
        if len(lanes[0]) < 3 or len(lanes) < 3:
            trial['errors'].append('insufficient_dimensions')
        if len(colors) != 1 or bg in colors:
            trial['errors'].append('rail_not_monochrome_foreground')
            continue
        marker = next(iter(colors))
        marker_cells = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == marker}
        if marker_cells != set(rail):
            trial['errors'].append('marker_color_not_exactly_owned_by_rail')
        if len(lanes[0]) >= 2 and any(grid[lane[1][0]][lane[1][1]] != bg for lane in lanes):
            trial['errors'].append('adjacent_strip_not_background')
        if not trial['errors']:
            roles.append({'direction': direction, 'marker': marker, 'background': bg, 'lanes': lanes, 'rail': rail})
    record['raw_role_count'] = len(roles)
    if len(roles) != 1:
        return None, dict(record, failure='raw_role_not_unique')
    role = roles[0]
    components = body_components(grid, bg)
    barriers = [dict(c, cells=sorted(c['cells'])) for c in components if c['color'] != role['marker']]
    background_cells = [(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == bg]
    groups = [set(background_cells), set(role['rail'])] + [set(c['cells']) for c in barriers]
    owned = set().union(*groups)
    if sum(len(g) for g in groups) != h*w or owned != {(r, c) for r in range(h) for c in range(w)}:
        raise AssertionError('whole input ownership failed')
    role['barriers'] = barriers
    record.update(role=role, ownership={'background': background_cells, 'marker_rail': role['rail'], 'barriers': barriers,
                                      'owned_cell_count': len(owned), 'disjoint': True})
    return role, record


def launch_records(grid, role):
    h, w = len(grid), len(grid[0])
    bg, marker = role['background'], role['marker']
    d = DELTAS[role['direction']]
    side = (-d[1], d[0])
    launches = []
    for lane in role['lanes']:
        rec = {'source': lane[0], 'scan': [], 'active': False}
        for p in lane[1:]:
            a, b = add(p, side), add(p, (-side[0], -side[1]))
            center = grid[p[0]][p[1]]
            vals = [grid[q[0]][q[1]] if within(q, h, w) else None for q in (a, b)]
            rec['scan'].append({'cell': p, 'center': center, 'flanks': [a, b], 'values': vals})
            if center != bg:
                rec['reason'] = 'center_obstacle_before_channel'; break
            if None in vals:
                rec['reason'] = 'missing_flank'; break
            if any(v not in (bg, marker) for v in vals):
                if vals[0] == vals[1] and vals[0] not in (bg, marker):
                    rec.update(active=True, initial_color=vals[0], channel_entry=p, reason='first_flanks_equal')
                else:
                    rec['reason'] = 'first_flanks_unequal'
                break
        else:
            rec['reason'] = 'no_barrier_flanks'
        launches.append(rec)
    return launches


def render(grid, program, observer=None, state_limit=None):
    record = {'program': program, 'traces': [], 'states_completed': 0}
    try:
        if type(program) is not str or program not in PROGRAMS:
            return None, dict(record, failure='invalid_program')
        role, parsed = parse(grid)
        record['parse'] = parsed
        if role is None:
            return None, dict(record, failure=parsed['failure'])
        h, w = len(grid), len(grid[0])
        bg, marker = role['background'], role['marker']
        launches = launch_records(grid, role)
        record['launches'] = launches
        proposals, destinations = [], []
        for launch in launches:
            if not launch['active']:
                continue
            p, d, color = launch['source'], DELTAS[role['direction']], launch['initial_color']
            trace = {'source': p, 'initial_color': color, 'states': [], 'turns': [], 'state_space_bound': 4*h*w*len({c['color'] for c in role['barriers']})}
            record['traces'].append(trace)
            seen = set()
            for _ in range(trace['state_space_bound']):
                if state_limit is not None and record['states_completed'] >= state_limit:
                    raise TimeoutError('explicit diagnostic state limit reached')
                side = (-d[1], d[0])
                flank_cells = [add(p, side), add(p, (-side[0], -side[1]))]
                flank_values = [grid[q[0]][q[1]] if within(q, h, w) else None for q in flank_cells]
                if program == 'refreshed_color' and flank_values[0] == flank_values[1] and flank_values[0] not in (None, bg, marker):
                    color = flank_values[0]
                state = (*p, *d, color)
                if state in seen:
                    trace['termination'] = 'state_cycle'
                    return None, dict(record, failure='state_cycle')
                seen.add(state)
                trace['states'].append({'cell': p, 'direction': d, 'active_color': color, 'flanks': flank_cells, 'flank_values': flank_values})
                record['states_completed'] += 1
                emit(observer, 'state_completed', program=program, source=launch['source'], state=trace['states'][-1], states_completed=record['states_completed'])
                q = add(p, d)
                if not within(q, h, w):
                    trace['termination'] = 'canvas_exit'; break
                front = grid[q[0]][q[1]]
                if front == bg:
                    p = q; continue
                if front == marker or (program != 'any_color' and front != color):
                    trace.update(termination='foreign_obstacle', obstacle=q, obstacle_color=front); break
                open_sides = [s for s, cell, value in zip((side, (-side[0], -side[1])), flank_cells, flank_values) if within(cell, h, w) and value == bg]
                if len(open_sides) != 1:
                    trace.update(termination='turn_not_unique', obstacle=q, obstacle_color=front, open_sides=open_sides); break
                d = open_sides[0]
                trace['turns'].append({'cell': p, 'obstacle': q, 'obstacle_color': front, 'direction_after': d})
                p = add(p, d)
            else:
                trace['termination'] = 'finite_bound_exhausted'
                return None, dict(record, failure='finite_bound_exhausted')
            trace['destination'] = p
            if p == launch['source'] or grid[p[0]][p[1]] != bg:
                return None, dict(record, failure='destination_not_fresh_background')
            destinations.append(p)
            proposals.extend([[*launch['source'], bg], [*p, marker]])
        if len(set(destinations)) != len(destinations):
            return None, dict(record, failure='endpoint_collision')
        output, merge = merge_proposals(grid, proposals)
        record['merge'] = merge
        if output is None:
            return None, dict(record, failure=merge['failure'])
        changed = {(r, c) for r in range(h) for c in range(w) if output[r][c] != grid[r][c]}
        expected_changed = {tuple(p[:2]) for p in proposals}
        original_counts = Counter(v for row in grid for v in row)
        final_counts = Counter(v for row in output for v in row)
        if changed != expected_changed or original_counts != final_counts:
            raise AssertionError('endpoint conservation failed')
        record.update(status='complete', changed_cells=sorted(changed), marker_count_preserved=True, all_other_cells_preserved=True)
        return output, record
    except BaseException as error:
        diagnostic = {'exception': type(error).__name__, 'message': str(error), 'resource_failure': isinstance(error, RESOURCE_ERRORS),
                      'semantic_HOLD': False, 'input': grid, 'program': program, 'completed_resource_runtime_prefix': record}
        error.evaluation_diagnostic = deepcopy(diagnostic)
        emit(observer, 'execution_exception', **diagnostic)
        raise

