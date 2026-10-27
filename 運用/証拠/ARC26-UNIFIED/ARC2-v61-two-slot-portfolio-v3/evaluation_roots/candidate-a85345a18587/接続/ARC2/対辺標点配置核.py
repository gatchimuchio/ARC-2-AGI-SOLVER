"""Input-only separator / opposite-edge anchors / translated mask composition.

The geometric view and finite overlap controls are new glue. Accepted helpers
provide separator detection, color grouping, components, transforms and shifts.
No output, identity, file access, fitted color, or training grid is retained.
"""
from itertools import product

from 接続.ARC2.既存区切投射 import full_height_color_columns
from 接続.ARC2.既存疎点転写 import sparse_point_color_points, shifted_sparse_point_mask
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.記号命令教材 import valid_grid

ROTATIONS = ('identity', 'rot90', 'rot180', 'rot270')
INVERSE = ('identity', 'rot270', 'rot180', 'rot90')
PROGRAMS = tuple(product(('color_union', 'components8'),
                         ('source_first', 'source_last', 'small_first', 'large_first')))


def parse(grid):
    if not valid_grid(grid):
        return [], {'failure': 'invalid_grid'}
    roles, probes = [], []
    for orientation, name in enumerate(ROTATIONS):
        view = transform_grid_by_name(grid, name)
        h, w = len(view), len(view[0])
        for separator in full_height_color_columns(view):
            s, sep_color = separator['col'], separator['color']
            if s < 1 or w-s-1 < 3 or h < 3:
                continue
            left = s+1
            corners = {view[r][c] for r in (0, h-1) for c in (left, w-1)}
            interior = {view[r][c] for r in range(1, h-1) for c in range(left+1, w-1)}
            probe = {'orientation': name, 'separator': s}
            probes.append(probe)
            if len(corners) != 1 or len(interior) != 1:
                probe['failure'] = 'no_corner_frame_or_blank_interior'
                continue
            frame, bg = next(iter(corners)), next(iter(interior))
            # This is the complete structural role gate. Subsequent source or
            # placement failures stay in the role set and veto the full grid.
            if len({frame, bg, sep_color}) != 3:
                probe['failure'] = 'non_distinct_structural_colors'
                continue
            if any(view[0][c] != view[h-1][c] or view[0][c] == bg
                   for c in range(left, w)) or any(
                       view[r][left] != view[r][w-1] or view[r][left] == bg
                       for r in range(h)):
                probe['failure'] = 'unpaired_or_blank_perimeter'
                continue
            source = [row[:s] for row in view]
            masks = sparse_point_color_points(source, bg)
            if not masks:
                probe['failure'] = 'empty_source'
                continue
            rows, cols = {}, {}
            for r in range(1, h-1):
                color = view[r][left]
                if color != frame:
                    rows.setdefault(color, []).append(r)
            for c in range(left+1, w-1):
                color = view[0][c]
                if color != frame:
                    cols.setdefault(color, []).append(c)
            probe['role_index'] = len(roles)
            roles.append(dict(view=view, source=source, orientation=orientation,
                              separator=s, left=left, background=bg,
                              masks=masks, rows=rows, cols=cols))
    return roles, {'roles': len(roles), 'probes': probes}


