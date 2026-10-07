"""Strict085 plus a finite, input-witnessed two-color complement action.

The old parser, ownership, actions and action-bearing outcomes are unchanged.
The new prior is exactly period two on rows, columns, or diagonals after D4.
Period and phase come from this source-defined inventory and observed colors;
no teacher output is consulted while rendering and no output surface is stored.
"""
from . import 厳密枠局所命令 as old085

from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.既存二値原型 import binary_template_from_grid, colorize_binary_template

PERIODIC_AXES = ((1, 0), (0, 1), (1, 1))
PERIODIC_ACTIONS = tuple(
    ('periodic_complement', transform, dr, dc)
    for transform in old085.TRANSFORMS for dr, dc in PERIODIC_AXES)


def periodic_action(grid, blank, group_color, model):
    """Complement support, filling only from a fully witnessed binary phase."""
    if model not in PERIODIC_ACTIONS:
        return None, {'failure': 'outside_finite_action_inventory'}
    source = transform_grid_by_name(grid, model[1])
    if source is None:
        raise AssertionError('accepted_transform_rejected')
    palette = {v for row in source for v in row}
    colors = palette - {blank}
    if blank not in palette or len(colors) != 2 or group_color in palette:
        return None, {'failure': 'incomplete_distinct_color_roles'}
    dr, dc = model[2:]
    witnesses = [[], []]
    for r, row in enumerate(source):
        for c, value in enumerate(row):
            if value != blank:
                witnesses[(dr*r + dc*c) % 2].append((r, c, value))
    phase_colors = [{v for _, _, v in cells} for cells in witnesses]
    if any(len(values) != 1 for values in phase_colors):
        return None, {'failure': 'incomplete_or_conflicting_phase',
                      'phase_witnesses': witnesses}
    phase = tuple(next(iter(values)) for values in phase_colors)
    if set(phase) != colors:
        return None, {'failure': 'phase_not_primitive_two_color',
                      'phase_witnesses': witnesses}
    support = binary_template_from_grid(source, blank)
    complement = colorize_binary_template(support, 1, 0)
    output = [[phase[(dr*r + dc*c) % 2] if occupied else blank
               for c, occupied in enumerate(row)]
              for r, row in enumerate(complement)]
    return output, {'blank': blank, 'group_color': group_color,
                    'phase_colors': phase, 'phase_witnesses': witnesses,
                    'period': 2, 'axis': (dr, dc), 'transform': model[1]}


def render(grid):
    original = old085.render(grid)
    old_output, old_record = original
    # Preserve old success, ambiguity, and action-bearing failed-role aggregates.
    if old_output is not None or not old_record.get('roles') or any(
            role['alternatives'] for role in old_record['roles']):
        return original
    roles, parse_record = old085.parse(grid)
    if not roles:
        raise AssertionError('old_parse_not_repeatable')
    returns, records, failed_roles = [], [], []
    for role in roles:
        panels, blank = role['panels'], role['blank']
        demos = [g for g in role['groups'] if g is not role['target']]
        alternatives = []
        for model in PERIODIC_ACTIONS:
            directions, demo_witnesses = [], []
            for demo in demos:
                a, b = demo['members']
                compatible, witnesses = [], []
                for first, second in ((a, b), (b, a)):
                    output, witness = periodic_action(
                        panels[first]['interior'], blank, demo['color'], model)
                    if output == panels[second]['interior']:
                        compatible.append((first, second))
                        witnesses.append({'direction': (first, second),
                                          'witness': witness})
                directions.append(compatible)
                demo_witnesses.append(witnesses)
            if directions and all(directions):
                alternatives.append({'model': model,
                                     'demo_directions': directions,
                                     'demo_witnesses': demo_witnesses})
        target = role['target']
        source_id = next(i for i in target['members'] if i != role['blank_id'])
        outputs, target_witnesses = [], []
        for alternative in alternatives:
            output, witness = periodic_action(
                panels[source_id]['interior'], blank, target['color'],
                alternative['model'])
            outputs.append(output)
            target_witnesses.append(witness)
        records.append({'groups': role['groups'], 'blank': blank,
                        'frame_color': role['frame_color'],
                        'panels': [p['bbox'] for p in panels],
                        'alternatives': alternatives, 'outputs': outputs,
                        'target_witnesses': target_witnesses})
        if not outputs or any(output is None for output in outputs):
            failed_roles.append(len(records)-1)
        returns.extend(outputs)
    record = {'parse': parse_record, 'roles': records,
              'extension': 'witnessed_periodic_complement',
              'old_record': old_record}
    if failed_roles:
        return None, dict(record, failed_roles=failed_roles,
                          failure='structural_role_or_retained_action_failed')
    if any(output != returns[0] for output in returns[1:]):
        return None, dict(record, failure='complete_grid_disagreement')
    return returns[0], dict(record, agreed_outputs=len(returns), status='PASS')


def fit(teachers):
    if not isinstance(teachers, list) or len(teachers) < 2:
        return False, {'failure': 'insufficient_teachers'}
    if any(not isinstance(p, dict) or not old085.valid_grid(p.get('input')) or
           not old085.valid_grid(p.get('output')) for p in teachers):
        return False, {'failure': 'invalid_teachers'}
    if len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return False, {'failure': 'duplicate_teachers'}
    rows = []
    for pair in teachers:
        output, record = render(pair['input'])
        rows.append({'exact': output == pair['output'], 'record': record})
    return all(row['exact'] for row in rows), {'teachers': rows}
