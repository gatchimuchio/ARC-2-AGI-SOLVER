"""Input-only repeated-annulus grammar and twelve literal rendering identities.

Prepared source only. Runtime release is separate from this source packet.
"""

DIRECTIONS = ((-1, -1), (-1, 0), (-1, 1), (0, -1),
              (0, 1), (1, -1), (1, 0), (1, 1))
PROGRAMS = (
    ('same_sector_half_turn', 'literal_marker_transfer', 'common_extreme_corners'),
    ('same_sector_half_turn', 'literal_marker_transfer', 'unique_foreground_mode'),
    ('same_sector_half_turn', 'marker_role_placement', 'common_extreme_corners'),
    ('same_sector_half_turn', 'marker_role_placement', 'unique_foreground_mode'),
    ('opposite_sector_identity', 'literal_marker_transfer', 'common_extreme_corners'),
    ('opposite_sector_identity', 'literal_marker_transfer', 'unique_foreground_mode'),
    ('opposite_sector_identity', 'marker_role_placement', 'common_extreme_corners'),
    ('opposite_sector_identity', 'marker_role_placement', 'unique_foreground_mode'),
    ('same_sector_radial_axes', 'literal_marker_transfer', 'common_extreme_corners'),
    ('same_sector_radial_axes', 'literal_marker_transfer', 'unique_foreground_mode'),
    ('same_sector_radial_axes', 'marker_role_placement', 'common_extreme_corners'),
    ('same_sector_radial_axes', 'marker_role_placement', 'unique_foreground_mode'),
)


def invariant(detail):
    error = RuntimeError('contract_invariant_failure: ' + detail)
    error.contract_invariant_detail = detail
    raise error


def grid_schema_errors(grid):
    """Inspect every available literal row/cell, without coercion or cell hashing."""
    errors = []
    if type(grid) not in (list, tuple):
        return [{'reason': 'invalid_grid_container'}]
    if not grid:
        errors.append({'reason': 'empty_grid'})
    width = None
    if grid and type(grid[0]) in (list, tuple):
        width = len(grid[0])
    for r, row in enumerate(grid):
        if type(row) not in (list, tuple):
            errors.append({'row': r, 'reason': 'invalid_row_container'})
            continue
        if not row:
            errors.append({'row': r, 'reason': 'empty_row'})
        if width is not None and len(row) != width:
            errors.append({'row': r, 'reason': 'ragged_row'})
        for c, value in enumerate(row):
            if type(value) is not int:
                errors.append({'row': r, 'column': c, 'reason': 'invalid_cell_type'})
            elif not 0 <= value <= 9:
                errors.append({'row': r, 'column': c, 'reason': 'cell_out_of_range'})
    return errors


def valid_grid(grid):
    return not grid_schema_errors(grid)


def snapshot_grid(grid):
    errors = grid_schema_errors(grid)
    if errors:
        return None, errors
    return tuple(tuple(value for value in row) for row in grid), []


def clone_grid(grid):
    return [[value for value in row] for row in grid]


def valid_model(model):
    return (type(model) is tuple and len(model) == 3
            and all(type(label) is str for label in model) and model in PROGRAMS)


def valid_role(role):
    return (type(role) is tuple and len(role) == 8
            and all(type(value) is int for value in role)
            and all(0 <= role[index] <= 9 for index in (0, 5, 6, 7))
            and role[1] >= 0 and role[2] >= 0
            and role[3] == role[1] + 4 and role[4] == role[2] + 4)


def target_cells(center):
    cr, cc = center
    targets = []
    for dr, dc in DIRECTIONS:
        for ur in (-1, 0, 1):
            for uc in (-1, 0, 1):
                targets.append((cr + 6 * dr + ur, cc + 6 * dc + uc))
    for dr, dc in DIRECTIONS:
        targets.append((cr + dr, cc + dc))
    targets.append((cr, cc))
    return targets


