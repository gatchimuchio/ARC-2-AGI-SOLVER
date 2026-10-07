"""Prospective sparse marker assembly using accepted object and bbox helpers.

Whole bicolored objects translate without rotation. Their common-color pins
coincide in pairs, every payload cell survives, and a rectangular payload anchors
the canvas. All marker roles, qualifying anchors, and completed placements are
retained. No task identity, learned output grid, or query data is consulted.
"""
from collections import Counter

from 接続.ARC2.既存領域転写 import mixed_region_dicts_for_grid
from 接続.ARC2.既存色群関係 import scaffold_legend_bbox
from 接続.ARC2.既存物体特徴 import dominant_background_for_grid

CONNECTIVITIES = (False, True)
DEFAULT_WORK_LIMIT = 250000


class AssemblyIncomplete(RuntimeError):
    """The complete finite search did not finish within the explicit work cap."""


def grid_key(grid):
    return tuple(map(tuple, grid))


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


def observe_roles(grid, diagonal):
    if not valid_grid(grid):
        return [], {'failure': 'invalid_grid'}
    counts = Counter(v for row in grid for v in row)
    if sum(n == max(counts.values()) for n in counts.values()) != 1:
        return [], {'failure': 'background_tie'}
    background = dominant_background_for_grid(grid)
    regions = mixed_region_dicts_for_grid(grid, background, diagonal)
    if len(regions) < 2 or any(len(p['colors']) != 2 for p in regions):
        return [], {'failure': 'whole_objects_not_bicolored',
                    'region_count': len(regions),
                    'region_palettes': [p['colors'] for p in regions]}
    common = set.intersection(*(set(p['colors']) for p in regions))
    roles = []
    for marker in sorted(common):
        pieces = []
        for region in regions:
            body = {(r, c): grid[r][c] for r, c in region['cells']
                    if grid[r][c] != marker}
            pins = frozenset((r, c) for r, c in region['cells']
                             if grid[r][c] == marker)
            top, left, bottom, right = scaffold_legend_bbox(set(body))
            pieces.append({'body': body, 'pins': pins,
                           'anchor': len(body) == (bottom-top+1)*(right-left+1)})
        for anchor, piece in enumerate(pieces):
            if piece['anchor']:
                roles.append({'background': background, 'marker': marker,
                              'pieces': pieces, 'anchor': anchor})
    return roles, {'background': background, 'common_marker_candidates': sorted(common),
                   'region_count': len(regions), 'role_count': len(roles)}


def enumerate_assemblies(grid, diagonal, *, work_limit=DEFAULT_WORK_LIMIT):
    if type(diagonal) is not bool:
        raise ValueError('diagonal must be a Boolean')
    if type(work_limit) is not int or work_limit < 1:
        raise ValueError('work_limit must be a positive integer')
    roles, observation = observe_roles(grid, diagonal)
    all_models, returns = [], []
    work = 0
    for role_index, role in enumerate(roles):
        pieces, anchor = role['pieces'], role['anchor']
        anchor_piece = pieces[anchor]
        visited, models = set(), []
        nodes = 0

        def visit(positions, body, pins):
            nonlocal work, nodes
            state = tuple(sorted(positions.items()))
            if state in visited:
                return
            work += 1
            if work > work_limit:
                raise AssemblyIncomplete(f'assembly work limit exceeded: {work_limit}')
            visited.add(state)
            nodes += 1
            if len(positions) == len(pieces):
                if any(count != 2 for count in pins.values()):
                    return
                output = [[role['background']] * len(grid[0]) for _ in grid]
                for (row, col), color in body.items():
                    output[row][col] = color
                for row, col in pins:
                    output[row][col] = role['marker']
                models.append({'output': output, 'positions': state,
                               'role_index': role_index, 'marker': role['marker'],
                               'anchor': anchor})
                return
            singles = {point for point, count in pins.items() if count == 1}
            if not singles:
                return
            # Every completion must pair this pin with one unplaced piece.
            # A saturated prefix cannot acquire another connected piece.
            row, col = min(singles)
            for index, piece in enumerate(pieces):
                if index in positions:
                    continue
                shifts = {(row-source_row, col-source_col)
                          for source_row, source_col in piece['pins']}
                for dr, dc in sorted(shifts):
                    work += 1
                    if work > work_limit:
                        raise AssemblyIncomplete(f'assembly work limit exceeded: {work_limit}')
                    moved_body = {(r+dr, c+dc): color
                                  for (r, c), color in piece['body'].items()}
                    moved_pins = {(r+dr, c+dc) for r, c in piece['pins']}
                    moved_cells = set(moved_body) | moved_pins
                    if any(not (0 <= r < len(grid) and 0 <= c < len(grid[0]))
                           for r, c in moved_cells):
                        continue
                    if (set(moved_body) & (set(body) | set(pins))
                            or moved_pins & set(body)):
                        continue
                    if any(pins.get(point, 0) == 2 for point in moved_pins):
                        continue
                    visit({**positions, index: (dr, dc)}, {**body, **moved_body},
                          pins + Counter(moved_pins))

        visit({anchor: (0, 0)}, dict(anchor_piece['body']), Counter(anchor_piece['pins']))
        all_models.extend(models)
        returns.append({'role_index': role_index, 'marker': role['marker'],
                        'anchor': anchor, 'nodes': nodes, 'model_count': len(models)})
    outputs = {grid_key(model['output']): model['output'] for model in all_models}
    return all_models, {'diagonal': diagonal, 'observation': observation,
                        'role_returns': returns, 'complete': True, 'work': work,
                        'model_count': len(all_models), 'output_count': len(outputs)}


def fit_teachers(pairs, *, work_limit=DEFAULT_WORK_LIMIT):
    records, policies = [], []
    if not pairs:
        return [], {'failure': 'empty_teachers', 'trials': records}
    for diagonal in CONNECTIVITIES:
        checks = []
        for pair in pairs:
            models, record = enumerate_assemblies(pair['input'], diagonal, work_limit=work_limit)
            outputs = {grid_key(model['output']) for model in models}
            checks.append({'exact': outputs == {grid_key(pair['output'])}, **record})
        records.append({'diagonal': diagonal, 'teachers': checks})
        if all(check['exact'] for check in checks):
            policies.append(diagonal)
    return policies, {'trials': records, 'policies': policies}


def render(grid, policies, *, work_limit=DEFAULT_WORK_LIMIT):
    if not policies or any(type(policy) is not bool for policy in policies):
        return None, {'failure': 'no_valid_fitting_policies', 'returns': []}
    returns, all_models = [], []
    # Every fitted policy returns before semantic missing-output or grid conflicts
    # are checked. Unexpected and resource exceptions deliberately propagate.
    for diagonal in policies:
        models, record = enumerate_assemblies(grid, diagonal, work_limit=work_limit)
        returns.append(record)
        all_models.extend(models)
    output_keys = {grid_key(model['output']) for model in all_models}
    record = {'returns': returns, 'models': all_models,
              'output_count': len(output_keys)}
    if any(result['model_count'] == 0 for result in returns):
        return None, {'failure': 'fitted_policy_has_no_complete_assembly', **record}
    if len(output_keys) != 1:
        return None, {'failure': 'complete_assemblies_disagree', **record}
    return [list(row) for row in next(iter(output_keys))], record
