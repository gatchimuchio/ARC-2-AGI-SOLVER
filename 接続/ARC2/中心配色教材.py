"""Certify unique palette votes, target partition and unchanged source output."""
from collections import Counter
from . import 既存中心配色 as old


def integer_sector(component, origin):
    row0, col0 = origin
    count = len(component)
    row_sum = sum(row for row, _ in component)
    col_sum = sum(col for _, col in component)
    vertical = 'top' if row_sum < row0 * count else 'bottom' if row_sum > (row0 + 2) * count else ''
    horizontal = 'left' if col_sum < col0 * count else 'right' if col_sum > (col0 + 2) * count else ''
    return '_'.join(part for part in (vertical, horizontal) if part) or None


def sector_contains(sector, row, col, origin):
    row0, col0 = origin
    return (('top' not in sector or row < row0)
            and ('bottom' not in sector or row > row0 + 2)
            and ('left' not in sector or col < col0)
            and ('right' not in sector or col > col0 + 2))


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
    background = old._dominant_color(grid)
    components = [(color, component) for color in sorted(set(counts) - {background})
                  for component in old._barrier_component_records(grid, color)]
    if not components:
        return None, {'failure': 'missing_foreground'}
    maximum = max(len(c['cells']) for _, c in components)
    largest = [(color, c) for color, c in components if len(c['cells']) == maximum]
    if len(largest) != 1:
        return None, {'failure': 'largest_target_tie'}
    target_color, target = largest[0]
    target_cells = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == target_color}
    if target_cells != set(target['cells']):
        return None, {'failure': 'split_target_color'}
    source_cells = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row)
                    if v not in (background, target_color)}
    source_colors = sorted({grid[r][c] for r, c in source_cells})
    if len(source_colors) != 2:
        return None, {'failure': 'source_palette_not_two'}
    origins = [(r, c) for r in range(height - 2) for c in range(width - 2)
               if {(y, x) for y in range(r, r + 3) for x in range(c, c + 3)} <= target_cells]
    if len(origins) != 1:
        return None, {'failure': 'anchor_not_unique_3x3'}
    row0, col0 = origin = origins[0]
    perimeter = {(r, c) for r in range(row0, row0 + 3) for c in range(col0, col0 + 3)
                 if r in (row0, row0 + 2) or c in (col0, col0 + 2)}
    center = {(row0 + 1, col0 + 1)}
    parts = old._palette_cell_components(target_cells - perimeter)
    if (set().union(*parts) != target_cells - perimeter
            or sum(len(part) for part in parts) != len(target_cells - perimeter)
            or sum(part == center for part in parts) != 1):
        return None, {'failure': 'target_partition_incomplete'}
    proposals, assignments, used_source = {}, [], set()
    area_votes = Counter()
    for component in parts:
        if component == center:
            continue
        sector = integer_sector(component, origin)
        raw_sector = old._target_square_palette_sector(component, origin)
        if sector is None or raw_sector is None or raw_sector[0] != sector:
            return None, {'failure': 'centroid_sector_unresolved_or_disagrees'}
        candidates = {p for p in source_cells if sector_contains(sector, *p, origin)}
        if candidates != {p for p in source_cells if raw_sector[1](*p)}:
            return None, {'failure': 'source_sector_predicate_disagrees'}
        votes = Counter(grid[r][c] for r, c in candidates)
        if not votes:
            return None, {'failure': 'sector_has_no_source_votes'}
        winners = [color for color, n in votes.items() if n == max(votes.values())]
        if len(winners) != 1:
            return None, {'failure': 'sector_source_vote_tie'}
        color = winners[0]
        used_source.update(candidates)
        area_votes[color] += len(component)
        for cell in component:
            if cell in proposals:
                return None, {'failure': 'target_component_overlap'}
            proposals[cell] = color
        assignments.append({'sector': sector, 'component_size': len(component),
                            'selected_color': color,
                            'source_counts': {str(c): n for c, n in sorted(votes.items())}})
    if not area_votes:
        return None, {'failure': 'missing_outer_components'}
    center_winners = [color for color, n in area_votes.items() if n == max(area_votes.values())]
    if len(center_winners) != 1:
        return None, {'failure': 'center_area_vote_tie'}
    center_color = center_winners[0]
    proposals[row0 + 1, col0 + 1] = center_color
    if set(proposals) != target_cells - perimeter:
        return None, {'failure': 'target_proposal_coverage_incomplete'}
    expected = [row[:] for row in grid]
    for (r, c), color in proposals.items():
        expected[r][c] = color
    protected = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row)
                 if v != target_color} | perimeter
    if any(expected[r][c] != grid[r][c] for r, c in protected):
        return None, {'failure': 'perimeter_background_or_source_changed'}
    expected_record = {'renderer_case': 'target_square_quadrant_palette_rewrite',
        'background_color': background, 'target_color': target_color, 'source_colors': source_colors,
        'square_origin': list(origin), 'outer_component_count': len(assignments),
        'center_color': center_color, 'assignments': assignments,
        'source_patch_count': len(old._palette_cell_components(source_cells, diagonal=True))}
    output, source_record = old._target_square_palette_render(grid)
    if output != expected or source_record != expected_record:
        return None, {'failure': 'source_output_or_record_disagrees'}
    return output, {'source_record': source_record, 'certificate': {
        'target_cells': len(target_cells), 'recolored_target_cells': len(proposals),
        'preserved_perimeter_cells': len(perimeter), 'protected_cells': len(protected),
        'source_cells': len(source_cells), 'source_cells_used_in_at_least_one_vote': len(used_source),
        'source_cells_unused_and_preserved': len(source_cells - used_source),
        'center_area_votes': dict(area_votes)}}


def fit_guarded(teachers):
    if len(teachers) < 2 or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return False
    if not all(old._target_square_palette_render(p['input'])[0] == p['output'] for p in teachers):
        return False
    return all(guarded_render(p['input'])[0] == p['output'] for p in teachers)


class 中心配色教材:
    def __init__(self, 教師群):
        self.適合 = fit_guarded(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する中心配色なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師再現": self.適合}
