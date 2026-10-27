"""既存役割を教師で確定し、全領域と消去証拠を検査して元格子のみ通す。"""
from collections import Counter
from . import 既存種境界 as old
from .既存種境界 import (
    NEIGHBORS_4, NEIGHBORS_8, flood_same_color, same_color_components,
    adjacent_to_region, touches_grid_edge, seeded_boundary_barrier_recolor,
)


def guarded_render(grid, colors, *, removal_witness=False):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    if (not isinstance(colors, dict) or set(colors) != {'fill', 'seed', 'background', 'barrier'}
            or any(type(v) is not int or not 0 <= v <= 9 for v in colors.values())
            or len(set(colors.values())) != 4):
        return None, {'failure': 'invalid_distinct_roles'}
    fill, seed, background, barrier = (colors[k] for k in ('fill', 'seed', 'background', 'barrier'))
    if {v for row in grid for v in row} - {seed, background, barrier}:
        return None, {'failure': 'unknown_or_existing_fill_color'}
    height, width = len(grid), len(grid[0])
    seeds = [(r, c) for r in range(height) for c in range(width) if grid[r][c] == seed]
    if len(seeds) != 1:
        return None, {'failure': 'seed_not_unique'}
    sr, sc = seeds[0]
    starts = [(sr + dr, sc + dc) for dr, dc in NEIGHBORS_4
              if 0 <= sr + dr < height and 0 <= sc + dc < width
              and grid[sr + dr][sc + dc] == background]
    if not starts:
        return None, {'failure': 'no_seed_background_neighbor'}
    region = flood_same_color(grid, starts, background)
    components = same_color_components(grid, barrier)
    all_barriers = {(r, c) for r in range(height) for c in range(width) if grid[r][c] == barrier}
    covered = set().union(*components) if components else set()
    if covered != all_barriers or sum(map(len, components)) != len(covered):
        return None, {'failure': 'barrier_coverage_incomplete_or_overlapping'}
    preserved, edge_barriers = set(), set()
    for component in components:
        if adjacent_to_region(component, region, height, width):
            preserved.update(component)
            if touches_grid_edge(component, height, width):
                edge_barriers.update(component)
    removed = all_barriers - preserved
    if removed and not removal_witness:
        return None, {'failure': 'nonadjacent_removal_without_teacher_witness'}
    fills = {(r, c) for r, c in region
             if r in (0, height - 1) or c in (0, width - 1)
             or any((r + dr, c + dc) in edge_barriers for dr, dc in NEIGHBORS_8)}
    expected = [[background] * width for _ in range(height)]
    for r, c in preserved:
        expected[r][c] = barrier
    for r, c in fills:
        expected[r][c] = fill
    expected[sr][sc] = seed
    output, records = seeded_boundary_barrier_recolor(grid, colors)
    if output is None or output != expected:
        return None, {'failure': 'source_output_disagrees'}
    return output, {'source_records': records, 'certificate': {
        'seed_background_start_count': len(starts), 'seed_region_size': len(region),
        'barrier_components': len(components), 'barrier_pixels': len(all_barriers),
        'preserved_barrier_pixels': len(preserved), 'removed_barrier_pixels': len(removed),
        'fill_pixels': len(fills), 'removal_witness': bool(removal_witness),
    }}


class 種境界教材:
    def __init__(self, 教師群):
        self.色役割 = None
        self.消去証拠数 = 0
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        colors = old.infer_seed_boundary_colors({'train': 教師群})
        if colors is None:
            return
        raw_records = []
        for pair in 教師群:
            output, records = old.seeded_boundary_barrier_recolor(pair['input'], colors)
            if output is None or output != pair['output']:
                return
            raw_records.append(records)
        if not any(raw_records):
            return
        # 元役割と全raw教師再現を先に確定し、tieで別役割へ選び直さない。
        for pair in 教師群:
            counts = Counter(v for row in pair['input'] for v in row)
            if sum(n == max(counts.values()) for n in counts.values()) != 1:
                return
        witnesses = sum(any(any(not item['preserved'] for item in record['barrier_records'])
                            for record in records) for records in raw_records)
        if not all(guarded_render(p['input'], colors, removal_witness=witnesses > 0)[0] == p['output']
                   for p in 教師群):
            return
        self.色役割 = colors
        self.消去証拠数 = witnesses

    def 候補(self, 格子, _policy):
        if self.色役割 is None:
            return None, {'failure': '全教師を再現するseed境界役割なし'}
        return guarded_render(格子, self.色役割, removal_witness=self.消去証拠数 > 0)

    def 記録(self):
        return {'全教師再現': self.色役割 is not None, '色役割': self.色役割,
                '消去証拠数': self.消去証拠数}
