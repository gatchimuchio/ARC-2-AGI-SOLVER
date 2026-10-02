"""完全保持を含む全axisの一意最大と元選択を証明して元格子のみ通す。"""
from collections import Counter
from .既存対称剪定 import (
    same_color_components_8, vertical_prune_candidate, apply_vertical_symmetry_pruning,
    MAX_REMOVAL_FRACTION_DIVISOR,
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
    expected = [row[:] for row in grid]
    certificates = []
    for color in sorted(set(counts) - {background}):
        for cells in same_color_components_8(grid, color):
            cell_set = set(cells)
            low, high = min(c for _, c in cells), max(c for _, c in cells)
            maxima, best_count = [], -1
            for axis2 in range(2 * low, 2 * high + 1):
                kept = {p for p in cell_set if (p[0], axis2 - p[1]) in cell_set}
                if len(kept) > best_count:
                    maxima, best_count = [(axis2, kept)], len(kept)
                elif len(kept) == best_count:
                    maxima.append((axis2, kept))
            if len(maxima) != 1:
                return None, {'failure': 'maximum_retention_axis_tie', 'color': color}
            axis2, kept = maxima[0]
            removed = cell_set - kept
            limit = max(3, len(cells) // MAX_REMOVAL_FRACTION_DIVISOR + 1)
            if len(removed) > limit:
                return None, {'failure': 'component_over_original_removal_limit', 'color': color}
            original = vertical_prune_candidate(cells)
            if not removed:
                if original is not None:
                    return None, {'failure': 'source_excludes_complete_symmetry', 'color': color}
            elif (original is None or original['axis2'] != axis2 or original['kept'] != kept):
                return None, {'failure': 'source_axis_disagrees', 'color': color}
            for r, c in removed:
                expected[r][c] = background
            certificates.append({'color': color, 'component_size': len(cells), 'axis2': axis2,
                                 'kept_count': len(kept), 'removed_count': len(removed),
                                 'original_removal_limit': limit})
    output, record = apply_vertical_symmetry_pruning(grid)
    if output is None:
        return None, record or {'failure': 'source_no_candidate'}
    if output != expected:
        return None, {'failure': 'source_output_disagrees'}
    return output, {**record, 'maximum_retention_certificate': certificates}


class 対称剪定教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        self.全教師再現 = all(guarded_render(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する最大保持対称剪定なし'}
        return guarded_render(格子)

    def 記録(self):
        return {'全教師再現': self.全教師再現}