def parse(grid):
    snapshot, errors = snapshot_grid(grid)
    record = {'completed_checks': [], 'role_count': 0}
    if errors:
        return (), dict(record, failure='invalid_grid', schema_errors=errors)
    grid = snapshot
    record['completed_checks'].append('literal_grid')
    h, w = len(grid), len(grid[0])
    record['dimensions'] = (h, w)
    bg = grid[0][0]
    for r in range(h):
        for c in range(w):
            if (r == 0 or c == 0 or r == h - 1 or c == w - 1) and grid[r][c] != bg:
                return (), dict(record, failure='nonuniform_perimeter', failed_coordinate=(r, c))
    record['background'] = bg
    record['completed_checks'].append('uniform_perimeter')
    foreground = []
    for r in range(h):
        for c in range(w):
            if grid[r][c] != bg:
                foreground.append((r, c))
    if not foreground:
        return (), dict(record, failure='no_foreground')
    record['foreground_count'] = len(foreground)
    record['completed_checks'].append('foreground_present')
    top = min(r for r, c in foreground)
    left = min(c for r, c in foreground)
    bottom = max(r for r, c in foreground)
    right = max(c for r, c in foreground)
    record['frame_bounds'] = (top, left, bottom, right)
    if bottom - top != 8 or right - left != 8:
        return (), dict(record, failure='frame_extent_not_9x9')
    record['completed_checks'].append('frame_extent_9x9')
    cr, cc = top + 4, left + 4
    record['center'] = (cr, cc)
    for r in range(h):
        for c in range(w):
            inside = top <= r <= bottom and left <= c <= right
            hole = abs(r - cr) <= 1 and abs(c - cc) <= 1
            expected_foreground = inside and not hole
            if (grid[r][c] != bg) != expected_foreground:
                return (), dict(record, failure='invalid_annulus_geometry', failed_coordinate=(r, c))
    record['completed_checks'].append('annulus_geometry')
    symmetry = {'row_sign': True, 'column_sign': True, 'transpose': True}
    discrepancies = []
    for r in range(top, bottom + 1):
        for c in range(left, right + 1):
            for name, rr, col in (('row_sign', 2 * cr - r, c),
                                  ('column_sign', r, 2 * cc - c),
                                  ('transpose', cr + c - cc, cc + r - cr)):
                if grid[r][c] != grid[rr][col]:
                    symmetry[name] = False
                    discrepancies.append({'coordinate': (r, c), 'action': name,
                                          'image': (rr, col)})
    record['symmetry_checks'] = symmetry
    if discrepancies:
        return (), dict(record, failure='source_not_d4', symmetry_discrepancies=discrepancies)
    record['completed_checks'].append('source_d4')
    corners = [(cr + dr, cc + dc) for dr in (-4, 4) for dc in (-4, 4)]
    corner_values = tuple(grid[r][c] for r, c in corners)
    if any(value != corner_values[0] for value in corner_values):
        invariant('corner_body_not_common')
    corner = corner_values[0]
    record['corner_color'] = corner
    record['corner_samples'] = [{'coordinate': cell, 'value': grid[cell[0]][cell[1]]}
                                for cell in corners]
    record['completed_checks'].append('common_corner_body')
    counts = [0] * 10
    for r, c in foreground:
        counts[grid[r][c]] += 1
    record['foreground_color_counts'] = [{'color': color, 'count': counts[color]}
                                         for color in range(10) if counts[color]]
    maximum = max(counts)
    modes = tuple(color for color in range(10) if counts[color] == maximum)
    if len(modes) != 1:
        return (), dict(record, failure='foreground_mode_not_unique', mode_colors=modes)
    mode = modes[0]
    record['unique_mode_color'] = mode
    record['completed_checks'].append('unique_foreground_mode')
    if mode != corner:
        return (), dict(record, failure='body_selectors_disagree')
    record['completed_checks'].append('body_selectors_agree')
    diagonal_samples = []
    cardinal_samples = []
    for dr, dc in DIRECTIONS:
        cell = (cr + 2 * dr, cc + 2 * dc)
        sample = {'direction': (dr, dc), 'coordinate': cell, 'value': grid[cell[0]][cell[1]]}
        (diagonal_samples if dr and dc else cardinal_samples).append(sample)
    diagonal = diagonal_samples[0]['value']
    if any(sample['value'] != diagonal for sample in diagonal_samples):
        invariant('diagonal_markers_not_common')
    record['diagonal_marker'] = diagonal
    record['diagonal_samples'] = diagonal_samples
    record['completed_checks'].append('common_diagonal_markers')
    cardinal = cardinal_samples[0]['value']
    if any(sample['value'] != cardinal for sample in cardinal_samples):
        invariant('cardinal_markers_not_common')
    record['cardinal_marker'] = cardinal
    record['cardinal_samples'] = cardinal_samples
    record['completed_checks'].append('common_cardinal_markers')
    if diagonal == bg or cardinal == bg:
        invariant('marker_background_contradicts_geometry')
    if diagonal == corner or cardinal == corner:
        return (), dict(record, failure='marker_role_alias')
    record['completed_checks'].append('marker_roles')
    envelope = (cr - 7, cc - 7, cr + 7, cc + 7)
    record['envelope_bounds'] = envelope
    if envelope[0] < 0 or envelope[1] < 0 or envelope[2] >= h or envelope[3] >= w:
        return (), dict(record, failure='envelope_out_of_bounds')
    record['completed_checks'].append('envelope_in_bounds')
    targets = target_cells((cr, cc))
    owned = set()
    source_cells = set(foreground)
    for r, c in sorted(targets):
        if ((r, c) in owned or not (0 <= r < h and 0 <= c < w)
                or (r, c) in source_cells or grid[r][c] != bg):
            invariant('invalid_target_ownership')
        owned.add((r, c))
    if len(owned) != 81 or len(source_cells) != 72:
        invariant('invalid_target_ownership')
    record['target_count'] = len(owned)
    record['completed_checks'].append('target_ownership')
    role = (bg, top, left, cr, cc, corner, diagonal, cardinal)
    record['role'] = role
    record['role_count'] = 1
    return (role,), record


