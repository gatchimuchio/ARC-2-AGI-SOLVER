"""Compose complete classes through strict081's guarded frame swap.

The teacher fitter and policy objects are the frozen strict081 objects. Only a
complete structural zero-view result can enter this prospective input grammar:
one frame has at least two atomic primitive classes; another disjoint frame has
the same number of compound classes. Every native component belongs to exactly
one class and every class participates in a complete anchor-compatible bijection.
All bijections and unused-color normalizations survive to output consensus.
Each class reads the original input through strict081._view; certified writes are
combined simultaneously, with the same equal-color overlap rule as the guard.
"""
from collections import Counter
from itertools import combinations
from . import 厳格枠倍率置換 as strict

MODELS = strict.MODELS
CROPS = strict.CROPS
fit_teachers = strict.fit_teachers
motif = strict.motif


def multiclass_frames(grid):
    """The strict081 frame geometry, retaining all native primitive classes."""
    height, width = len(grid), len(grid[0])
    found = {}
    for color in sorted({v for row in grid for v in row}):
        for cells in strict._enclosed_non_wall_regions(grid, color):
            r0, c0, r1, c1 = strict.scaffold_legend_bbox(set(cells))
            box = (r0 - 1, c0 - 1, r1 + 1, c1 + 1)
            if not (0 <= box[0] < box[2] < height and 0 <= box[1] < box[3] < width):
                continue
            if any(grid[r][c] != color for r, c in strict.perimeter_cells(box)):
                continue
            inside = strict.interior(box)
            counts = Counter(grid[r][c] for r, c in inside)
            maximum = max(counts.values())
            for background, count in sorted(counts.items()):
                if count != maximum:
                    continue
                payload = {(r, c): grid[r][c] for r, c in inside
                           if grid[r][c] != background}
                if not payload:
                    continue
                patch = strict.crop_grid(grid, (r0, c0, r1, c1))
                offset = (r0, c0)
                if motif.dominant_background(patch) != background:
                    choices = sorted(set(range(10)) - set(payload.values()))
                    if not choices:
                        continue
                    sentinel = choices[0]
                    patch = [[payload.get((r, c), sentinel) for c in range(width)]
                             for r in range(height)]
                    if motif.dominant_background(patch) != sentinel:
                        continue
                    offset = (0, 0)
                groups, observed = {}, {}
                for component in motif.extract_motif_components(patch):
                    scale, primitive = motif.compress_pattern(motif.pattern_from_component(component))
                    cells = {(r + offset[0], c + offset[1]): value
                             for r, c, value in component['cells']}
                    if set(cells) & set(observed):
                        raise ValueError('multiclass_component_ownership_overlap')
                    observed.update(cells)
                    group = groups.setdefault(primitive, {'primitive': primitive,
                        'payload': {}, 'component_count': 0})
                    group['payload'].update(cells)
                    group['component_count'] += 1
                if observed != payload:
                    raise ValueError('multiclass_frame_payload_ownership_failed')
                if len(groups) < 2:
                    continue
                sizes = {sum(v is not None for row in primitive for v in row)
                         for primitive in groups}
                if sizes == {1}:
                    role = 'marker'
                elif min(sizes) > 1:
                    role = 'motif'
                else:
                    continue
                frame = {'bbox': box, 'color': color, 'background': background,
                         'inside': inside, 'payload': payload, 'role': role,
                         'component_count': sum(g['component_count'] for g in groups.values())}
                frame['classes'] = [{**frame, **groups[primitive]}
                                    for primitive in sorted(groups, key=repr)]
                found[box, background] = frame
    return list(found.values())


def class_matchings(marker, exemplar):
    """Enumerate every complete one-to-one matching, without ranking anchors."""
    markers, glyphs = marker['classes'], exemplar['classes']
    if len(markers) != len(glyphs):
        return
    def visit(index, unused, pairs):
        if index == len(markers):
            yield tuple(pairs)
            return
        atom = markers[index]
        for j in sorted(unused):
            if motif.pattern_colors(atom['primitive']) & motif.pattern_colors(glyphs[j]['primitive']):
                yield from visit(index + 1, unused - {j}, pairs + [(atom, glyphs[j])])
    yield from visit(0, set(range(len(glyphs))), [])


