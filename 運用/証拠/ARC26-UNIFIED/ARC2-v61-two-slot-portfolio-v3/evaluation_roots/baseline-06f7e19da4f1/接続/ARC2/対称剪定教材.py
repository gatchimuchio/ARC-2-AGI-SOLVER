"""完全保持を含む全axisの一意最大と元選択を証明して元格子のみ通す。"""
from collections import Counter
from .既存対称剪定 import (
    same_color_components_8, vertical_prune_candidate, apply_vertical_symmetry_pruning,
    MAX_REMOVAL_FRACTION_DIVISOR,
)


def owned_row_gaps(grid, cells, background):
    """Background intervals bracketed by this C8 object's cells on the same row.

    This is a row-span ownership view, not a connected-cavity requirement.
    Another color inside the span invalidates ownership rather than being erased.
    """
    cell_set = set(cells)
    gaps = set()
    for row in {r for r, _ in cells}:
        cols = [c for r, c in cells if r == row]
        for col in range(min(cols), max(cols) + 1):
            if (row, col) not in cell_set:
                if grid[row][col] != background:
                    return None
                gaps.add((row, col))
    return gaps


def complete_gap_axes(gaps):
    if not gaps:
        return []
    low, high = min(c for _, c in gaps), max(c for _, c in gaps)
    return [axis2 for axis2 in range(2 * low, 2 * high + 1)
            if all((r, axis2 - c) in gaps for r, c in gaps)]


def gap_relation_supported(grid):
    """Every teacher gap view agrees with its original unique foreground axis."""
    output, record = guarded_render(grid)
    if output is None:
        return False
    background = record['background']
    witnessed = False
    for color in sorted(set(v for row in grid for v in row) - {background}):
        for cells in same_color_components_8(grid, color):
            gaps = owned_row_gaps(grid, cells, background)
            if gaps is None:
                return False
            if not gaps:
                continue
            witnessed = True
            original = vertical_prune_candidate(cells)
            if original is None or complete_gap_axes(gaps) != [original['axis2']]:
                return False
    return witnessed


def guarded_render(grid, *, bind_owned_gaps=False):
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
            axis_binding = None
            if len(maxima) != 1:
                if not bind_owned_gaps:
                    return None, {'failure': 'maximum_retention_axis_tie', 'color': color}
                gaps = owned_row_gaps(grid, cells, background)
                gap_axes = complete_gap_axes(gaps)
                eligible = [(a, k) for a, k in maxima if a in gap_axes]
                axis_binding = {
                    'foreground_maxima': [{'axis2': a, 'kept': sorted(k),
                                            'removed': sorted(cell_set - k)} for a, k in maxima],
                    'owned_gap_cells': sorted(gaps) if gaps is not None else None,
                    'complete_gap_axes': gap_axes,
                }
                if len(gap_axes) != 1 or len(eligible) != 1:
                    return None, {'failure': 'maximum_retention_axis_tie', 'color': color,
                                  'owned_gap_binding': axis_binding}
                axis2, kept = eligible[0]
            else:
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
            if axis_binding is not None:
                certificates[-1]['owned_gap_binding'] = axis_binding
    output, record = apply_vertical_symmetry_pruning(grid)
    if output is None:
        return None, record or {'failure': 'source_no_candidate'}
    if output != expected:
        return None, {'failure': 'source_output_disagrees'}
    return output, {**record, 'maximum_retention_certificate': certificates}


class 対称剪定教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        self.所有間隙軸支持 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        self.全教師再現 = all(guarded_render(p['input'])[0] == p['output'] for p in 教師群)
        self.所有間隙軸支持 = self.全教師再現 and all(gap_relation_supported(p['input']) for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する最大保持対称剪定なし'}
        return guarded_render(格子, bind_owned_gaps=self.所有間隙軸支持)

    def 記録(self):
        return {'全教師再現': self.全教師再現, '所有間隙軸支持': self.所有間隙軸支持}