def execute(grid, role, model):
    snapshot, errors = snapshot_grid(grid)
    if errors:
        return None, {'failure': 'invalid_grid', 'schema_errors': errors}
    grid = snapshot
    if not valid_model(model):
        return None, {'failure': 'invalid_model'}
    if not valid_role(role):
        return None, {'failure': 'invalid_role'}
    roles, record = parse(grid)
    if len(roles) > 1:
        invariant('multiple_structural_roles')
    if not roles or role != roles[0]:
        return None, {'failure': 'invalid_role', 'parse_record': record}
    bg, top, left, cr, cc, body, diagonal, cardinal = role
    exterior, center_ring, center_body = model
    assignments = []
    for dr, dc in DIRECTIONS:
        for ur in (-1, 0, 1):
            for uc in (-1, 0, 1):
                target = (cr + 6 * dr + ur, cc + 6 * dc + uc)
                if exterior == 'same_sector_half_turn':
                    source = (cr + 3 * dr - ur, cc + 3 * dc - uc)
                elif exterior == 'opposite_sector_identity':
                    source = (cr - 3 * dr + ur, cc - 3 * dc + uc)
                else:
                    vr = -ur if dr else ur
                    vc = -uc if dc else uc
                    source = (cr + 3 * dr + vr, cc + 3 * dc + vc)
                assignments.append({'target': target, 'value': grid[source[0]][source[1]],
                                    'owner': 'exterior', 'direction': (dr, dc),
                                    'local_offset': (ur, uc), 'source': source})
    for dr, dc in DIRECTIONS:
        source = (cr + 2 * dr, cc + 2 * dc)
        value = (grid[source[0]][source[1]] if center_ring == 'literal_marker_transfer'
                 else diagonal if dr and dc else cardinal)
        assignments.append({'target': (cr + dr, cc + dc), 'value': value,
                            'owner': 'center_ring', 'direction': (dr, dc),
                            'source': source if center_ring == 'literal_marker_transfer' else None,
                            'role_slot': 'diagonal_marker' if dr and dc else 'cardinal_marker'})
    value = (record['corner_color'] if center_body == 'common_extreme_corners'
             else record['unique_mode_color'])
    assignments.append({'target': (cr, cc), 'value': value, 'owner': 'center_body',
                        'selector': center_body})
    owned = set()
    h, w = len(grid), len(grid[0])
    for assignment in assignments:
        r, c = assignment['target']
        if ((r, c) in owned or not (0 <= r < h and 0 <= c < w)
                or grid[r][c] != bg or assignment['value'] == bg):
            invariant('invalid_target_ownership')
        owned.add((r, c))
    if len(assignments) != 81 or owned != set(target_cells((cr, cc))):
        invariant('invalid_target_ownership')
    output = clone_grid(grid)
    for assignment in assignments:
        r, c = assignment['target']
        output[r][c] = assignment['value']
    return output, {'role': role, 'model': model, 'assignments': assignments,
                    'write_count': 81, 'preserved_foreground_count': 72,
                    'simultaneous': True}
