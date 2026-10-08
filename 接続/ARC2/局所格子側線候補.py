"""Complete local lattice scenes, gated at frozen133's ownership boundary.

Exposure: the lead's single input-only 133 call HOLDed at unowned_active_cells.
The lead then reported other complete, differently coloured hollow frames,
colours reused between frames and other objects' bars, and canvas-clipped bars.
This module's author has not read that query, any target, or any score.

Frozen133 supplies the unchanged strict teacher fit and model identities.
Its successful rendering and every other failure remain unchanged. Only the
completed unowned_active_cells boundary opens this additional input view.
All complete whole monochrome lattice-frame components are mandatory. Every
other active cell must have a unique exact-cover assignment to their complete
or canvas-clipped sides. No successful-object or successful-cover selection.
Frame roles normalize locally to the original fitted role; bar colour remains
an unfitted variable in the original palette. The ray graph is unchanged.
"""
from collections import deque

from . import 格子側線厳密候補 as strict

execute_graph = strict.execute_graph
valid_grid = strict.valid_grid
observe = strict.observe
parse_view = strict.parse_view
fit = strict.fit


def _side_specs(bounds):
    u0, v0, u1, v1 = bounds
    return [
        ('u_low', [(u0-1, v) for v in range(v0, v1+1)], (-1, -1)),
        ('u_high', [(u1+1, v) for v in range(v0, v1+1)], (1, 1)),
        ('v_low', [(u, v0-1) for u in range(u0, u1+1)], (-1, 1)),
        ('v_high', [(u, v1+1) for u in range(u0, u1+1)], (1, -1)),
    ]


def parse_local_scenes(grid, model):
    """Enumerate ownership before any ray executes; ambiguous ownership HOLDs."""
    spacer, substrate, fitted_frame, emission, sign = model
    h, w = len(grid), len(grid[0])
    universe = {(r, c) for r in range(h) for c in range(w)}
    spacer_cells = {p for p in universe if grid[p[0]][p[1]] == spacer}
    parity = 1-next(iter({(r+c) % 2 for r, c in spacer_cells}))

    def uv(p):
        r, c = p
        return (r+c-parity)//2, (r-c-parity)//2

    def rc(p):
        u, v = p
        return u+v+parity, u-v

    active = {p for p in universe if grid[p[0]][p[1]] not in (spacer, substrate)}
    unseen = set(active)
    frames, components = [], []
    while unseen:
        seed = min(unseen)
        colour = grid[seed[0]][seed[1]]
        pending, cells = deque([seed]), set()
        unseen.remove(seed)
        while pending:
            p = pending.popleft()
            cells.add(p)
            for dr, dc in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                q = (p[0]+dr, p[1]+dc)
                if q in unseen and grid[q[0]][q[1]] == colour:
                    unseen.remove(q)
                    pending.append(q)
        points = {uv(p) for p in cells}
        u0, u1 = min(u for u, v in points), max(u for u, v in points)
        v0, v1 = min(v for u, v in points), max(v for u, v in points)
        perimeter = {(u, v) for u in range(u0, u1+1) for v in range(v0, v1+1)
                     if u in (u0, u1) or v in (v0, v1)}
        is_frame = u1-u0 >= 2 and v1-v0 >= 2 and points == perimeter
        component = dict(id=len(components), colour=colour, cells=sorted(cells),
                         bounds=[u0, v0, u1, v1], complete_frame=is_frame)
        components.append(component)
        if is_frame:
            # These are semantic role maps, not additional colour-fitted models.
            # Bar colours are unbound variables, so there is no free numeric
            # palette permutation to select or discard during normalization.
            frames.append(dict(id=len(frames), component=component['id'],
                               colour=colour, cells=sorted(cells),
                               bounds=component['bounds'],
                               local_role_map={
                                   'spacer': {'input': spacer, 'fitted': spacer},
                                   'substrate': {'input': substrate, 'fitted': substrate},
                                   'frame': {'input': colour, 'fitted': fitted_frame},
                                   'bar_colour': 'unfitted original-palette variable'}))

    frame_cells = {tuple(p) for frame in frames for p in frame['cells']}
    payload = active-frame_cells
    candidates = []
    for frame in frames:
        for side, points, normal in _side_specs(frame['bounds']):
            full = [rc(p) for p in points]
            visible = [p for p in full if p in universe]
            if not visible or set(visible) & frame_cells:
                continue
            colours = {grid[r][c] for r, c in visible}
            if len(colours) != 1 or colours & {spacer, substrate, frame['colour']}:
                continue
            candidates.append(dict(id=len(candidates), kind='source', frame=frame['id'],
                                   side=side, colour=next(iter(colours)), cells=visible,
                                   full_cells=full, normal=normal,
                                   clipped_cells=[p for p in full if p not in universe]))

    covers = []
    candidate_cells = [set(c['cells']) for c in candidates]
    by_cell = {p: [i for i, cells in enumerate(candidate_cells) if p in cells]
               for p in payload}

    def cover(remaining, selected, participating):
        if not remaining:
            if participating == set(range(len(frames))):
                covers.append(sorted(selected))
            return
        cell = min(remaining, key=lambda p: (sum(candidate_cells[i] <= remaining
                                                for i in by_cell[p]), p))
        for i in by_cell[cell]:
            cells = candidate_cells[i]
            if cells <= remaining:
                cover(remaining-cells, selected+[i], participating | {candidates[i]['frame']})

    if frames:
        cover(payload, [], set())
    record = dict(model=list(model), parity=parity, components=components,
                  mandatory_frames=frames, candidate_bars=candidates,
                  ownership_covers=covers, cover_count=len(covers),
                  ownership=dict(spacer=sorted(spacer_cells), frames=sorted(frame_cells),
                                 remaining_active=sorted(payload),
                                 substrate=sorted(universe-spacer_cells-active)),
                  normalization='one explicit semantic role map per mandatory frame; '
                                'bar colours are unfitted original-palette variables')
    if not covers:
        return None, dict(record, failure='no_complete_local_scene_ownership')
    if len(covers) != 1:
        return None, dict(record, failure='ambiguous_local_scene_ownership')
    sources = [dict(candidates[i], id=j) for j, i in enumerate(covers[0])]
    record['owned_pixel_count'] = len(universe)
    return dict(background=substrate, glyphs=sources, sources=sources), record


