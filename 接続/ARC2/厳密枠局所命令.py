"""Isolated finite composition: framed demonstrations of local grid actions.

No task data, learned output surface, task identifier, or filesystem access.
Accepted helpers perform crop, perimeter, containment, D4, binary colorization,
and straight-segment construction. The hierarchical view and action interpreter
are new glue, not an already accepted solver family.
"""
from itertools import combinations

from 接続.ARC2.既存配置展開 import crop_bbox
from 接続.ARC2.既存枠計数 import perimeter_cells
from 接続.ARC2.既存色群関係 import bbox_relation_for_bboxes
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.既存二値原型 import binary_template_from_grid, colorize_binary_template
from 接続.ARC2.既存疎点転写 import straight_octilinear_segment

TRANSFORMS = ('identity', 'rot90', 'rot180', 'rot270', 'flip_h', 'flip_v',
              'transpose', 'anti_transpose')
LOCAL_ACTIONS = tuple(('binary', transform, swap) for transform in TRANSFORMS
                      for swap in (False, True)) + tuple(
    ('segments', transform, geometry, endpoints)
    for transform in TRANSFORMS for geometry in ('axis', 'octilinear')
    for endpoints in ('all', 'marker_incident'))


class ResourceLimit(RuntimeError):
    """Incomplete enumeration is a resource failure, never a no-fit result."""


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30 and
            isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30 and
            all(isinstance(row, list) and len(row) == len(grid[0]) and
                all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))


def frames(grid):
    """All complete monochrome perimeters, including attached clutter."""
    h, w = len(grid), len(grid[0])
    result = []
    for top in range(h-2):
        for bottom in range(top+2, h):
            for left in range(w-2):
                color = grid[top][left]
                if any(grid[r][left] != color for r in range(top, bottom+1)):
                    continue
                for right in range(left+2, w):
                    if any(grid[top][c] != color or grid[bottom][c] != color
                           for c in range(left, right+1)):
                        break
                    if any(grid[r][right] != color for r in range(top, bottom+1)):
                        continue
                    box = top, left, bottom, right
                    if not all(grid[r][c] == color for r, c in perimeter_cells(box)):
                        raise AssertionError('perimeter_helper_disagreement')
                    interior = crop_bbox(grid, (top+1, left+1, bottom-1, right-1))
                    result.append({'bbox': box, 'color': color, 'interior': interior,
                                   'leaf': all(v != color for row in interior for v in row)})
    return result


def parse(grid):
    if not valid_grid(grid):
        return [], {'failure': 'invalid_grid'}
    raw = frames(grid)
    leaves = [frame for frame in raw if frame['leaf']]
    roles = []
    tested = 0
    for frame_color in sorted({frame['color'] for frame in leaves}):
        panels = [frame for frame in leaves if frame['color'] == frame_color]
        if len(panels) < 4 or len(panels) % 2:
            continue
        shapes = {(len(p['interior']), len(p['interior'][0])) for p in panels}
        if len(shapes) != 1:
            continue
        if any(not bbox_relation_for_bboxes(a['bbox'], b['bbox']).disjoint
               for a, b in combinations(panels, 2)):
            continue
        blank_panels = [(i, p['interior'][0][0]) for i, p in enumerate(panels)
                        if len({v for row in p['interior'] for v in row}) == 1]
        if len(blank_panels) != 1:
            continue
        blank_id, blank = blank_panels[0]
        if blank == frame_color:
            continue
        groups = []
        for outer in raw:
            if outer['color'] in {blank, frame_color}:
                continue
            members = tuple(i for i, p in enumerate(panels)
                            if bbox_relation_for_bboxes(outer['bbox'], p['bbox'])
                            .first_strictly_contains_second)
            if len(members) == 2:
                groups.append({'bbox': outer['bbox'], 'color': outer['color'],
                               'members': members})

        def visit(owned, selected):
            nonlocal tested
            tested += 1
            if tested > 10000:
                raise ResourceLimit('frame_group_cover_limit')
            if len(owned) == len(panels):
                target = [g for g in selected if blank_id in g['members']]
                if len(target) != 1:
                    raise AssertionError('exact_cover_target_ownership')
                role = {'frame_color': frame_color, 'blank': blank,
                        'blank_id': blank_id, 'panels': panels, 'groups': selected,
                        'target': target[0]}
                roles.append(role)
                return
            first = min(set(range(len(panels))) - owned)
            for group in groups:
                members = set(group['members'])
                if first not in members or members & owned:
                    continue
                if any(not bbox_relation_for_bboxes(group['bbox'], old['bbox']).disjoint
                       for old in selected):
                    continue
                visit(owned | members, selected + [group])

        visit(set(), [])
    return roles, {'raw_frames': len(raw), 'leaf_frames': len(leaves),
                   'roles': len(roles), 'cover_nodes': tested}


