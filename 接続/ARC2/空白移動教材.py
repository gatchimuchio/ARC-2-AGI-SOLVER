"""全0矩形を要求し、教師で一意な既存配置グラフpriorをHDSへ渡す。"""
from . import 既存空白移動 as old
from .既存空白移動 import (
    connected_components_4, is_rectangle, rect_cells,
    render_farthest_blank_rectangle_relocator,
)


def guarded_render(grid, fill_color, marker_color):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    if (type(fill_color) is not int or type(marker_color) is not int
            or not 1 <= fill_color <= 9 or not 1 <= marker_color <= 9
            or fill_color == marker_color):
        return None, {'failure': 'invalid_distinct_nonzero_roles'}
    zeros = connected_components_4(grid, 0)
    if len(zeros) != 1 or not is_rectangle(zeros[0]):
        return None, {'failure': 'all_zero_cells_must_form_one_rectangle'}
    output, record = render_farthest_blank_rectangle_relocator(grid, fill_color, marker_color)
    if output is None:
        return None, record
    source = set(rect_cells(tuple(record['source_bbox'])))
    target = set(rect_cells(tuple(record['target_bbox'])))
    if source != set(zeros[0]) or len(source) != len(target):
        return None, {'failure': 'rectangle_accounting_mismatch'}
    expected = [row[:] for row in grid]
    for r, c in source:
        expected[r][c] = fill_color
    for r, c in target:
        if grid[r][c] not in (0, fill_color, marker_color):
            return None, {'failure': 'target_contains_obstacle_color'}
        expected[r][c] = 0
    if output != expected or sum(v == 0 for row in output for v in row) != len(source):
        return None, {'failure': 'source_output_or_blank_area_mismatch'}
    return output, record


class 空白移動教材:
    def __init__(self, 教師群):
        self.役割 = None
        self.生適合数 = 0
        self.教師記録 = []
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        fits = []
        for marker in old.marker_color_candidates({'train': 教師群}):
            records, fills = [], set()
            for pair in 教師群:
                model = old.train_transition_model(pair)
                if model is None:
                    break
                fill = model['fill_color']
                fills.add(fill)
                output, record = old.render_farthest_blank_rectangle_relocator(pair['input'], fill, marker)
                if output is None or output != pair['output']:
                    break
                records.append(record)
            else:
                if len(fills) == 1:
                    fits.append((next(iter(fills)), marker, records))
        self.生適合数 = len(fits)
        # 元の全教師適合を先に一意と確定する。guardで競合役割を間引かない。
        if len(fits) != 1:
            return
        fill, marker, records = fits[0]
        if not all(guarded_render(p['input'], fill, marker)[0] == p['output'] for p in 教師群):
            return
        self.役割 = (fill, marker)
        self.教師記録 = records

    def 候補(self, 格子, _policy):
        if self.役割 is None:
            return None, {'failure': '全教師を再現する一意な空白移動役割なし'}
        return guarded_render(格子, *self.役割)

    def 記録(self):
        return {'全教師再現': self.役割 is not None, '生適合数': self.生適合数,
                'fill_color': self.役割[0] if self.役割 else None,
                'marker_color': self.役割[1] if self.役割 else None,
                '教師記録': self.教師記録}
