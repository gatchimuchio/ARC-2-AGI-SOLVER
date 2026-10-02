"""Verify the full union of unit cardinal matches; return only the old output."""
from . import 既存十字着色 as old

OFFSETS = ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))


def raw_color_fit(teachers):
    transitions = []
    for pair in teachers:
        inp, out = pair['input'], pair['output']
        if not old.is_rectangular(inp) or not old.is_rectangular(out) or old.grid_shape(inp) != old.grid_shape(out):
            return None
        changed = {(a, b) for row_a, row_b in zip(inp, out) for a, b in zip(row_a, row_b) if a != b}
        if len(changed) != 1:
            return None
        transitions.append(next(iter(changed)))
    if len(set(transitions)) != 1:
        return None
    source, target = transitions[0]
    if source == target:
        return None
    if not all(old.plus_recolor(p['input'], source, target) == p['output'] for p in teachers):
        return None
    return source, target


def guarded_render(grid, source, target):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    if any(type(v) is not int or not 0 <= v <= 9 for v in (source, target)) or source == target:
        return None, {'failure': 'invalid_color_roles'}
    height, width = len(grid), len(grid[0])
    centers = {(r, c) for r in range(1, height - 1) for c in range(1, width - 1)
               if all(grid[r + dr][c + dc] == source for dr, dc in OFFSETS)}
    if not centers:
        return None, {'failure': 'no_complete_plus_match'}
    matched = {(r + dr, c + dc) for r, c in centers for dr, dc in OFFSETS}
    expected = [[target if (r, c) in matched else value for c, value in enumerate(row)]
                for r, row in enumerate(grid)]
    output = old.plus_recolor(grid, source, target)
    if output is None or output != expected:
        return None, {'failure': 'source_output_disagrees'}
    return output, {'source': source, 'target': target, 'centers': len(centers),
                    'union_pixels': len(matched), 'overlap_reuses': 5 * len(centers) - len(matched),
                    'source_outside_union': sum(v == source for row in grid for v in row) - len(matched)}


def fit_guarded(teachers):
    if not teachers or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return None
    fit = raw_color_fit(teachers)
    if fit is None:
        return None
    if not all(guarded_render(p['input'], *fit)[0] == p['output'] for p in teachers):
        return None
    return fit


class 十字教材:
    def __init__(self, 教師群):
        self.色遷移 = fit_guarded(教師群)

    def 候補(self, 格子, _policy):
        if self.色遷移 is None:
            return None, {'failure': '全教師を再現する十字色遷移なし'}
        return guarded_render(格子, *self.色遷移)

    def 記録(self):
        return {'全教師再現': self.色遷移 is not None, '色遷移': self.色遷移}