def act(grid, blank, ink, model):
    source = transform_grid_by_name(grid, model[1])
    if source is None:
        raise AssertionError('accepted_transform_rejected')
    palette = {v for row in source for v in row}
    if model[0] == 'binary':
        if palette != {blank, ink}:
            return None
        template = binary_template_from_grid(source, blank)
        return colorize_binary_template(template, ink, blank) if model[2] else \
            colorize_binary_template(template, blank, ink)
    marker_colors = palette - {blank, ink}
    if len(marker_colors) != 1 or ink not in palette or blank not in palette:
        return None
    marker = next(iter(marker_colors))
    points = [(r, c) for r, row in enumerate(source) for c, v in enumerate(row)
              if v != blank]
    proposed = set()
    for first, second in combinations(points, 2):
        if model[3] == 'marker_incident' and source[first[0]][first[1]] != marker \
                and source[second[0]][second[1]] != marker:
            continue
        if model[2] == 'axis' and first[0] != second[0] and first[1] != second[1]:
            continue
        segment = straight_octilinear_segment(first, second)
        if segment is not None:
            proposed.update((r, c) for r, c in segment if source[r][c] == blank)
    if not proposed:
        return None
    out = [row[:] for row in source]
    for r, c in proposed:
        out[r][c] = ink
    return out


def render(grid, *, parser=None):
    roles, parse_record = (parse if parser is None else parser)(grid)
    returns = []
    role_records = []
    failed_roles = []
    for role in roles:
        demos = [g for g in role['groups'] if g is not role['target']]
        panels, blank = role['panels'], role['blank']
        retained = []
        alternatives = []
        for model in LOCAL_ACTIONS:
            orders = []
            for demo in demos:
                a, b = demo['members']
                compatible = [(a, b) for a, b in ((a, b), (b, a))
                              if act(panels[a]['interior'], blank, demo['color'], model)
                              == panels[b]['interior']]
                orders.append(compatible)
            if orders and all(orders):
                retained.append(model)
                alternatives.append({'model': model, 'demo_directions': orders})
        target = role['target']
        source_id = next(i for i in target['members'] if i != role['blank_id'])
        outputs = [act(panels[source_id]['interior'], blank, target['color'], model)
                   for model in retained]
        role_records.append({'groups': role['groups'], 'blank': blank,
                             'frame_color': role['frame_color'],
                             'panels': [p['bbox'] for p in panels],
                             'alternatives': alternatives, 'outputs': outputs})
        # Structural alternatives are not selected using action success.
        if not outputs or any(output is None for output in outputs):
            failed_roles.append(len(role_records)-1)
        returns.extend(outputs)
    if failed_roles:
        return None, {'parse': parse_record, 'roles': role_records,
                      'failed_roles': failed_roles,
                      'failure': 'structural_role_or_retained_action_failed'}
    if not returns:
        return None, {'parse': parse_record, 'failure': 'no_structural_role'}
    if any(out != returns[0] for out in returns[1:]):
        return None, {'parse': parse_record, 'roles': role_records,
                      'failure': 'complete_grid_disagreement'}
    return returns[0], {'parse': parse_record, 'roles': role_records,
                        'agreed_outputs': len(returns), 'status': 'PASS'}


def fit(teachers):
    if not isinstance(teachers, list) or len(teachers) < 2:
        return False, {'failure': 'insufficient_teachers'}
    if any(not isinstance(p, dict) or not valid_grid(p.get('input')) or
           not valid_grid(p.get('output')) for p in teachers):
        return False, {'failure': 'invalid_teachers'}
    if len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return False, {'failure': 'duplicate_teachers'}
    rows = []
    for pair in teachers:
        output, record = render(pair['input'])
        rows.append({'exact': output == pair['output'], 'record': record})
    return all(row['exact'] for row in rows), {'teachers': rows}
