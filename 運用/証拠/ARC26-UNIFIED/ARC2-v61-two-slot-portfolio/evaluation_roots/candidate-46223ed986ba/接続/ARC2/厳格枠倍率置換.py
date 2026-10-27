"""Frame views over the accepted guarded motif swap and crop operations.

The finite teacher-selected policies choose the atomic-marker or compound-motif
frame, retaining its border or extracting its interior, or restore the complete
input after the same swap. All physical views and unused-color normalizations
are retained. Source support is either unrestricted or requires at least two
agreeing whole exemplars; both policies are tested and all fitting policies
survive. Incomplete views force HOLD; resource/runtime failures propagate.
No dataset, task identity, paths, fixed motif, fixed palette, or file access.
"""
from collections import Counter
from itertools import combinations
from .既存領域転写 import _enclosed_non_wall_regions
from .既存色群関係 import scaffold_legend_bbox, bbox_relation_for_bboxes
from .既存枠計数 import perimeter_cells
from .既存重畳組立 import crop_grid
from .倍率置換教材 import guarded_render
from . import 既存倍率置換 as motif
from .凡例集合教材 import valid_grid

CROPS = (('marker', 'border'), ('marker', 'interior'),
         ('motif', 'border'), ('motif', 'interior'), ('both', 'whole_input'))
MODELS = tuple((support, role, scope) for support in ('any', 'repeated')
               for role, scope in CROPS)


def key(grid):
    return tuple(map(tuple, grid))


def interior(box):
    r0, c0, r1, c1 = box
    return {(r, c) for r in range(r0+1, r1) for c in range(c0+1, c1)}


def frames(grid):
    """Reuse enclosed-region boundary boxes, preserving every modal background."""
    height, width = len(grid), len(grid[0])
    found = {}
    for color in sorted({v for row in grid for v in row}):
        for cells in _enclosed_non_wall_regions(grid, color):
            r0, c0, r1, c1 = scaffold_legend_bbox(set(cells))
            box = (r0-1, c0-1, r1+1, c1+1)
            if not (0 <= box[0] < box[2] < height and 0 <= box[1] < box[3] < width):
                continue
            border = perimeter_cells(box)
            if any(grid[r][c] != color for r, c in border):
                continue
            inside = interior(box)
            counts = Counter(grid[r][c] for r, c in inside)
            maximum = max(counts.values())
            for background, count in sorted(counts.items()):
                if count != maximum:
                    continue
                payload = {(r, c): grid[r][c] for r, c in inside if grid[r][c] != background}
                if not payload:
                    continue
                # Native component extraction runs on the actual interior crop.
                patch = crop_grid(grid, (r0, c0, r1, c1))
                if motif.dominant_background(patch) != background:
                    # A tied alternative is represented using a background-only
                    # normalization canvas, rather than the old color tie-break.
                    choices = sorted(set(range(10)) - set(payload.values()))
                    if not choices:
                        continue
                    sentinel = choices[0]
                    patch = [[payload.get((r, c), sentinel) for c in range(width)]
                             for r in range(height)]
                    if motif.dominant_background(patch) != sentinel:
                        continue
                    offset = (0, 0)
                else:
                    offset = (r0, c0)
                components = motif.extract_motif_components(patch)
                patterns = {motif.compress_pattern(motif.pattern_from_component(c))[1]
                            for c in components}
                if len(patterns) != 1:
                    continue
                pattern = next(iter(patterns))
                size = sum(v is not None for row in pattern for v in row)
                observed = {(r+offset[0], c+offset[1]): v
                            for item in components for r, c, v in item['cells']}
                if observed != payload:
                    raise ValueError('frame_payload_component_ownership_failed')
                found[box, background] = {'bbox': box, 'color': color,
                    'background': background, 'inside': inside, 'payload': payload,
                    'primitive': pattern, 'component_count': len(components),
                    'role': 'marker' if size == 1 else 'motif'}
    return list(found.values())


def _view(grid, first, second, sentinel):
    payload = {**first['payload'], **second['payload']}
    height, width = len(grid), len(grid[0])
    view = [[payload.get((r, c), sentinel) for c in range(width)] for r in range(height)]
    if motif.dominant_background(view) != sentinel:
        return None, {'failure': 'normalized_view_background_unresolved'}
    output, record = guarded_render(view)
    if output is None:
        return None, record
    components = motif.extract_motif_components(view)
    patterns = {motif.compress_pattern(motif.pattern_from_component(c))[1] for c in components}
    if len(patterns) != 2:
        raise ValueError('guarded_swap_primitive_inventory_changed')
    anchor = record['source_record']['anchor_color']
    placements = record['source_record']['placements']
    if len(placements) != len(components):
        raise ValueError('guarded_swap_component_inventory_changed')
    for component, placement in zip(components, placements):
        owners = [f for f in (first, second)
                  if {(r, c) for r, c, _ in component['cells']} <= f['inside']]
        if len(owners) != 1:
            raise ValueError('normalized_component_owner_unresolved')
        scale, primitive = motif.compress_pattern(motif.pattern_from_component(component))
        replacement = next(p for p in patterns if p != primitive)
        top, left = placement['target_top_left']
        writes = motif.scaled_pattern_cells(replacement, scale, top, left)
        if any((r, c) not in owners[0]['inside'] for r, c, _ in writes):
            return None, {'failure': 'swap_crosses_owning_frame', 'placement': placement}
    restored = [row[:] for row in grid]
    for frame in (first, second):
        for r, c in frame['inside']:
            restored[r][c] = frame['background'] if output[r][c] == sentinel else output[r][c]
    return restored, record


