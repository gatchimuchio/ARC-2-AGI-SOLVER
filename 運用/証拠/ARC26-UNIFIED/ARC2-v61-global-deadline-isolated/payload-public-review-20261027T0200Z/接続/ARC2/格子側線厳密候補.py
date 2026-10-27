"""Prospective checkerboard/diamond-side view composed with accepted ray action.

New priors: a period-two spacer parity; the other parity is a square lattice
with integer coordinates ((r+c-p)/2, (r-c-p)/2); one complete hollow rectangle
of a fitted frame colour; optional complete, monochrome bars one lattice step
outside its sides. All pixels belong to spacer, substrate, frame, or a bar.
The finite application grammar emits from bar endpoints or every bar cell,
in the outward or inward side-normal direction. Colour roles are fitted, not
fixed numeric constants. No task identity, output lookup, or background mode.

The accepted finite ray graph draws on the original grid. No reflector roles
are declared here; its reflection-policy arguments are consequently inert.
Exceptions, including resource errors, propagate unchanged.
"""
from copy import deepcopy
from itertools import permutations, product

from .色線反射候補 import execute_graph
from .色線反射教材 import valid_grid


def observe(observer, kind, **values):
    if observer is not None:
        observer(deepcopy(dict(kind=kind, **values)))


def parse_view(grid, roles):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    spacer, substrate, frame = roles
    if len(set(roles)) != 3:
        return None, {'failure': 'aliased_roles'}
    h, w = len(grid), len(grid[0])
    universe = {(r, c) for r in range(h) for c in range(w)}
    spacer_cells = {(r, c) for r, c in universe if grid[r][c] == spacer}
    phases = {(r+c) % 2 for r, c in spacer_cells}
    if len(phases) != 1:
        return None, {'failure': 'spacer_not_single_parity'}
    phase = next(iter(phases))
    if spacer_cells != {(r, c) for r, c in universe if (r+c) % 2 == phase}:
        return None, {'failure': 'spacer_parity_incomplete'}
    parity = 1-phase

    def uv(cell):
        r, c = cell
        return (r+c-parity)//2, (r-c-parity)//2

    def rc(cell):
        u, v = cell
        return u+v+parity, u-v

    frame_cells = {(r, c) for r, c in universe if grid[r][c] == frame}
    if not frame_cells:
        return None, {'failure': 'missing_frame'}
    lattice_frame = {uv(p) for p in frame_cells}
    u0, u1 = min(u for u, v in lattice_frame), max(u for u, v in lattice_frame)
    v0, v1 = min(v for u, v in lattice_frame), max(v for u, v in lattice_frame)
    if u1-u0 < 2 or v1-v0 < 2:
        return None, {'failure': 'frame_has_no_interior'}
    expected_frame = {(u, v) for u in range(u0, u1+1) for v in range(v0, v1+1)
                      if u in (u0, u1) or v in (v0, v1)}
    if lattice_frame != expected_frame:
        return None, {'failure': 'incomplete_lattice_rectangle_frame'}
    side_specs = [
        ('u_low', [(u0-1, v) for v in range(v0, v1+1)], (-1, -1)),
        ('u_high', [(u1+1, v) for v in range(v0, v1+1)], (1, 1)),
        ('v_low', [(u, v0-1) for u in range(u0, u1+1)], (-1, 1)),
        ('v_high', [(u, v1+1) for u in range(u0, u1+1)], (1, -1)),
    ]
    bars, sides, owned = [], [], set(frame_cells)
    for name, lattice_cells, normal in side_specs:
        cells = [rc(p) for p in lattice_cells]
        present = [p for p in cells if p in universe and grid[p[0]][p[1]] != substrate]
        if not present:
            sides.append(dict(side=name, status='inactive', cells=cells))
            continue
        colours = {grid[r][c] for r, c in present}
        if len(present) != len(cells) or len(colours) != 1 or colours & set(roles):
            return None, {'failure': 'side_not_complete_monochrome_bar', 'side': name,
                          'completed_sides': sides, 'side_cells': cells, 'present': present}
        if owned & set(cells):
            return None, {'failure': 'overlapping_input_roles'}
        colour = next(iter(colours))
        bar = dict(id=len(bars), kind='source', side=name, colour=colour,
                   cells=cells, normal=normal)
        bars.append(bar)
        sides.append(dict(side=name, status='bar', colour=colour, cells=cells))
        owned.update(cells)
    if not bars:
        return None, {'failure': 'no_bars', 'sides': sides}
    foreground = universe-spacer_cells-{(r, c) for r, c in universe if grid[r][c] == substrate}
    if owned != foreground:
        return None, {'failure': 'unowned_active_cells', 'cells': sorted(foreground-owned),
                      'sides': sides}
    groups = dict(spacer=sorted(spacer_cells), frame=sorted(frame_cells),
                  bars=[b['cells'] for b in bars], substrate=sorted(universe-spacer_cells-owned))
    record = dict(roles=list(roles), parity=parity, frame_bounds=[u0, v0, u1, v1],
                  sides=sides, ownership=groups, owned_pixel_count=len(universe))
    return dict(background=substrate, glyphs=bars, sources=bars), record


