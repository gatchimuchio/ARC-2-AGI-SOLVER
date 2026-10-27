"""Certify a complete zero panel and the external inventory named by its markers."""
from collections import Counter
from . import 既存標識計数 as old


def guarded_render(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    counts = Counter(v for row in grid for v in row)
    if sum(n == max(counts.values()) for n in counts.values()) != 1:
        return None, {'failure': 'background_tie'}
    background = old.dominant_background(grid)
    if background == 0:
        return None, {'failure': 'zero_is_background'}
    panel, markers = old.extract_marker_panel(grid)
    if panel is None:
        return None, {'failure': 'raw_panel_unresolved', 'source_failure': markers}
    all_zero = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == 0}
    if set(panel['cells']) != all_zero:
        return None, {'failure': 'zero_cells_outside_selected_component'}
    r0, c0, r1, c1 = panel['bbox']
    region = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
    marker_map = {(r0 + m['row'], c0 + m['col']): m['color'] for m in markers}
    visible_markers = {(r, c): grid[r][c] for r, c in region if grid[r][c] != 0}
    if marker_map != visible_markers or len(marker_map) != len(markers):
        return None, {'failure': 'marker_coverage_incomplete_or_overlapping'}
    expected = [[0] * panel['width'] for _ in range(panel['height'])]
    external_counts = {}
    for marker in markers:
        color = marker['color']
        marker_cell = (r0 + marker['row'], c0 + marker['col'])
        components = old.color_components(grid, color, include_diagonal=True)
        inside, outside, covered = [], [], set()
        for component in components:
            cells = set(component['cells'])
            if not cells or covered & cells:
                return None, {'failure': 'inventory_coverage_invalid'}
            covered.update(cells)
            if cells & region and cells - region:
                return None, {'failure': 'marker_color_component_straddles_panel'}
            (inside if cells <= region else outside).append(cells)
        actual = {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value == color}
        if covered != actual or inside != [{marker_cell}]:
            return None, {'failure': 'marker_color_coverage_incomplete'}
        count = len(outside)
        if count < 1:
            return None, {'failure': 'missing_external_component'}
        columns = [marker['col'] + 2 * index for index in range(count)]
        if columns[-1] >= panel['width']:
            return None, {'failure': 'count_exceeds_panel_width'}
        for col in columns:
            expected[marker['row']][col] = color
        external_counts[color] = count
    if any(expected[m['row']][m['col']] != m['color'] for m in markers):
        return None, {'failure': 'marker_changed'}
    if Counter(v for row in expected for v in row if v != 0) != Counter(external_counts):
        return None, {'failure': 'listed_inventory_counts_changed'}
    output, records = old.render_marker_panel_inventory_count_lattice(grid)
    expected_panel = {'bbox': list(panel['bbox']), 'height': panel['height'],
                      'width': panel['width'], 'zero_cell_count': panel['size']}
    if (output is None or records.get('panel') != expected_panel or records.get('markers') != markers
            or output != expected):
        return None, {'failure': 'raw_selection_or_output_disagrees'}
    return output, {'source_records': records, 'certificate': {
        'zero_pixels': len(all_zero), 'marker_count': len(markers),
        'external_counts': external_counts, 'external_components': sum(external_counts.values()),
        'marker_added_to_count': False,
    }}


class 標識計数教材:
    def __init__(self, 教師群):
        self.適合 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        if not all(old.render_marker_panel_inventory_count_lattice(p['input'])[0] == p['output'] for p in 教師群):
            return
        self.適合 = all(guarded_render(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {'failure': '全教師を再現する標識計数panelなし'}
        return guarded_render(格子)

    def 記録(self):
        return {'全教師再現': self.適合}
