"""最小periodを先決し全行と両境界を確認して元格子だけをHDSへ渡す。"""
from collections import Counter
from .既存反復行 import (
    infer_panel_periods, select_panel_period, periodic_panel_anomaly_compress,
)


def guarded_render(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    periods = infer_panel_periods(grid)
    if not periods:
        return None, {'failure': 'no_periodic_boundary_columns'}
    period = min(periods)
    if select_panel_period(grid) != period:
        return None, {'failure': 'source_period_not_minimum'}
    panel_count = (len(grid[0]) - 1) // period
    expected, row_records = [], []
    for index, row in enumerate(grid):
        chunks = [tuple(row[i * period:(i + 1) * period]) for i in range(panel_count)]
        counts = Counter(chunks)
        singletons = [chunk for chunk, count in counts.items() if count == 1]
        if len(counts) == 1:
            chosen, branch = chunks[0], 'all_identical'
        elif len(singletons) == 1:
            chosen, branch = singletons[0], 'unique_singleton'
        else:
            return None, {'failure': 'ambiguous_row_at_minimum_period', 'row': index,
                          'period': period, 'raw_periods': periods}
        candidate = list(chosen) + [row[-1]]
        if len(candidate) != period + 1 or candidate[0] != row[0] or candidate[-1] != row[-1]:
            return None, {'failure': 'row_boundary_or_width_disagrees'}
        expected.append(candidate)
        row_records.append({'row': index, 'branch': branch,
                            'multiplicities': sorted(counts.values())})
    output = periodic_panel_anomaly_compress(grid)
    if output is None or output != expected or len(output) != len(grid):
        return None, {'failure': 'source_output_disagrees'}
    return output, {'raw_periods': periods, 'period': period, 'panel_count': panel_count,
                    'row_records': row_records, 'output_shape': [len(output), period + 1]}


class 反復行教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        self.全教師再現 = all(guarded_render(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する最小周期の反復行抽出なし'}
        return guarded_render(格子)

    def 記録(self):
        return {'全教師再現': self.全教師再現}
