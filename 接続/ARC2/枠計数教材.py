"""Certify the fixed frame tally code, including witnessed unmatched-color removal."""
from collections import Counter
from . import 既存枠計数 as old


def guarded_render(grid, *, removal_witness=False):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    colors = Counter(v for row in grid for v in row)
    if sum(n == max(colors.values()) for n in colors.values()) != 1:
        return None, {'failure': 'background_tie'}
    background = old.dominant_background(grid)
    components = old.foreground_components(grid, background)
    covered = set()
    for component in components:
        cells = component['cells']
        if (not cells or component['size'] != len(cells) or covered.intersection(cells)
                or any(not (0 <= r < len(grid) and 0 <= c < len(grid[0]))
                       or grid[r][c] != component['color'] for r, c in cells)):
            return None, {'failure': 'component_coverage_invalid'}
        covered.update(cells)
    foreground = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != background}
    if covered != foreground:
        return None, {'failure': 'component_coverage_incomplete'}
    frames = [c for c in components if old.is_rectangular_frame(c)]
    small = [c for c in components if not old.is_rectangular_frame(c)]
    if len(frames) < 2:
        return None, {'failure': 'too_few_frames'}
    if len({f['color'] for f in frames}) != len(frames):
        return None, {'failure': 'duplicate_frame_color'}
    shapes = {(f['bbox'][2] - f['bbox'][0] + 1, f['bbox'][3] - f['bbox'][1] + 1) for f in frames}
    if len(shapes) != 1:
        return None, {'failure': 'mixed_frame_shapes'}
    for i, frame in enumerate(frames):
        a = frame['bbox']
        for other in frames[i + 1:]:
            b = other['bbox']
            if not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]):
                return None, {'failure': 'frame_boxes_overlap'}
    frame_colors = {f['color'] for f in frames}
    unmatched = [c for c in small if c['color'] not in frame_colors]
    if unmatched and not removal_witness:
        return None, {'failure': 'unmatched_removal_without_teacher_witness'}
    counts = Counter(c['color'] for c in small)
    expected = [[background] * len(grid[0]) for _ in grid]
    encoded = {}
    for frame in frames:
        color = frame['color']
        for r, c in frame['cells']:
            expected[r][c] = color
        r0, c0, r1, c1 = frame['bbox']
        slots = list(range(c0 + 2, c1 - 1, 2))
        count = counts[color]
        if count > len(slots):
            return None, {'failure': 'slot_overflow'}
        chosen = slots[-count:] if count else []
        for c in chosen:
            expected[(r0 + r1) // 2][c] = color
        encoded[color] = len(chosen)
    if any(encoded[color] != counts[color] for color in frame_colors):
        return None, {'failure': 'represented_counts_changed'}
    output, records = old.render_frame_component_count_slots(grid)
    if output is None or output != expected:
        return None, {'failure': 'source_output_disagrees_or_no_candidate'}
    return output, {'source_records': records, 'certificate': {
        'frame_count': len(frames), 'physical_item_count': len(small),
        'represented_item_count': sum(counts[c] for c in frame_colors),
        'encoded_by_color': encoded, 'unmatched_components': len(unmatched),
        'unmatched_pixels': sum(c['size'] for c in unmatched),
        'removal_witness': bool(removal_witness),
    }}


def fit_guarded(teachers):
    if not teachers or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return None
    if not all(old.render_frame_component_count_slots(p['input'])[0] == p['output'] for p in teachers):
        return None
    # 教師の完全再現を確認する段階だけ、消去の実証候補を検査する。
    checks = [guarded_render(p['input'], removal_witness=True) for p in teachers]
    if not all(output == p['output'] for (output, _), p in zip(checks, teachers)):
        return None
    witnesses = sum(record['certificate']['unmatched_components'] > 0 for _, record in checks)
    if not all(guarded_render(p['input'], removal_witness=witnesses > 0)[0] == p['output'] for p in teachers):
        return None
    return {'removal_witnesses': witnesses}


class 枠計数教材:
    def __init__(self, 教師群):
        fit = fit_guarded(教師群)
        self.適合 = fit is not None
        self.消去証拠数 = 0 if fit is None else fit['removal_witnesses']

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {'failure': '全教師を再現する枠計数なし'}
        return guarded_render(格子, removal_witness=self.消去証拠数 > 0)

    def 記録(self):
        return {'全教師再現': self.適合, '消去証拠数': self.消去証拠数}
