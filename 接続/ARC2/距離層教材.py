"""全領域・seed保存を検査し、元距離層充填だけをHDSへ渡す。"""
from collections import Counter
from .既存距離層 import (
    detect_separator, separator_cells, open_components, boundary_layers_8,
    seeded_separator_layer_fill,
)


def guarded_render(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    counts = Counter(v for row in grid for v in row)
    backgrounds = [v for v, n in counts.items() if n == max(counts.values())]
    if len(backgrounds) != 1:
        return None, {'failure': 'background_tie'}
    background = backgrounds[0]
    separator, record = detect_separator(grid)
    if separator is None:
        return None, record
    height, width = len(grid), len(grid[0])
    blocked = separator_cells(grid, separator)
    regions = open_components(grid, blocked)
    all_cells = {(r, c) for r in range(height) for c in range(width)}
    union = set().union(*regions) if regions else set()
    if union != all_cells - blocked or sum(map(len, regions)) != len(union):
        return None, {'failure': 'region_partition_incomplete_or_overlapping'}
    output, record = seeded_separator_layer_fill(grid)
    if output is None:
        return None, record or {'failure': 'source_no_candidate'}
    expected = [row[:] for row in grid]
    for region in regions:
        layers = boundary_layers_8(region, height, width)
        if set(layers) != region:
            return None, {'failure': 'region_layer_coverage_incomplete'}
        palette = {}
        for r, c in region:
            value = grid[r][c]
            if value == background:
                continue
            layer = layers[r, c]
            if layer in palette and palette[layer] != value:
                return None, {'failure': 'same_layer_seed_conflict'}
            palette[layer] = value
        if not palette:
            # 未seed領域は原入力のまま保持する。
            continue
        period = max(palette) + 1
        for r, c in region:
            expected[r][c] = palette.get(layers[r, c] % period, background)
    if output != expected:
        return None, {'failure': 'source_output_disagrees'}
    if any(output[r][c] != value for r, row in enumerate(grid)
           for c, value in enumerate(row) if value != background):
        return None, {'failure': 'seed_or_separator_changed'}
    return output, record


class 距離層教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        self.背景位相証拠数 = 0
        self.無seed保存証拠数 = 0
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        records = []
        for pair in 教師群:
            output, record = guarded_render(pair['input'])
            if output is None or output != pair['output']:
                return
            records.append(record)
        self.全教師再現 = True
        # 分岐を示す教師の件数であり、native支持へ別加算しない。
        self.背景位相証拠数 = sum(any(len(r['layer_colors']) < len(r['sequence'])
                                  for r in record['rewrite_records']) for record in records)
        self.無seed保存証拠数 = sum(record['open_component_count'] > len(record['rewrite_records'])
                                  for record in records)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する距離層周期充填なし'}
        return guarded_render(格子)

    def 記録(self):
        return {'全教師再現': self.全教師再現, '背景位相証拠数': self.背景位相証拠数,
                '無seed保存証拠数': self.無seed保存証拠数}