def _cannot_enter(origin, direction, h, w):
    """A separating canvas boundary certifies every future ray point outside."""
    r, c = origin
    dr, dc = direction
    return ((r < 0 and dr <= 0) or (r >= h and dr >= 0)
            or (c < 0 and dc <= 0) or (c >= w and dc >= 0))


def render(grid, model, observer=None):
    spacer, substrate, frame, emission, sign = model
    if emission not in ('ends', 'all') or sign not in (-1, 1):
        return None, {'failure': 'invalid_application_program'}
    scene, record = parse_view(grid, (spacer, substrate, frame))
    observe(observer, 'view_return', model=model, scene=scene, record=record)
    local = scene is None and record.get('failure') == 'unowned_active_cells'
    strict_failure = record if local else None
    if local:
        scene, record = parse_local_scenes(grid, model)
        record['strict_boundary'] = strict_failure
        observe(observer, 'local_view_return', model=model, scene=scene, record=record)
    if scene is None:
        return None, record
    initial = []
    missing = []
    h, w = len(grid), len(grid[0])
    for bar in scene['sources']:
        source_cells = bar['full_cells'] if local else bar['cells']
        starts = (source_cells[0], source_cells[-1]) if emission == 'ends' else source_cells
        dr, dc = (sign*x for x in bar['normal'])
        for r, c in starts:
            if local and not (0 <= r < h and 0 <= c < w):
                proof = dict(source=bar['id'], origin=[r, c], direction=[dr, dc],
                             observed=False, executed=False,
                             cannot_enter_canvas=_cannot_enter((r, c), (dr, dc), h, w))
                missing.append(proof)
                continue
            initial.append((bar['id'], r+dr, c+dc, dr, dc, bar['colour']))
    if local:
        record['offcanvas_source_obligations'] = missing
        if any(not p['cannot_enter_canvas'] for p in missing):
            return None, dict(record, failure='unobserved_source_may_enter_canvas')
    output, graph = execute_graph(grid, scene, record, (1, 'reflector', 'reflect'),
                                  initial, observer=observer)
    return output, dict(view_and_graph=graph, model=list(model))


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
