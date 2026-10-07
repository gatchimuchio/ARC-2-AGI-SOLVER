"""Certify complete, simultaneous replacement under the source normalization rules."""
from collections import Counter, defaultdict
from . import 既存倍率置換 as old


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
    background = old.dominant_background(grid)
    components = old.extract_motif_components(grid)
    if len(components) < 2:
        return None, {'failure': 'too_few_motif_components'}
    foreground = {(r, c): v for r, row in enumerate(grid) for c, v in enumerate(row) if v != background}
    covered, records, groups = {}, [], defaultdict(list)
    for index, component in enumerate(components):
        cells = {(r, c): v for r, c, v in component['cells']}
        if (len(cells) != len(component['cells']) or len(cells) != component['size']
                or set(cells) & set(covered) or any(foreground.get(p) != v for p, v in cells.items())):
            return None, {'failure': 'component_coverage_invalid'}
        covered.update(cells)
        pattern = old.pattern_from_component(component)
        scale, primitive = old.compress_pattern(pattern)
        ph, pw = len(pattern), len(pattern[0])
        valid_scales = [s for s in range(1, min(ph, pw) + 1)
                        if ph % s == 0 and pw % s == 0
                        and all(pattern[r][c] == pattern[(r // s) * s][(c // s) * s]
                                for r in range(ph) for c in range(pw))]
        if scale != max(valid_scales):
            return None, {'failure': 'source_maximum_scale_disagrees'}
        top, left, bottom, right = component['bbox']
        expanded = {(r, c): v for r, c, v in old.scaled_pattern_cells(primitive, scale, top, left)}
        if (expanded != cells or len(primitive) * scale != bottom - top + 1
                or len(primitive[0]) * scale != right - left + 1):
            return None, {'failure': 'primitive_inverse_expansion_disagrees'}
        records.append({'component': component, 'scale': scale, 'primitive': primitive,
                        'valid_scales': valid_scales})
        groups[primitive].append(index)
    if covered != foreground:
        return None, {'failure': 'foreground_coverage_incomplete'}
    if len(groups) != 2:
        return None, {'failure': 'primitive_group_count_not_two'}
    a, b = sorted(groups, key=lambda p: (len(p), len(p[0]), repr(p)))
    common = old.pattern_colors(a) & old.pattern_colors(b)
    if not common:
        return None, {'failure': 'no_common_anchor_color'}
    anchor_counts = {c: old.pattern_color_count(a, c) + old.pattern_color_count(b, c) for c in common}
    winners = [c for c, n in anchor_counts.items() if n == min(anchor_counts.values())]
    if len(winners) != 1:
        return None, {'failure': 'anchor_color_count_tie'}
    anchor = winners[0]
    if old.choose_anchor_color(a, b) != anchor:
        return None, {'failure': 'source_anchor_color_disagrees'}
    proposals, placements, anchor_blocks = {}, [], []
    overlaps = 0
    for record in records:
        component, scale, source = record['component'], record['scale'], record['primitive']
        target = b if source == a else a
        source_cell = min((r, c) for r, row in enumerate(source) for c, v in enumerate(row) if v == anchor)
        target_cell = min((r, c) for r, row in enumerate(target) for c, v in enumerate(row) if v == anchor)
        source_anchor = tuple(v * scale for v in source_cell)
        target_anchor = tuple(v * scale for v in target_cell)
        if (old.anchor_offset(source, anchor, scale) != source_anchor
                or old.anchor_offset(target, anchor, scale) != target_anchor):
            return None, {'failure': 'source_fixed_anchor_disagrees'}
        global_anchor = (component['bbox'][0] + source_anchor[0], component['bbox'][1] + source_anchor[1])
        top, left = global_anchor[0] - target_anchor[0], global_anchor[1] - target_anchor[1]
        for r, c, value in old.scaled_pattern_cells(target, scale, top, left):
            if not (0 <= r < height and 0 <= c < width):
                return None, {'failure': 'placement_out_of_bounds'}
            if (r, c) in proposals:
                if proposals[r, c] != value:
                    return None, {'failure': 'different_color_proposals_overlap'}
                overlaps += 1
            proposals[r, c] = value
        anchor_blocks.append([(global_anchor[0] + dr, global_anchor[1] + dc)
                              for dr in range(scale) for dc in range(scale)])
        placements.append({'source_component': old.component_summary(component), 'scale': scale,
                           'target_top_left': [top, left], 'anchor_global_cell': list(global_anchor)})
    if any(proposals.get(p) != anchor for block in anchor_blocks for p in block):
        return None, {'failure': 'selected_anchor_block_changed'}
    expected = [[proposals.get((r, c), background) for c in range(width)] for r in range(height)]
    output, source_record = old.render_motif_pair_scaled_anchor_swap(grid)
    expected_record = {'background': background, 'anchor_color': anchor,
                       'primitive_group_count': 2, 'component_count': len(components),
                       'primitive_group_sizes': [len(groups[a]), len(groups[b])], 'placements': placements}
    if output is None:
        return None, {'failure': 'source_no_candidate', 'source_record': source_record}
    if output != expected or source_record != expected_record:
        return None, {'failure': 'source_output_or_record_disagrees'}
    return output, {'source_record': source_record, 'certificate': {
        'components': len(components), 'scales': [r['scale'] for r in records],
        'valid_scales': [r['valid_scales'] for r in records], 'anchor_color_counts': anchor_counts,
        'foreground_before': len(foreground), 'foreground_after': len(proposals),
        'same_color_overlapping_proposals': overlaps,
    }}


def fit_guarded(teachers):
    if not teachers or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return False
    if not all(old.render_motif_pair_scaled_anchor_swap(p['input'])[0] == p['output'] for p in teachers):
        return False
    return all(guarded_render(p['input'])[0] == p['output'] for p in teachers)


class 倍率置換教材:
    def __init__(self, 教師群):
        self.適合 = fit_guarded(教師群)
        if self.適合 is False:
            models, record = _fit_complete_frame_no_fit(教師群)
            if models:
                self.枠モデル群, self.枠適合記録 = models, record

    def 候補(self, 格子, _policy):
        if hasattr(self, '枠モデル群'):
            from .多類枠倍率置換 import render
            return render(格子, self.枠モデル群)
        if not self.適合:
            return None, {'failure': '全教師を再現する倍率motif置換なし'}
        return guarded_render(格子)

    def 記録(self):
        if hasattr(self, '枠モデル群'):
            return {'全教師再現': self.適合, '全教師共通枠倍率置換': self.枠適合記録}
        return {'全教師再現': self.適合}


def _fit_complete_frame_no_fit(teachers):
    """Recheck every raw teacher; only recognized structural no-fit enables views."""
    from .凡例集合教材 import valid_grid
    if (not isinstance(teachers, (list, tuple)) or len(teachers) < 2
            or any(not isinstance(pair, dict) or not valid_grid(pair.get('input'))
                   or not valid_grid(pair.get('output')) for pair in teachers)
            or len({tuple(map(tuple, pair['input'])) for pair in teachers}) != len(teachers)):
        return None, None
    # fit_guarded short-circuits. Materialize the complete raw inventory first;
    # a later exception must propagate even if an earlier record is unrecognized.
    raw = [old.render_motif_pair_scaled_anchor_swap(pair['input']) for pair in teachers]
    for output, record in raw:
        if (output is not None or not isinstance(record, dict)
                or set(record) != {'failure', 'primitive_group_count', 'component_count'}
                or record['failure'] != 'primitive_group_count_not_two'
                or type(record['primitive_group_count']) is not int
                or type(record['component_count']) is not int
                or record['component_count'] < 2
                or not 1 <= record['primitive_group_count'] <= record['component_count']
                or record['primitive_group_count'] == 2):
            return None, None
    # Lazy import avoids the strict view -> guarded renderer dependency cycle.
    from .多類枠倍率置換 import fit_teachers
    models, fit_record = fit_teachers(teachers)
    return models, {'complete': True, 'raw_records': [record for _, record in raw],
                    'retained_models': models, 'strict_fit_record': fit_record}
