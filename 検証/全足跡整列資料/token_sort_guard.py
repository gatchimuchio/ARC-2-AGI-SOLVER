"""Certify the source's complete token footprints before its fixed reassignment."""
from collections import Counter
import token_sort_primitives as old


def raw_axis(grid, background):
    candidates = []
    for row in range(1, len(grid) - 1):
        counts = Counter(v for v in grid[row] if v != background)
        if sum(counts.values()) < 5 or max(counts.values(), default=0) < 3:
            continue
        colors = [c for c, n in counts.items() if n == max(counts.values())]
        if len(colors) != 1:
            return None, {'failure': 'raw_axis_color_tie', 'row': row}
        color = colors[0]
        tokens = old.contiguous_axis_tokens(grid, row, background, color)
        if len(tokens) >= 3:
            candidates.append((row, color, tokens))
    if len(candidates) != 1:
        return None, {'failure': 'raw_axis_count_not_one', 'count': len(candidates)}
    return candidates[0], None


def guarded_render(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row) for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    height, width = len(grid), len(grid[0])
    counts = Counter(v for row in grid for v in row)
    if sum(n == max(counts.values()) for n in counts.values()) != 1:
        return None, {'failure': 'background_tie'}
    background = old.dominant_color(grid)
    axis, failure = raw_axis(grid, background)
    if axis is None:
        return None, failure
    row, axis_color, tokens = axis
    footprints, covered = [], set()
    for left, right, color in tokens:
        offsets = old.token_footprint_offsets(grid, row, left, right, color)
        if not offsets or 0 not in offsets or not old.is_contiguous_offset_interval(offsets):
            return None, {'failure': 'invalid_token_footprint'}
        cells = {(row + dr, col) for dr in offsets for col in range(left, right + 1)}
        if (covered & cells or any(not (0 <= r < height and 0 <= c < width) or grid[r][c] != color
                                   for r, c in cells)):
            return None, {'failure': 'footprint_coverage_invalid'}
        component, pending = {(row, left)}, [(row, left)]
        while pending:
            r, c = pending.pop()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                q = r + dr, c + dc
                if (q not in component and 0 <= q[0] < height and 0 <= q[1] < width
                        and grid[q[0]][q[1]] == color):
                    component.add(q)
                    pending.append(q)
        if component != cells:
            return None, {'failure': 'partial_token_component'}
        covered.update(cells)
        footprints.append(offsets)
    sorted_footprints = sorted(footprints, key=lambda offsets: (len(offsets), min(offsets), max(offsets)))
    if Counter(sorted_footprints) != Counter(footprints):
        return None, {'failure': 'footprint_multiplicity_changed'}
    expected = [line[:] for line in grid]
    for r, c in covered:
        expected[r][c] = background
    proposals = {}
    for (left, right, color), offsets in zip(tokens, sorted_footprints):
        for dr in offsets:
            for c in range(left, right + 1):
                q = row + dr, c
                if not (0 <= q[0] < height and 0 <= q[1] < width):
                    return None, {'failure': 'reassigned_footprint_out_of_bounds'}
                if q in proposals and proposals[q] != color:
                    return None, {'failure': 'different_color_proposals_overlap'}
                if q not in covered and grid[q[0]][q[1]] not in (background, color):
                    return None, {'failure': 'stationary_foreground_overwrite'}
                proposals[q] = color
    for (r, c), color in proposals.items():
        expected[r][c] = color
    affected = covered | set(proposals)
    if expected[row] != grid[row] or any(expected[r][c] != grid[r][c]
            for r in range(height) for c in range(width) if (r, c) not in affected):
        return None, {'failure': 'axis_or_outside_cells_changed'}
    output, source_record = old.render_axis_token_footprint_sorter(grid)
    expected_record = {'axis_row': row, 'axis_color': axis_color, 'background': background,
                       'tokens': [{'col0': l, 'col1': r, 'color': c} for l, r, c in tokens],
                       'footprint_lengths': [len(x) for x in footprints],
                       'sorted_footprint_lengths': [len(x) for x in sorted_footprints],
                       'shape': [height, width], 'candidate_count': 1}
    if output is None:
        return None, {'failure': 'source_no_candidate', 'source_record': source_record}
    if output != expected or source_record != expected_record:
        return None, {'failure': 'source_output_or_record_disagrees'}
    return output, {'source_record': source_record, 'certificate': {
        'raw_axes': 1, 'token_components': len(tokens), 'original_footprints': footprints,
        'reassigned_footprints': sorted_footprints, 'original_token_pixels': len(covered),
        'reassigned_token_pixels': len(proposals), 'outside_affected_cells': height * width - len(affected),
    }}


def fit_guarded(teachers):
    if not teachers or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return False
    if not all(old.render_axis_token_footprint_sorter(p['input'])[0] == p['output'] for p in teachers):
        return False
    return all(guarded_render(p['input'])[0] == p['output'] for p in teachers)
