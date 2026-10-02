"""全header/run対応とcue保存を確認し、元順位着色だけをHDSへ渡す。"""
from collections import Counter
from .既存順位着色 import (
    same_color_components_4, top_header_rank_by_color, vertical_bounded_runs,
    apply_header_ranked_vertical_run_recolor,
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
    colors = set(grid[0]) - {background}
    if not colors:
        return None, {'failure': 'no_header_colors'}
    for color in colors:
        components = [c for c in same_color_components_4(grid, color)
                      if any(r == 0 for r, _ in c)]
        if len(components) != 1:
            return None, {'failure': 'top_color_component_not_unique', 'color': color}
    headers = top_header_rank_by_color(grid, background)
    runs = vertical_bounded_runs(grid, background)
    by_target = {}
    for run in runs:
        by_target.setdefault(run['target'], []).append(run)
    if set(by_target) != colors or set(headers) != colors:
        return None, {'failure': 'header_and_run_target_sets_differ'}
    protected = {tuple(cell) for header in headers.values() for cell in header['component']}
    protected.update((run[key], run['col']) for run in runs
                     for key in ('top_endpoint_row', 'bottom_endpoint_row'))
    proposals = {}
    for color, candidates in by_target.items():
        rank = headers[color]['rank']
        if not 1 <= rank <= len(candidates):
            return None, {'failure': 'header_rank_out_of_range', 'color': color}
        ordered = sorted(candidates, key=lambda r: (r['top_endpoint_row'], r['col'], r['bottom_endpoint_row']))
        selected = ordered[rank - 1]
        for row in range(selected['start'], selected['end'] + 1):
            cell = row, selected['col']
            if cell in protected:
                return None, {'failure': 'selected_run_overwrites_cue', 'cell': list(cell)}
            if cell in proposals and proposals[cell] != color:
                return None, {'failure': 'conflicting_run_recolors', 'cell': list(cell)}
            proposals[cell] = color
    output, record = apply_header_ranked_vertical_run_recolor(grid)
    if output is None:
        return None, record or {'failure': 'source_no_candidate'}
    expected = [row[:] for row in grid]
    for (r, c), color in proposals.items():
        expected[r][c] = color
    if output != expected:
        return None, {'failure': 'source_output_disagrees'}
    return output, record


class 順位着色教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        self.全教師再現 = all(guarded_render(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現するheader順位着色なし'}
        return guarded_render(格子)

    def 記録(self):
        return {'全教師再現': self.全教師再現}
