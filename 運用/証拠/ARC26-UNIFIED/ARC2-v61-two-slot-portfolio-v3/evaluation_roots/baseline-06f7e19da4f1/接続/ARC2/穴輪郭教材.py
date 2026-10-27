"""元のpalette一意fit後に重複semantic roleを保守的に検査する。"""
from itertools import permutations
from .既存穴輪郭 import color_components, component_background_holes, EIGHT_DELTAS, render_binary_object_hole_outline_renderer


def guarded_hole_outline(grid, parameters):
    if not grid or not grid[0] or len(grid) > 30 or len(grid[0]) > 30 or any(len(row) != len(grid[0]) for row in grid):
        return None, {'failure': 'invalid_grid'}
    if not isinstance(parameters, (list, tuple)) or len(parameters) != 5 or len(set(parameters)) != 5:
        return None, {'failure': 'invalid_role_palette'}
    background, obj, border, hole, filled = parameters
    output, record = render_binary_object_hole_outline_renderer(grid, *parameters)
    if output is None:
        return None, record
    proposals = {}
    components = color_components(grid, obj)
    for component in components:
        holes = component_background_holes(grid, component, background)
        hole_cells = set().union(*holes) if holes else set()
        body_color = filled if hole_cells else obj
        for cell in component['cells']:
            proposals.setdefault(cell, set()).add(body_color)
        for cell in hole_cells:
            proposals.setdefault(cell, set()).add(hole)
        for row, col in component['cells']:
            for dr, dc in EIGHT_DELTAS:
                rr, cc = row + dr, col + dc
                if (0 <= rr < len(grid) and 0 <= cc < len(grid[0])
                        and grid[rr][cc] == background and (rr, cc) not in hole_cells):
                    proposals.setdefault((rr, cc), set()).add(border)
    if any(len(values) != 1 for values in proposals.values()):
        return None, {'failure': 'conflicting_component_role_proposals'}
    expected = [row[:] for row in grid]
    for (row, col), values in proposals.items():
        expected[row][col] = next(iter(values))
    if output != expected:
        return None, {'failure': 'source_differs_from_simultaneous_roles'}
    return output, {**record, 'certified_role_proposal_cells': len(proposals)}


class 穴輪郭教材:
    def __init__(self, 教師群):
        self.方針 = None
        self.適合方針数 = 0
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        if any((len(p['input']), len(p['input'][0])) != (len(p['output']), len(p['output'][0])) for p in 教師群):
            return
        入力色 = sorted({v for p in 教師群 for row in p['input'] for v in row})
        新出力色 = sorted({v for p in 教師群 for row in p['output'] for v in row} - set(入力色))
        if len(入力色) != 2 or len(新出力色) < 3:
            return
        適合 = []
        for 背景色, 物体色 in permutations(入力色, 2):
            for 輪郭色, 穴色, 有穴物体色 in permutations(新出力色, 3):
                方針 = (背景色, 物体色, 輪郭色, 穴色, 有穴物体色)
                if all(render_binary_object_hole_outline_renderer(p['input'], *方針)[0] == p['output'] for p in 教師群):
                    適合.append(方針)
        self.適合方針数 = len(適合)
        if len(適合) != 1:
            return
        if all(guarded_hole_outline(p['input'], 適合[0])[0] == p['output'] for p in 教師群):
            self.方針 = 適合[0]

    def 候補(self, 格子, _policy):
        if self.方針 is None:
            return None, {'failure': '全教師を再現する穴輪郭方針が一意でない'}
        return guarded_hole_outline(格子, self.方針)

    def 記録(self):
        return {'適合方針数': self.適合方針数, '方針': self.方針}
