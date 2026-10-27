"""Certify the fixed downward run-span prior; never replace its output."""
from collections import Counter, deque
from . import 既存流路 as old
from . import 有限量流路接続 as finite


def raw_fits(teachers):
    candidates = set()
    for pair in teachers:
        inp, out = pair['input'], pair['output']
        if not old.is_rectangular(inp) or not old.is_rectangular(out) or old.grid_shape(inp) != old.grid_shape(out):
            return []
        bg = old.background_color(inp)
        changes = [(a, b) for ra, rb in zip(inp, out) for a, b in zip(ra, rb) if a != b]
        if not changes or any(a != bg for a, b in changes):
            return []
        candidates.update(b for a, b in changes if b in old.colors(inp))
    fits = []
    for flow in sorted(candidates):
        obstacles = []
        for pair in teachers:
            others = old.colors(pair['input']) - {old.background_color(pair['input']), flow}
            if len(others) != 1:
                break
            obstacles.append(next(iter(others)))
        else:
            if len(set(obstacles)) == 1:
                fit = old.CorridorFit(flow, obstacles[0])
                if all(old.gravity_corridor_route(p['input'], fit) == p['output'] for p in teachers):
                    fits.append(fit)
    return fits


def guarded_render(grid, fit, *, _obstacle_bounded=False):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    if (not isinstance(fit, old.CorridorFit)
            or any(type(v) is not int or not 0 <= v <= 9 for v in (fit.flow_color, fit.obstacle_color))
            or fit.flow_color == fit.obstacle_color):
        return None, {'failure': 'invalid_roles'}
    counts = Counter(v for row in grid for v in row)
    if sum(n == max(counts.values()) for n in counts.values()) != 1:
        return None, {'failure': 'background_tie'}
    bg = old.background_color(grid)
    flow, obstacle = fit.flow_color, fit.obstacle_color
    if bg in (flow, obstacle) or set(counts) != {bg, flow, obstacle}:
        return None, {'failure': 'palette_out_of_scope'}
    height, width = len(grid), len(grid[0])
    seeds = {(r, c) for r in range(height) for c in range(width) if grid[r][c] == flow}
    reached, active = set(seeds), deque(sorted(seeds))
    contacts, clipped = set(), set()
    while active:
        r, c = active.popleft()
        if r + 1 >= height:
            continue
        next_cells = []
        if grid[r + 1][c] in (bg, flow):
            next_cells.append((r + 1, c))
        else:
            left = right = c
            while left > 0 and grid[r + 1][left - 1] == obstacle:
                left -= 1
            while right + 1 < width and grid[r + 1][right + 1] == obstacle:
                right += 1
            contacts.add((r + 1, left, right))
            if left == 0 or right == width - 1:
                clipped.add((r + 1, left, right))
            span_left, span_right = max(0, left - 1), min(width - 1, right + 1)
            if _obstacle_bounded:
                lower, upper = span_left, span_right
                span_left = span_right = c
                while span_left > lower and grid[r][span_left - 1] != obstacle:
                    span_left -= 1
                while span_right < upper and grid[r][span_right + 1] != obstacle:
                    span_right += 1
            for col in range(span_left, span_right + 1):
                if grid[r][col] == obstacle:
                    return None, {'failure': 'triggered_span_crosses_obstacle'}
                next_cells.append((r, col))
        for cell in next_cells:
            if cell not in reached:
                reached.add(cell)
                active.append(cell)
    expected = [row[:] for row in grid]
    for r, c in reached:
        expected[r][c] = flow
    output = old.gravity_corridor_route(grid, fit)
    if output is None:
        return None, {'failure': 'source_no_candidate'}
    if output != expected:
        return None, {'failure': 'source_output_disagrees'}
    if any(output[r][c] != value for r, row in enumerate(grid) for c, value in enumerate(row) if value != bg):
        return None, {'failure': 'original_foreground_changed'}
    return output, {'background': bg, 'flow': flow, 'obstacle': obstacle,
                    'seed_count': len(seeds), 'added_flow': len(reached - seeds),
                    'obstacle_run_contacts': len(contacts), 'clipped_exit_runs': len(clipped)}


def fit_guarded(teachers):
    if not teachers or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return None
    fits = raw_fits(teachers)
    if len(fits) != 1:
        return None
    fit = fits[0]
    if not all(guarded_render(p['input'], fit)[0] == p['output'] for p in teachers):
        return None
    return fit


class 流路教材:
    def __init__(self, 教師群):
        self.役割 = fit_guarded(教師群) if finite.valid_teachers(教師群) else None
        self.有限役割 = () if self.役割 is not None else finite.fit(教師群)

    def 候補(self, 格子, _policy):
        if self.有限役割:
            return finite.consensus(格子, self.有限役割)
        if self.役割 is None:
            return None, {'failure': '全教師を再現する流路役割なし'}
        output, record = guarded_render(格子, self.役割)
        if record.get('failure') != 'triggered_span_crosses_obstacle':
            return output, record
        bounded, detail = guarded_render(格子, self.役割, _obstacle_bounded=True)
        return (bounded, detail) if bounded is not None else (output, record)

    def 記録(self):
        if self.有限役割:
            return {'全教師再現': True, 'flow': None, 'obstacle': None,
                    'mode': 'prospective_finite_material_composition',
                    '有限役割': self.有限役割}
        return {'全教師再現': self.役割 is not None,
                'flow': None if self.役割 is None else self.役割.flow_color,
                'obstacle': None if self.役割 is None else self.役割.obstacle_color}