def _compose(grid, marker, exemplar, matching, sentinel):
    writes, details, owned = {}, [], set()
    for atom, glyph in matching:
        class_payload = {**atom['payload'], **glyph['payload']}
        if set(class_payload) & owned:
            raise ValueError('multiclass_class_ownership_overlap')
        owned.update(class_payload)
        # This is the original certified renderer, including owning-frame checks.
        # It always reads grid, never the output of an earlier class action.
        restored, detail = strict._view(grid, atom, glyph, sentinel)
        details.append(detail)
        if restored is None:
            return None, {'failure': 'class_view_unresolved', 'classes': details}
        view = [[class_payload.get((r, c), sentinel) for c in range(len(grid[0]))]
                for r in range(len(grid))]
        components = motif.extract_motif_components(view)
        placements = detail['source_record']['placements']
        if len(components) != atom['component_count'] + glyph['component_count']:
            raise ValueError('multiclass_native_component_partition_changed')
        for component, placement in zip(components, placements):
            scale, primitive = motif.compress_pattern(motif.pattern_from_component(component))
            owners = [part for part in (atom, glyph)
                      if {(r, c): value for r, c, value in component['cells']}.items()
                      <= part['payload'].items()]
            if len(owners) != 1 or primitive != owners[0]['primitive']:
                raise ValueError('multiclass_native_class_owner_unresolved')
            target = glyph['primitive'] if owners[0] is atom else atom['primitive']
            top, left = placement['target_top_left']
            # Recover explicit support from the accepted placement helper, then
            # take values from the actual guarded rendering, including bg colors.
            for r, c, value in motif.scaled_pattern_cells(target, scale, top, left):
                if restored[r][c] != value:
                    raise ValueError('multiclass_guarded_value_disagrees')
                if (r, c) in writes and writes[r, c] != restored[r][c]:
                    return None, {'failure': 'different_class_proposals_overlap',
                                  'cell': [r, c], 'classes': details}
                writes[r, c] = restored[r][c]
    if owned != set(marker['payload']) | set(exemplar['payload']):
        raise ValueError('multiclass_complete_frame_ownership_failed')
    restored = [row[:] for row in grid]
    for frame in (marker, exemplar):
        for r, c in frame['inside']:
            restored[r][c] = writes.get((r, c), frame['background'])
    return restored, {'classes': details, 'owned_cells': len(owned), 'write_cells': len(writes)}


def enumerate_multiclass_outputs(grid):
    outputs = {model: set() for model in MODELS}
    record = {'views': [], 'unresolved': [], 'frames': [], 'rejected_pairs': [], 'complete': True,
              'composition': 'complete_multiclass_guarded_frame_swap'}
    if not strict.valid_grid(grid):
        return outputs, {**record, 'failure': 'invalid_grid', 'complete': False}
    inventory = multiclass_frames(grid)
    record['frames'] = [{**{k: f[k] for k in ('bbox', 'color', 'background', 'role', 'component_count')},
                         'class_count': len(f['classes'])} for f in inventory]
    for first, second in combinations(inventory, 2):
        if first['role'] == second['role'] or not strict.bbox_relation_for_bboxes(first['bbox'], second['bbox']).disjoint:
            continue
        roles = {f['role']: f for f in (first, second)}
        marker, exemplar = roles['marker'], roles['motif']
        matchings = list(class_matchings(marker, exemplar))
        # A wholly unrelated pair is outside this grammar, as in strict081.
        if not any(motif.pattern_colors(a['primitive']) & motif.pattern_colors(b['primitive'])
                   for a in marker['classes'] for b in exemplar['classes']):
            continue
        pair_record = {'frames': [first['bbox'], second['bbox']],
                       'matching_count': len(matchings), 'normalizations': []}
        if not matchings:
            record['rejected_pairs'].append({'frames': pair_record['frames'],
                                            'failure': 'no_complete_class_matching'})
            continue
        record['views'].append(pair_record)
        choices = sorted(set(range(10)) - set(first['payload'].values()) - set(second['payload'].values()))
        if not choices:
            record['unresolved'].append({'frames': pair_record['frames'],
                                         'failure': 'no_background_normalization_color'})
        for matching in matchings:
            mapping = [{'marker': a['primitive'], 'glyph': b['primitive']} for a, b in matching]
            for sentinel in choices:
                restored, detail = _compose(grid, marker, exemplar, matching, sentinel)
                attempt = {'sentinel': sentinel, 'mapping': mapping, 'record': detail}
                pair_record['normalizations'].append(attempt)
                if restored is None:
                    record['unresolved'].append({'frames': pair_record['frames'], **attempt})
                    continue
                for model in MODELS:
                    support, role, scope = model
                    if support == 'repeated' and any(g['component_count'] < 2 for g in exemplar['classes']):
                        continue
                    if scope == 'whole_input':
                        candidate = restored
                    else:
                        box = roles[role]['bbox']
                        if scope == 'interior':
                            box = (box[0] + 1, box[1] + 1, box[2] - 1, box[3] - 1)
                        candidate = strict.crop_grid(restored, box)
                    outputs[model].add(strict.key(candidate))
    record['complete'] = not record['unresolved']
    record['output_counts'] = {str(m): len(v) for m, v in outputs.items()}
    record['full_grid_alternatives'] = [{'model': m, 'outputs': sorted(values)}
                                      for m, values in outputs.items()]
    return outputs, record


def _zero_view_gap(record):
    return (record.get('complete') is True and record.get('views') == []
            and bool(record.get('output_counts'))
            and all(n == 0 for n in record['output_counts'].values()))


def enumerate_outputs(grid):
    outputs, record = strict.enumerate_outputs(grid)
    if not _zero_view_gap(record):
        return outputs, record
    return enumerate_multiclass_outputs(grid)


def render(grid, models):
    output, original_record = strict.render(grid, models)
    if not _zero_view_gap(original_record):
        return output, original_record
    outputs, record = enumerate_multiclass_outputs(grid)
    record['strict_zero_view_record'] = original_record
    if not record['complete']:
        return None, {**record, 'failure': 'retained_view_unresolved'}
    if any(not outputs[tuple(m)] for m in models):
        return None, {**record, 'failure': 'retained_model_has_no_output'}
    alternatives = set().union(*(outputs[tuple(m)] for m in models))
    record['full_grid_count'] = len(alternatives)
    if len(alternatives) != 1:
        return None, {**record, 'failure': 'retained_full_grids_disagree'}
    return [list(row) for row in next(iter(alternatives))], record
