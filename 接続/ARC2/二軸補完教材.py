"""全有限軌道の既知整合と原入力witnessを証明する二軸補完教材。"""
from __future__ import annotations
from .既存二軸補完 import (pair_preserves_nonzero_and_fills_zero,
    zero_reflection_axes_for_pair, render_zero_mask_bidirectional_reflection_fill)

def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(value) is int and 0 <= value <= 9 for value in row)
                    for row in grid))

def guarded_render(grid, axes):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    height, width = len(grid), len(grid[0])
    if (not isinstance(axes, (tuple, list)) or len(axes) != 2
            or any(type(value) is not int for value in axes)):
        return None, {'failure': 'invalid_axes'}
    row_sum, col_sum = axes
    base = {'input_shape': [height, width], 'axes': [row_sum, col_sum]}
    if not (0 <= row_sum <= 2 * height - 2 and 0 <= col_sum <= 2 * width - 2):
        return None, {**base, 'failure': 'axis_centres_outside_canvas'}
    output = [row[:] for row in grid]
    visited = set()
    records = []
    missing_count = 0
    observed_count = 0
    for row in range(height):
        for col in range(width):
            if (row, col) in visited:
                continue
            orbit = sorted({(r, c) for r, c in (
                (row, col), (row_sum-row, col),
                (row, col_sum-col), (row_sum-row, col_sum-col))
                if 0 <= r < height and 0 <= c < width})
            if any(cell in visited for cell in orbit):
                return None, {**base, 'failure': 'orbit_partition_inconsistent'}
            visited.update(orbit)
            observed = [[r, c, grid[r][c]] for r, c in orbit if grid[r][c] != 0]
            missing = [[r, c] for r, c in orbit if grid[r][c] == 0]
            values = sorted({value for _r, _c, value in observed})
            if len(values) > 1:
                return None, {**base, 'failure': 'known_orbit_conflict',
                              'orbit': [list(cell) for cell in orbit], 'observed': observed}
            if not values:
                return None, {**base, 'failure': 'orbit_without_original_witness',
                              'orbit': [list(cell) for cell in orbit]}
            value = values[0]
            for r, c in missing:
                output[r][c] = value
            missing_count += len(missing)
            observed_count += len(observed)
            records.append({'cells': [list(cell) for cell in orbit],
                            'observed': observed, 'missing': missing, 'value': value})
    if missing_count == 0:
        return None, {**base, 'failure': 'no_zero_mask_cells'}
    if len(visited) != height*width or observed_count+missing_count != height*width:
        return None, {**base, 'failure': 'incomplete_orbit_coverage'}
    if any(output[r][c] != grid[r][c] for r in range(height)
           for c in range(width) if grid[r][c] != 0):
        return None, {**base, 'failure': 'known_cell_changed'}
    if any(value == 0 for row in output for value in row):
        return None, {**base, 'failure': 'zero_mask_incomplete'}
    original, raw_record = render_zero_mask_bidirectional_reflection_fill(grid, row_sum, col_sum)
    expected_record = {'row_reflection_sum': row_sum, 'col_reflection_sum': col_sum,
                       'filled_zero_count': missing_count, 'resolved_cell_count': missing_count}
    if original is None:
        return None, {**base, 'failure': 'original_renderer_failed', 'raw_record': raw_record}
    if original != output:
        return None, {**base, 'failure': 'original_grid_disagrees'}
    if raw_record != expected_record:
        return None, {**base, 'failure': 'original_record_disagrees'}
    return original, {**base, 'raw_record': raw_record, 'orbit_count': len(records),
                      'observed_cells_preserved': observed_count,
                      'filled_zero_count': missing_count, 'orbits': records}

def fit_teachers(train):
    if not isinstance(train, list) or len(train) < 2:
        return None, {'failure': 'too_few_teachers'}
    if any(not isinstance(pair, dict) or not valid_grid(pair.get('input'))
           or not valid_grid(pair.get('output')) for pair in train):
        return None, {'failure': 'invalid_teachers'}
    inputs = [tuple(map(tuple, pair['input'])) for pair in train]
    if len(set(inputs)) != len(inputs):
        return None, {'failure': 'duplicate_teacher_inputs'}
    raw_axis_records = []
    axis_sets = []
    for pair in train:
        ok, precheck = pair_preserves_nonzero_and_fills_zero(pair)
        candidates = zero_reflection_axes_for_pair(pair) if ok else []
        raw_axis_records.append({'precheck': precheck, 'axis_candidates': candidates})
        axis_sets.append({(a['row_reflection_sum'], a['col_reflection_sum']) for a in candidates})
    common = sorted(set.intersection(*axis_sets))
    base = {'raw_axis_records': raw_axis_records, 'common_axes': [list(a) for a in common]}
    if len(common) != 1:
        return None, {**base, 'failure': 'raw_common_axes_not_unique'}
    axes = common[0]
    raw_records = []
    for pair in train:
        output, record = render_zero_mask_bidirectional_reflection_fill(pair['input'], *axes)
        raw_records.append({'exact': output == pair['output'], 'record': record})
    base['raw_records'] = raw_records
    if not all(row['exact'] for row in raw_records):
        return None, {**base, 'failure': 'raw_teacher_mismatch'}
    teacher_records = []
    for pair in train:
        output, record = guarded_render(pair['input'], axes)
        teacher_records.append(record)
        if output != pair['output']:
            return None, {**base, 'failure': 'teacher_certificate_failed',
                          'teacher_records': teacher_records}
    return {'axes': list(axes)}, {**base, 'teacher_records': teacher_records}

class 二軸補完教材:
    def __init__(self, 教師群):
        model, record = fit_teachers(教師群)
        self.軸 = tuple(model['axes']) if model is not None else None
        if self.軸 is None:
            # A fitted original view owns every success and HOLD unchanged.
            # The masked crop view is considered only outside that fit domain.
            from .遮蔽軌道窓 import fit
            self.遮蔽モデル, masked_record = fit(教師群)
            self.視点判定 = {
                "旧視点不成立": record.get('failure'),
                "遮蔽視点": "成立" if self.遮蔽モデル is not None else "不成立",
                "遮蔽不成立": masked_record.get('failure'),
                "競合制御": "旧視点成立時は遮蔽fitを実行せず旧成功とHOLDを保持",
            }

    def 候補(self, 格子, _policy):
        if self.軸 is None:
            if self.遮蔽モデル is None:
                return None, {"failure": "全教師を再現する共有二軸なし"}
            from .遮蔽軌道窓 import predict
            output, record = predict(格子, self.遮蔽モデル)
            return output, {"view": "masked_orbit", "view_selection": self.視点判定,
                            "masked_record": record}
        return guarded_render(格子, self.軸)

    def 記録(self):
        if self.軸 is not None:
            return {"共有反射和": list(self.軸)}
        return {"共有反射和": None, "視点判定": self.視点判定,
                "遮蔽モデル": self.遮蔽モデル}