def _act(role, program, source_tie=False):
    grouping, control = program
    view, bg = role['view'], role['background']
    h, w = len(view), len(view[0])
    objects = []
    for color, cells in role['masks'].items():
        parts = ([cells] if grouping == 'color_union' else
                 [part['cells'] for part in color_components(role['source'], color, True)])
        for part in parts:
            top, bottom = min(r for r, c in part), max(r for r, c in part)
            left, right = min(c for r, c in part), max(c for r, c in part)
            objects.append(dict(color=color, cells=part, bbox=(top, left, bottom, right)))
    erased, proposals, failures, placements = set(), {}, [], []
    for obj in objects:
        color, cells = obj['color'], obj['cells']
        rows, cols = role['rows'].get(color, []), role['cols'].get(color, [])
        if not rows or not cols:
            continue
        top, left, bottom, right = obj['bbox']
        if (top+bottom) % 2 or (left+right) % 2:
            failures.append('noninteger_source_center')
            continue
        center = ((top+bottom)//2, (left+right)//2)
        # Explicit prior: only unresolved small_first ties inherit source_first.
        rank = (obj['bbox'] if control.startswith('source_') else
                ((len(cells),) + obj['bbox'] if source_tie and control == 'small_first' else (len(cells),)))
        if control in ('source_last', 'large_first'):
            rank = tuple(-x for x in rank)
        erased.update(cells)
        for r, c in product(rows, cols):
            shifted = shifted_sparse_point_mask(cells, r-center[0], c-center[1], h, w)
            if shifted is None:
                failures.append('shift_out_of_bounds')
                continue
            if any(not (0 < tr < h-1 and role['left'] < tc < w-1) for tr, tc in shifted):
                failures.append('shift_outside_frame_interior')
                continue
            placements.append(dict(color=color, source_bbox=obj['bbox'], anchor=(r, c),
                                   cell_count=len(shifted)))
            for point in shifted:
                proposals.setdefault(point, []).append((rank, color))
    out = [row[:] for row in view]
    for r, c in erased:
        out[r][c] = bg
    overlap_count = 0
    for (r, c), choices in proposals.items():
        best = min(rank for rank, color in choices)
        winners = {color for rank, color in choices if rank == best}
        if len({color for rank, color in choices}) > 1:
            overlap_count += 1
        if len(winners) != 1:
            failures.append('equal_priority_color_conflict')
        else:
            out[r][c] = next(iter(winners))
    if not placements:
        failures.append('no_placements')
    record = dict(objects=len(objects), placements=placements,
                  erased_cells=len(erased), overlap_cells=overlap_count, failures=failures)
    if failures:
        return None, record
    return transform_grid_by_name(out, INVERSE[role['orientation']]), record


def act(role, program):
    # Preserve the complete original successful/failing tuple outside the
    # explicitly declared, previously undefined equal-size overlap domain.
    original = _act(role, program)
    failures = original[1]['failures']
    if (original[0] is not None or program[1] != 'small_first' or not failures
            or any(reason != 'equal_priority_color_conflict' for reason in failures)):
        return original
    return _act(role, program, source_tie=True)


def render(grid, program):
    if tuple(program) not in PROGRAMS:
        return None, {'failure': 'unknown_program'}
    roles, record = parse(grid)
    returns = [act(role, program) for role in roles]
    record['role_returns'] = [dict(output=out, detail=detail) for out, detail in returns]
    if not returns:
        return None, dict(record, failure='no_structural_role')
    if any(out is None for out, detail in returns):
        return None, dict(record, failure='retained_role_failed')
    if any(out != returns[0][0] for out, detail in returns):
        return None, dict(record, failure='role_grid_disagreement')
    return returns[0][0], record


def fit(teachers):
    if (len(teachers) < 2 or any(not valid_grid(p.get('input')) or not valid_grid(p.get('output'))
                                for p in teachers)):
        return (), {'failure': 'invalid_teachers'}
    if len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return (), {'failure': 'duplicate_teacher_inputs'}
    retained, records = [], []
    for program in PROGRAMS:
        returns = [render(p['input'], program) for p in teachers]
        exact = [out == p['output'] for (out, detail), p in zip(returns, teachers)]
        records.append(dict(program=program, exact=exact,
                            returns=[dict(output=out, detail=detail) for out, detail in returns]))
        if all(exact):
            retained.append(program)
    return tuple(retained), dict(complete=True, program_count=len(PROGRAMS),
                                retained=retained, program_returns=records)


def consensus(grid, programs):
    returns = [render(grid, program) for program in programs]
    record = dict(complete=True, programs=list(programs),
                  program_returns=[dict(output=out, detail=detail) for out, detail in returns])
    if not returns:
        return None, dict(record, failure='no_retained_programs')
    if any(out is None for out, detail in returns):
        return None, dict(record, failure='retained_program_failed')
    if any(out != returns[0][0] for out, detail in returns):
        return None, dict(record, failure='program_grid_disagreement')
    return returns[0][0], record
