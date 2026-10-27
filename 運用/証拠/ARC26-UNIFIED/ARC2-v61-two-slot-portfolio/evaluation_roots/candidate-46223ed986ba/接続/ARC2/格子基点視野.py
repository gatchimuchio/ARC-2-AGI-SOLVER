"""Chamber view extension around the unchanged lattice-anchor transfer.

Fit remains strict. Only placement-boundary failures admit copy-then-crop.
"""
from . import 格子基点転写核 as strict
from 接続.ARC2.既存重畳組立 import crop_grid

fit = strict.fit
valid_grid = strict.valid_grid


def boundary_role(record):
    failures = record.get('failures', [])
    return (record.get('failure') == 'incomplete_role_render' and bool(failures)
            and all(set(item) == {'tile', 'failures'}
                    and item['failures'] == ['placement_outside_tile']
                    for item in failures))


def boundary_render(record):
    roles = record.get('roles', [])
    return (record.get('failure') == 'retained_role_failed' and bool(roles)
            and any(boundary_role(role) for role in roles)
            and all('failure' not in role or boundary_role(role) for role in roles))


def render_role(grid, context, role, policy):
    original, original_record = strict.render_role(grid, context, role, policy)
    if original is not None or not boundary_role(original_record):
        return original, original_record
    bg = context['background']
    sr, sc = context['tiles'][role['source_index']]['index']
    output = [row[:] for row in grid]
    placements, failures = [], []
    for ti, tile in enumerate(context['tiles']):
        tr, tc = tile['index']
        horizontal, vertical = policy[0] and tc != sc, policy[1] and tr != sr
        name = 'rot180' if horizontal and vertical else 'flip_h' if horizontal else 'flip_v' if vertical else 'identity'
        pattern = strict.transform_grid_by_name([list(row) for row in role['primitive']], name)
        top, left, side = role['anchors'][ti]
        primitive_side = role['primitive_anchor_side']
        if side % primitive_side:
            failures.append(dict(tile=ti, failure='noninteger_anchor_scale'))
            continue
        scale = side // primitive_side
        ar, ac = strict.anchor_offset(pattern, role['anchor_color'], scale)
        r0, c0, r1, c1 = tile['bbox']
        cells = strict.scaled_pattern_cells(pattern, scale, r0+top-ar, c0+left-ac)
        # The envelope contains the complete copy and the entire chamber.
        er0, ec0 = min([r0] + [r for r, c, v in cells]), min([c0] + [c for r, c, v in cells])
        er1, ec1 = max([r1] + [r for r, c, v in cells]), max([c1] + [c for r, c, v in cells])
        canvas = [[None] * (ec1-ec0+1) for _ in range(er1-er0+1)]
        for r, c, value in cells:
            canvas[r-er0][c-ec0] = value
        view = crop_grid(canvas, (r0-er0, c0-ec0, r1-er0, c1-ec0))
        visible = [(r+r0, c+c0, value) for r, row in enumerate(view)
                   for c, value in enumerate(row) if value is not None]
        outside = [(r, c, v) for r, c, v in cells if not (r0 <= r <= r1 and c0 <= c <= c1)]
        local = []
        if (len(view) != r1-r0+1 or any(len(row) != c1-c0+1 for row in view)
                or len(cells) != len(set(cells)) or len(cells) != len(visible)+len(outside)
                or set(cells) != set(visible) | set(outside)):
            local.append('complete_copy_crop_partition_failed')
        expected_anchor = {(r0+r, c0+c) for r in range(top, top+side) for c in range(left, left+side)}
        visible_anchor = {(r, c) for r, c, v in visible if v == role['anchor_color']}
        if visible_anchor != expected_anchor:
            local.append('visible_anchor_ownership_failed')
        if any(grid[r][c] not in {bg, value} for r, c, value in visible):
            local.append('foreground_collision')
        placements.append(dict(tile=ti, transform=name, scale=scale, viewport=list(tile['bbox']),
                               support_envelope=[er0, ec0, er1, ec1], complete_cells=cells,
                               visible_cells=visible, outside_cells=outside))
        if local:
            failures.append(dict(tile=ti, failures=local))
        else:
            for r, c, value in visible:
                output[r][c] = value
    separator = context['lattice']
    if any(output[r][c] != grid[r][c] for r, row in enumerate(grid) for c, value in enumerate(row)
           if value != bg or r in separator['separator_rows'] or c in separator['separator_cols']):
        failures.append(dict(failure='original_foreground_or_separator_changed'))
    record = dict(strict_role_record=original_record, viewport_placements=placements, failures=failures)
    if failures:
        return None, dict(record, failure='complete_viewport_render_failed')
    return output, record


def render(grid, policy):
    original, original_record = strict.render(grid, policy)
    if original is not None or not boundary_render(original_record):
        return original, original_record
    context, roles, rejection = strict.parse_roles(grid)
    if context is None:
        return None, rejection
    results = [render_role(grid, context, role, policy) for role in roles]
    record = dict(policy=list(policy), roles=[r for _, r in results], role_count=len(results),
                  view_extension='complete_copy_cropped_to_lattice_chamber', strict_record=original_record)
    if any(out is None for out, _ in results):
        return None, dict(record, failure='retained_role_failed')
    if len({tuple(map(tuple, out)) for out, _ in results}) != 1:
        return None, dict(record, failure='role_full_grid_disagreement')
    return results[0][0], record


def consensus(grid, model):
    if not model or not model.get('policies'):
        return None, {'failure': 'no_retained_policies'}
    results = [render(grid, policy) for policy in model['policies']]
    record = {'policy_records': [r for _, r in results], 'evaluated_policy_count': len(results)}
    if any(out is None for out, _ in results):
        return None, dict(record, failure='retained_policy_failed')
    if len({tuple(map(tuple, out)) for out, _ in results}) != 1:
        return None, dict(record, failure='policy_full_grid_disagreement')
    return results[0][0], record