def render(grid, model, observer=None):
    spacer, substrate, frame, emission, sign = model
    if emission not in ('ends', 'all') or sign not in (-1, 1):
        return None, {'failure': 'invalid_application_program'}
    scene, record = parse_view(grid, (spacer, substrate, frame))
    observe(observer, 'view_return', model=model, scene=scene, record=record)
    if scene is None:
        return None, record
    initial = []
    for bar in scene['sources']:
        starts = (bar['cells'][0], bar['cells'][-1]) if emission == 'ends' else bar['cells']
        dr, dc = (sign*x for x in bar['normal'])
        for r, c in starts:
            initial.append((bar['id'], r+dr, c+dc, dr, dc, bar['colour']))
    output, graph = execute_graph(grid, scene, record, (1, 'reflector', 'reflect'),
                                  initial, observer=observer)
    return output, dict(view_and_graph=graph, model=list(model))


def fit(teachers, observer=None):
    if (type(teachers) not in (list, tuple) or len(teachers) < 2
            or any(type(p) is not dict or set(p) != {'input', 'output'}
                   or not valid_grid(p['input']) or not valid_grid(p['output']) for p in teachers)):
        return (), {'failure': 'invalid_or_insufficient_teachers'}
    if len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return (), {'failure': 'duplicate_teacher_inputs'}
    common = set.intersection(*[{c for row in p['input'] for c in row} for p in teachers])
    declared = [(*roles, emission, sign) for roles in permutations(sorted(common), 3)
                for emission, sign in product(('ends', 'all'), (-1, 1))]
    models, returns = [], []
    for model in declared:
        trials = []
        for i, pair in enumerate(teachers):
            observe(observer, 'render_start', model=model, teacher=i)
            output, record = render(pair['input'], model, observer)
            trial = dict(teacher=i, output=output, record=record, exact=output == pair['output'])
            trials.append(trial)
            observe(observer, 'render_return', model=model, **trial)
        fitted = all(t['exact'] for t in trials)
        returns.append(dict(model=list(model), teachers=trials, all_exact=fitted))
        if fitted:
            models.append(model)
    return tuple(models), dict(declared_models=[list(m) for m in declared], returns=returns,
                               retained_models=[list(m) for m in models])


def predict(grid, models, observer=None):
    returns = []
    for model in models:
        output, record = render(grid, model, observer)
        returns.append(dict(model=list(model), output=output, record=record))
    record = {'returns': returns}
    if not returns:
        return None, dict(record, failure='no_retained_models')
    if any(r['output'] is None for r in returns):
        return None, dict(record, failure='retained_model_failed')
    if any(r['output'] != returns[0]['output'] for r in returns):
        return None, dict(record, failure='retained_model_disagreement')
    return returns[0]['output'], record
