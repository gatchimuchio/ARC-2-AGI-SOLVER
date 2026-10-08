"""Prospective source-key perimeter view over the byte-frozen NEW126 core.

Only a complete zero-role structural parse enables the additional view. Every
corner-color frame interpretation survives to complete role/program reduction.
Unrelated perimeter cells are explicitly static; source-key pairs stay strict.
"""
import frozen126 as core

PROGRAMS = core.PROGRAMS
ROTATIONS = core.ROTATIONS
fit = core.fit
act = core.act


def _partial_parse(grid, original_record):
    roles, probes = [], []
    for orientation, name in enumerate(ROTATIONS):
        view = core.transform_grid_by_name(grid, name)
        h, w = len(view), len(view[0])
        for separator in core.full_height_color_columns(view):
            s, sep_color = separator['col'], separator['color']
            if s < 1 or w-s-1 < 3 or h < 3:
                continue
            left = s+1
            probe = {'orientation': name, 'separator': s}
            probes.append(probe)
            interior = {view[r][c] for r in range(1, h-1)
                        for c in range(left+1, w-1)}
            if len(interior) != 1:
                probe['failure'] = 'nonblank_interior'
                continue
            bg = next(iter(interior))
            if sep_color == bg:
                probe['failure'] = 'non_distinct_structural_colors'
                continue
            perimeter = [(r, c, view[r][c]) for r in range(h)
                         for c in range(left, w)
                         if r in (0, h-1) or c in (left, w-1)]
            if any(color == bg for r, c, color in perimeter):
                probe['failure'] = 'blank_perimeter'
                continue
            source = [row[:s] for row in view]
            masks = core.sparse_point_color_points(source, bg)
            if not masks:
                probe['failure'] = 'empty_source'
                continue
            corners = [view[r][c] for r in (0, h-1) for c in (left, w-1)]
            # A source key at a corner cannot be silently assigned to either
            # edge or reclassified as a frame/decorative cell.
            if any(color in masks for color in corners):
                probe['failure'] = 'ambiguous_source_key_corner'
                continue
            # Enumeration order is positional only. No frame candidate is
            # selected by frequency, numeric color, placement, or output.
            frames = list(dict.fromkeys(color for color in corners
                                        if color not in (bg, sep_color)))
            if not frames:
                probe['failure'] = 'no_corner_frame_candidate'
                continue
            rows, cols, conflicts = {}, {}, []
            for r in range(1, h-1):
                a, b = view[r][left], view[r][w-1]
                if a in masks or b in masks:
                    if a != b:
                        conflicts.append(('row', r, a, b))
                    else:
                        rows.setdefault(a, []).append(r)
            for c in range(left+1, w-1):
                a, b = view[0][c], view[h-1][c]
                if a in masks or b in masks:
                    if a != b:
                        conflicts.append(('column', c, a, b))
                    else:
                        cols.setdefault(a, []).append(c)
            if conflicts:
                probe['failure'] = 'unpaired_source_key'
                probe['conflicts'] = conflicts
                continue
            # Static includes every non-source-key perimeter cell, including
            # all frame candidates and decorations. The exact core action
            # copies these unchanged and writes only source/interior cells.
            static = [(r, c, color) for r, c, color in perimeter
                      if color not in masks]
            probe['frame_candidates'] = frames
            probe['role_indices'] = []
            for frame in frames:
                probe['role_indices'].append(len(roles))
                roles.append(dict(view=view, source=source, orientation=orientation,
                                  separator=s, left=left, background=bg,
                                  masks=masks, rows=rows, cols=cols, frame=frame,
                                  static_perimeter=static))
    return roles, dict(roles=len(roles), probes=probes,
                       input_view='partial_source_key_perimeter',
                       original_parse=original_record)


def _views(grid):
    roles, record = core.parse(grid)
    if roles or not core.valid_grid(grid):
        return roles, record, False
    roles, record = _partial_parse(grid, record)
    return roles, record, True


def parse(grid):
    roles, record, extended = _views(grid)
    return roles, record


def render(grid, program):
    if tuple(program) not in PROGRAMS:
        return core.render(grid, program)
    roles, record, extended = _views(grid)
    if not extended:
        # Preserve old successes, ambiguity, and action failures wholesale.
        return core.render(grid, program)
    returns = [act(role, program) for role in roles]
    record['role_returns'] = [dict(output=out, detail=detail) for out, detail in returns]
    if not returns:
        return None, dict(record, failure='no_structural_role')
    if any(out is None for out, detail in returns):
        return None, dict(record, failure='retained_role_failed')
    if any(out != returns[0][0] for out, detail in returns):
        return None, dict(record, failure='role_grid_disagreement')
    return returns[0][0], record


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
