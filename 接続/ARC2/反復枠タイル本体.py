"""Prospective shared tile-support role composed with the old annulus action.

This is a new grammar, not a repair or reinterpretation of the rejected one.
The unmodified legacy module retains all twelve original programs separately.
Only the two old body selectors and their alias check may be bypassed here.
No query, fit-selected body policy, stored grid, or color-specific choice exists.
"""

from . import 反復枠旧候補 as legacy
from .反復枠共通部品 import _bbox_for_cells, lattice_tile_mask, transform_grid_by_name

EXTERIORS = tuple(dict.fromkeys(program[0] for program in legacy.PROGRAMS))
MARKERS = tuple(dict.fromkeys(program[1] for program in legacy.PROGRAMS))
PROGRAMS = tuple((exterior, markers, 'shared_tile_spanning_color')
                 for exterior in EXTERIORS for markers in MARKERS)
OLD_BODY_FAILURES = {'foreground_mode_not_unique', 'body_selectors_disagree',
                     'marker_role_alias'}


def shared_tile_spanning_roles(grid, tile_boxes, excluded_colors):
    """Enumerate colors touching all four sides of every supplied tile.

    Pure reusable role selector: tile locations and exclusions are supplied by
    the caller. No counts, corners, adjacency heuristic, or numeric preference.
    Every eligible role is retained, including ambiguous inventories.
    """
    palette = sorted({value for row in grid for value in row} - set(excluded_colors))
    records = []
    roles = []
    for color in palette:
        support = []
        for box in tile_boxes:
            mask = lattice_tile_mask(grid, box, color)
            bbox = _bbox_for_cells(list(mask)) if mask else None
            expected = (0, 0, box[2] - box[0], box[3] - box[1])
            support.append({'tile': box, 'mask': sorted(mask), 'bbox': bbox,
                            'spans': bbox == expected})
        spans = bool(tile_boxes) and all(item['spans'] for item in support)
        records.append({'color': color, 'tile_support': support, 'eligible': spans})
        if spans:
            roles.append(color)
    return roles, records


def parse_roles(grid):
    old_roles, old_record = legacy.parse(grid)
    record = {'legacy_parse': old_record}
    if not old_roles and old_record.get('failure') not in OLD_BODY_FAILURES:
        return [], dict(record, failure='shared_geometry_rejected')
    if 'source_d4' not in old_record['completed_checks']:
        legacy.invariant('new_body_requires_completed_legacy_geometry')
    bg = old_record['background']
    cr, cc = old_record['center']
    top, left, _, _ = old_record['frame_bounds']
    marker_values = {direction: grid[cr + 2 * direction[0]][cc + 2 * direction[1]]
                     for direction in legacy.DIRECTIONS}
    diagonal = {value for (dr, dc), value in marker_values.items() if dr and dc}
    cardinal = {value for (dr, dc), value in marker_values.items() if not (dr and dc)}
    if len(diagonal) != 1 or len(cardinal) != 1 or bg in diagonal | cardinal:
        legacy.invariant('legacy_d4_marker_role_contradiction')
    diagonal, cardinal = next(iter(diagonal)), next(iter(cardinal))
    targets = legacy.target_cells((cr, cc))
    if any(not (0 <= r < len(grid) and 0 <= c < len(grid[0])) for r, c in targets):
        return [], dict(record, failure='envelope_out_of_bounds')
    if len(targets) != len(set(targets)) or any(grid[r][c] != bg for r, c in targets):
        legacy.invariant('legacy_target_ownership_contradiction')
    boxes = [(cr + 3 * dr - 1, cc + 3 * dc - 1,
              cr + 3 * dr + 1, cc + 3 * dc + 1) for dr, dc in legacy.DIRECTIONS]
    bodies, support = shared_tile_spanning_roles(grid, boxes, {bg, diagonal, cardinal})
    roles = [(bg, top, left, cr, cc, body, diagonal, cardinal) for body in bodies]
    record.update(body_role_support=support, body_roles=bodies, roles=roles,
                  target_count=len(targets), source='unchanged input')
    return roles, record if roles else dict(record, failure='no_shared_tile_spanning_role')


