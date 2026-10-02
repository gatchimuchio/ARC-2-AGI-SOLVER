"""入力役割と保存条件を確認して元の行周期priorを教師化する。"""
from collections import Counter
from . import 既存行周期 as old


def raw_separator_candidates(grid, background):
    height, width = old.grid_shape(grid)
    candidates = []
    for col in range(1, width - 1):
        values = [grid[row][col] for row in range(height) if grid[row][col] != background]
        if not values or len(set(values)) != 1:
            continue
        color = values[0]
        required = [row for row in range(height)
                    if any(grid[row][c] != background for c in range(width) if c != col)]
        if any(grid[row][col] != color for row in required):
            continue
        if len(values) < max(2, len(required)):
            continue
        candidates.append({'col': col, 'color': color, 'non_background_count': len(values),
                           'required_row_count': len(required)})
    return candidates


def guarded_separator_run(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_grid'}
    counts = Counter(v for row in grid for v in row)
    backgrounds = [v for v, n in counts.items() if n == max(counts.values())]
    if len(backgrounds) != 1:
        return None, {'failure': 'background_tie'}
    background = backgrounds[0]
    candidates = raw_separator_candidates(grid, background)
    if len(candidates) != 1:
        return None, {'failure': 'raw_separator_not_unique', 'candidate_count': len(candidates)}
    chosen = candidates[0]
    original_choice = old.find_partial_vertical_separator(grid, background)
    if original_choice is None or original_choice[2] != chosen:
        return None, {'failure': 'source_separator_disagrees'}
    output, record = old.render_separator_run_period_superposition(grid)
    if output is None:
        return None, record
    if old.grid_shape(output) != old.grid_shape(grid):
        return None, {'failure': 'output_shape_changed'}
    col = chosen['col']
    for row, values in enumerate(grid):
        if output[row][col] != values[col]:
            return None, {'failure': 'separator_changed'}
        left_active = any(v != background for v in values[:col])
        right_active = any(v != background for v in values[col + 1:])
        if left_active and right_active:
            return None, {'failure': 'both_sides_active'}
        if left_active and output[row][:col] != values[:col]:
            return None, {'failure': 'active_code_changed'}
        if right_active and output[row][col + 1:] != values[col + 1:]:
            return None, {'failure': 'active_code_changed'}
        if not left_active and not right_active and output[row] != values:
            return None, {'failure': 'inactive_row_changed'}
    return output, {**record, 'raw_separator_count': len(candidates)}


class 行周期教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        self.全教師再現 = all(guarded_separator_run(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する行周期合成なし'}
        return guarded_separator_run(格子)

    def 記録(self):
        return {'全教師再現': self.全教師再現}
