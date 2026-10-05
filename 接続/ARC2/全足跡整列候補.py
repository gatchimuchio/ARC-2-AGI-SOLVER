"""Fixed input-only whole-chart grammar and small certified action adapter.

History/teacher-informed prior. No target, task identifier or model search input.
"""
from collections import Counter
from 接続.ARC2.既存凡例穴対応 import clone_grid, grid_shape
from 接続.ARC2.既存順位着色 import same_color_components_4
from . import 全足跡旧部品 as legacy


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(line, list) and len(line) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in line)
                    for line in grid))


def enumerate_roles(grid, background):
    h, w = grid_shape(grid)
    colors = sorted({v for line in grid for v in line if v != background})
    foreground = {(r, c) for r in range(h) for c in range(w) if grid[r][c] != background}
    if not foreground:
        return [], [], None
    extent = [min(c for r, c in foreground), max(c for r, c in foreground)]
    cells_by_color = {color: {(r, c) for r, c in foreground if grid[r][c] == color}
                      for color in colors}
    components = {color: same_color_components_4(grid, color) for color in colors}
    raw, roles = [], []
    for row in range(1, h - 1):
        for axis in colors:
            failures = []
            axis_cells = cells_by_color[axis]
            if any(r != row for r, c in axis_cells):
                failures.append('axis_color_off_row')
            if sum(r == row for r, c in axis_cells) < 3:
                failures.append('fewer_than_three_axis_cells')
            if any(grid[row][c] == background for c in range(extent[0], extent[1] + 1)):
                failures.append('internal_axis_background_hole')
            bars, owned, used_columns = [], set(axis_cells), set()
            for color in colors:
                if color == axis:
                    continue
                for component in components[color]:
                    cells = set(component)
                    top, bottom = min(r for r, c in cells), max(r for r, c in cells)
                    left, right = min(c for r, c in cells), max(c for r, c in cells)
                    errors = []
                    rectangle = {(r, c) for r in range(top, bottom + 1)
                                 for c in range(left, right + 1)}
                    if cells != rectangle:
                        errors.append('not_complete_rectangle')
                    if not top <= row <= bottom:
                        errors.append('component_does_not_cross_axis')
                    columns = set(range(left, right + 1))
                    if used_columns & columns:
                        errors.append('slot_columns_overlap')
                    used_columns.update(columns)
                    if owned & cells:
                        errors.append('overlapping_ownership')
                    owned.update(cells)
                    bars.append({'left': left, 'right': right, 'color': color,
                                 'top': top, 'bottom': bottom, 'cell_count': len(cells),
                                 'offsets': list(range(top - row, bottom - row + 1)),
                                 'failures': errors})
            bars.sort(key=lambda bar: (bar['left'], bar['right'], bar['color']))
            if len(bars) < 3:
                failures.append('fewer_than_three_bars')
            if owned != foreground:
                failures.append('inexact_foreground_ownership')
            if any(bar['failures'] for bar in bars):
                failures.append('invalid_whole_bar_component')
            record = {'axis_row': row, 'axis_color': axis, 'background': background,
                      'extent': extent, 'axis_cells': sorted(axis_cells), 'bars': bars,
                      'foreground_count': len(foreground), 'owned_count': len(owned),
                      'failures': failures, 'retained': not failures}
            # Rejected-role certificates need counts/boxes, not repeated pixel sets.
            raw.append({k: v for k, v in record.items() if k != 'axis_cells'})
            if not failures:
                roles.append(record)
    return roles, raw, extent


def apply_role(grid, role):
    row, axis, bg = role['axis_row'], role['axis_color'], role['background']
    h, w = grid_shape(grid)
    tokens = legacy.contiguous_axis_tokens(grid, row, bg, axis)
    footprints = [legacy.token_footprint_offsets(grid, row, left, right, color)
                  for left, right, color in tokens]
    expected_tokens = [(b['left'], b['right'], b['color']) for b in role['bars']]
    expected_footprints = [tuple(b['offsets']) for b in role['bars']]
    sorted_footprints = sorted(footprints, key=lambda p: (len(p), min(p), max(p)))
    result = {'axis_row': row, 'axis_color': axis, 'background': bg,
              'tokens': tokens, 'original_footprints': footprints,
              'sorted_footprints': sorted_footprints,
              'status': 'failure', 'failure': None, 'output': None}
    if tokens != expected_tokens or footprints != expected_footprints:
        result['failure'] = 'certified_role_helper_disagreement'
        return result
    if footprints == sorted_footprints:
        result.update(status='no_op', failure='already_sorted', output=clone_grid(grid))
        return result
    old_cells = {(row + dr, c) for (left, right, color), fp in zip(tokens, footprints)
                 for dr in fp for c in range(left, right + 1)}
    proposals = {}
    for (left, right, color), fp in zip(tokens, sorted_footprints):
        for dr in fp:
            for c in range(left, right + 1):
                q = row + dr, c
                if not (0 <= q[0] < h and 0 <= q[1] < w):
                    result['failure'] = 'out_of_bounds'
                    return result
                if q in proposals:
                    result['failure'] = 'overlapping_slot_proposals'
                    return result
                if q not in old_cells and grid[q[0]][q[1]] != bg:
                    result['failure'] = 'stationary_foreground_collision'
                    return result
                proposals[q] = color
    out = clone_grid(grid)
    for r, c in old_cells:
        out[r][c] = bg
    for (r, c), color in proposals.items():
        out[r][c] = color
    affected = old_cells | set(proposals)
    if (out[row] != grid[row]
            or {(r, c) for r in range(h) for c in range(w) if out[r][c] == axis}
            != set(map(tuple, role['axis_cells']))
            or any(out[r][c] != grid[r][c] for r in range(h) for c in range(w)
                   if (r, c) not in affected)):
        result['failure'] = 'axis_or_outside_support_changed'
        return result
    result.update(status='success', output=out)
    return result


def aggregate_actions(actions):
    if not actions:
        return None, 'no_structural_roles'
    if any(action['status'] != 'success' for action in actions):
        return None, 'retained_role_failure_or_noop'
    if any(action['output'] != actions[0]['output'] for action in actions):
        return None, 'complete_output_disagreement'
    return clone_grid(actions[0]['output']), None


def render(grid):
    detail = {'schema': 'candidate030.chart.v1', 'status': 'HOLD', 'failure': None,
              'raw_roles': [], 'retained_roles': [], 'actions': []}
    if not valid_grid(grid):
        detail['failure'] = 'invalid_arc_grid'
        return None, detail
    counts = Counter(v for line in grid for v in line)
    backgrounds = sorted(c for c, n in counts.items() if n == max(counts.values()))
    detail.update(background_counts=dict(counts), background_candidates=backgrounds)
    if len(backgrounds) != 1:
        detail['failure'] = 'background_tie'
        return None, detail
    bg = backgrounds[0]
    roles, raw, extent = enumerate_roles(grid, bg)
    detail.update(background=bg, extent=extent, raw_roles=raw, retained_roles=roles)
    actions = []
    for role in roles:
        actions.append(apply_role(grid, role))
    out, failure = aggregate_actions(actions)
    detail.update(actions=actions, failure=failure, status='EMIT' if failure is None else 'HOLD')
    return out, detail