def enumerate_outputs(grid):
    outputs = {model: set() for model in MODELS}
    record = {'views': [], 'unresolved': [], 'frames': [], 'complete': True}
    if not valid_grid(grid):
        return outputs, {**record, 'failure': 'invalid_grid', 'complete': False}
    inventory = frames(grid)
    record['frames'] = [{k: f[k] for k in ('bbox', 'color', 'background', 'role', 'component_count')}
                        for f in inventory]
    for first, second in combinations(inventory, 2):
        if (first['role'] == second['role']
                or not bbox_relation_for_bboxes(first['bbox'], second['bbox']).disjoint):
            continue
        # The accepted swap requires a common anchor color. An atomic marker
        # supplies exactly one, so there is no anchor tie to resolve by color.
        if not (motif.pattern_colors(first['primitive']) & motif.pattern_colors(second['primitive'])):
            continue
        choices = sorted(set(range(10)) - set(first['payload'].values()) - set(second['payload'].values()))
        pair_record = {'frames': [first['bbox'], second['bbox']], 'normalizations': []}
        record['views'].append(pair_record)
        if not choices:
            record['unresolved'].append({'frames': pair_record['frames'],
                                         'failure': 'no_background_normalization_color'})
        for sentinel in choices:
            restored, detail = _view(grid, first, second, sentinel)
            attempt = {'sentinel': sentinel, 'record': detail}
            pair_record['normalizations'].append(attempt)
            if restored is None:
                record['unresolved'].append({'frames': pair_record['frames'], **attempt})
                continue
            roles = {f['role']: f for f in (first, second)}
            for model in MODELS:
                support, role, scope = model
                if support == 'repeated' and roles['motif']['component_count'] < 2:
                    continue
                if scope == 'whole_input':
                    candidate = restored
                else:
                    box = roles[role]['bbox']
                    if scope == 'interior':
                        box = (box[0]+1, box[1]+1, box[2]-1, box[3]-1)
                    candidate = crop_grid(restored, box)
                outputs[model].add(key(candidate))
    record['complete'] = not record['unresolved']
    record['output_counts'] = {str(m): len(v) for m, v in outputs.items()}
    record['full_grid_alternatives'] = [{'model': m, 'outputs': sorted(values)}
                                        for m, values in outputs.items()]
    return outputs, record


def fit_teachers(pairs):
    if (not isinstance(pairs, (list, tuple)) or len(pairs) < 2
            or any(not isinstance(p, dict) or not valid_grid(p.get('input'))
                   or not valid_grid(p.get('output')) for p in pairs)
            or len({key(p['input']) for p in pairs}) < 2):
        return None, {'failure': 'invalid_or_insufficient_teachers'}
    enumerated = [enumerate_outputs(p['input']) for p in pairs]
    record = {'teachers': [r for _, r in enumerated]}
    if any(not r['complete'] for _, r in enumerated):
        return None, {**record, 'failure': 'teacher_view_unresolved'}
    models = tuple(m for m in MODELS if all(outs[m] == {key(p['output'])}
                   for p, (outs, _) in zip(pairs, enumerated)))
    record['retained_models'] = models
    if not models:
        return None, {**record, 'failure': 'no_teacher_compatible_composition'}
    return models, record


def render(grid, models):
    if (not isinstance(models, (tuple, list)) or not models
            or any(tuple(m) not in MODELS for m in models)
            or len({tuple(m) for m in models}) != len(models)):
        return None, {'failure': 'invalid_models'}
    outputs, record = enumerate_outputs(grid)
    if not record['complete']:
        return None, {**record, 'failure': 'retained_view_unresolved'}
    if any(not outputs[tuple(m)] for m in models):
        return None, {**record, 'failure': 'retained_model_has_no_output'}
    alternatives = set().union(*(outputs[tuple(m)] for m in models))
    record['full_grid_count'] = len(alternatives)
    if len(alternatives) != 1:
        return None, {**record, 'failure': 'retained_full_grids_disagree'}
    return [list(row) for row in next(iter(alternatives))], record