def render_role(grid, role, program):
    """Use accepted tile transforms and the existing nine-patch ownership map."""
    if program not in PROGRAMS or not legacy.valid_role(role):
        return None, {'failure': 'invalid_role_or_program'}
    bg, top, left, cr, cc, body, diagonal, cardinal = role
    exterior, markers, selector = program
    assignments = []
    for dr, dc in legacy.DIRECTIONS:
        sr, sc = (-dr, -dc) if exterior == 'opposite_sector_identity' else (dr, dc)
        tile = [row[cc + 3 * sc - 1:cc + 3 * sc + 2]
                for row in grid[cr + 3 * sr - 1:cr + 3 * sr + 2]]
        transform = ('identity' if exterior == 'opposite_sector_identity' else
                     'rot180' if exterior == 'same_sector_half_turn' or dr and dc else
                     'flip_v' if dr else 'flip_h')
        copied = transform_grid_by_name(tile, transform)
        for ur in range(3):
            for uc in range(3):
                assignments.append((cr + 6 * dr + ur - 1,
                                    cc + 6 * dc + uc - 1, copied[ur][uc]))
    for dr, dc in legacy.DIRECTIONS:
        value = (grid[cr + 2 * dr][cc + 2 * dc] if markers == 'literal_marker_transfer'
                 else diagonal if dr and dc else cardinal)
        assignments.append((cr + dr, cc + dc, value))
    assignments.append((cr, cc, body))
    cells = {(r, c) for r, c, value in assignments}
    if (len(assignments) != 81 or cells != set(legacy.target_cells((cr, cc)))
            or any(grid[r][c] != bg or value == bg for r, c, value in assignments)):
        legacy.invariant('new_body_target_ownership')
    output = legacy.clone_grid(grid)
    for r, c, value in assignments:
        output[r][c] = value
    return output, {'role': role, 'program': program, 'assignments': assignments,
                    'write_count': 81, 'simultaneous': True}


def enumerate_outputs(grid):
    """Retain full outputs of every prospective program and every body role."""
    roles, parse_record = parse_roles(grid)
    records = []
    for role in roles:
        for program in PROGRAMS:
            output, record = render_role(grid, role, program)
            records.append(dict(record, output=output))
    successful = [record['output'] for record in records if record['output'] is not None]
    keys = {tuple(map(tuple, output)) for output in successful}
    agreed = bool(records) and len(successful) == len(records) and len(keys) == 1
    output = successful[0] if agreed else None
    return output, {'parse': parse_record, 'programs': PROGRAMS, 'results': records,
                    'full_output_count': len(successful), 'distinct_output_count': len(keys),
                    'failure': None if agreed else 'no_complete_full_grid_consensus'}


def enumerate_original_outputs(grid):
    """Original rejection semantics and all twelve program identities unchanged."""
    roles, record = legacy.parse(grid)
    results = []
    for program in legacy.PROGRAMS:
        if not roles:
            results.append({'program': program, 'output': None, 'parse_failure': record.get('failure')})
        else:
            output, action = legacy.execute(grid, roles[0], program)
            results.append(dict(action, output=output))
    return {'parse': record, 'programs': legacy.PROGRAMS, 'results': results}


def fit(teachers):
    """Fit every declared program without selecting among qualified roles."""
    if (len(teachers) < 2 or any(legacy.grid_schema_errors(pair['input'])
                               or legacy.grid_schema_errors(pair['output']) for pair in teachers)):
        return None, {'failure': 'invalid_or_insufficient_teachers'}
    records = []
    retained = []
    for program in PROGRAMS:
        teacher_records = []
        for pair in teachers:
            roles, parse_record = parse_roles(pair['input'])
            results = []
            for role in roles:
                output, record = render_role(pair['input'], role, program)
                results.append(dict(record, output=output, fits=output == pair['output']))
            teacher_records.append({'parse': parse_record, 'results': results,
                                    'fits_all_roles': bool(results) and all(r['fits'] for r in results)})
        fits = all(record['fits_all_roles'] for record in teacher_records)
        records.append({'program': program, 'teachers': teacher_records, 'retained': fits})
        if fits:
            retained.append(program)
    return ({'programs': retained} if retained else None), {'programs': records}


def predict(grid, state):
    """Evaluate the fitted inventory over all input-qualified body roles."""
    if not isinstance(state, dict) or not state.get('programs'):
        return None, {'failure': 'empty_or_no_fit_state', 'results': []}
    supplied = state['programs']
    if (not isinstance(supplied, (tuple, list))
            or any(not isinstance(program, (tuple, list)) for program in supplied)):
        return None, {'failure': 'invalid_fitted_state', 'results': []}
    programs = tuple(tuple(program) for program in supplied)
    if any(program not in PROGRAMS for program in programs) or len(set(programs)) != len(programs):
        return None, {'failure': 'invalid_fitted_state', 'results': []}
    roles, parse_record = parse_roles(grid)
    results = []
    for program in programs:
        for role in roles:
            output, record = render_role(grid, role, program)
            results.append(dict(record, output=output))
    outputs = [result['output'] for result in results if result['output'] is not None]
    distinct = {tuple(map(tuple, output)) for output in outputs}
    agreed = bool(results) and len(outputs) == len(results) and len(distinct) == 1
    return (outputs[0] if agreed else None), {
        'parse': parse_record, 'retained_programs': programs,
        'qualified_role_count': len(roles), 'evaluated_program_count': len(programs),
        'evaluated_program_role_count': len(results), 'results': results,
        'full_output_count': len(outputs), 'distinct_output_count': len(distinct),
        'failure': None if agreed else 'no_complete_full_grid_consensus'}
