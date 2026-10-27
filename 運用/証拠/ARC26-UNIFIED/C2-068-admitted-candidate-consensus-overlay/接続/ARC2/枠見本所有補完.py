"""Input-only composition of accepted frame, mask, palette and crop operations.

This is a proposed view for the existing partial-panel exemplar family. It has
no task identifiers, fixed colors, dimensions, glyphs, or output grids. The finite
program space is D4 mask orientation x mask polarity x palette identity/pair.
Every program reproducing every teacher is retained; a query requires full-grid
agreement from all retained programs. Exceptions propagate to the caller.

Duplicate per-key glyphs and palette records remain physical alternatives; no
component is selected by order or teacher output. Every full assignment must
resolve and agree. Glyph masks own exactly their extracted component cells.
"""
from collections import Counter
from itertools import product

from 接続.ARC2.既存配置展開 import crop_bbox
from 接続.ARC2.既存枠計数 import foreground_components, is_rectangular_frame
from 接続.ARC2.既存領域転写 import mixed_region_dicts_for_grid, bbox_shape_for_bbox
from 接続.ARC2.既存色群関係 import bbox_relation_for_bboxes, scaffold_legend_bbox
from 接続.ARC2.既存二値原型 import binary_template_from_grid, colorize_binary_template
from 接続.ARC2.既存格子操作 import transform_grid_by_name
from 接続.ARC2.凡例集合教材 import valid_grid

TRANSFORMS = ('identity', 'rot90', 'rot180', 'rot270',
              'flip_h', 'flip_v', 'transpose', 'anti_transpose')
PROGRAMS = tuple(product(TRANSFORMS, ('keep', 'erase'), ('identity', 'paired')))


def observe(grid, *, complete_legend_ownership=False):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    counts = Counter(v for row in grid for v in row)
    backgrounds = [v for v, count in counts.items() if count == max(counts.values())]
    if len(backgrounds) != 1:
        return None, {'failure': 'background_tie'}
    bg = backgrounds[0]
    components = foreground_components(grid, bg)
    frames = [component for component in components if is_rectangular_frame(component)]
    if len(frames) != 1:
        return None, {'failure': 'frame_not_unique', 'frame_count': len(frames)}
    frame = frames[0]
    mixed = mixed_region_dicts_for_grid(grid, bg, include_diagonal=False)
    owned = [cell for component in mixed for cell in component['cells']]
    foreground = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != bg}
    if set(owned) != foreground or len(owned) != len(foreground):
        raise ValueError('accepted_component_ownership_failed')
    slots, outside = [], []
    frame_owned = 0
    for component in mixed:
        if set(component['cells']) == frame['cells']:
            frame_owned += 1
            continue
        relation = bbox_relation_for_bboxes(frame['bbox'], component['bbox'])
        if relation.first_strictly_contains_second:
            height, width = bbox_shape_for_bbox(component['bbox'])
            if len(component['colors']) != 1 or len(component['cells']) != height * width:
                return None, {'failure': 'slot_not_filled_monochrome_rectangle'}
            slots.append(component)
        elif relation.disjoint:
            outside.append(component)
        else:
            return None, {'failure': 'foreground_crosses_frame'}
    if frame_owned != 1 or not slots:
        return None, {'failure': 'missing_frame_or_slots'}
    key_colors = {component['colors'][0] for component in slots}
    glyphs = [component for component in outside if len(component['colors']) == 1]
    legends = [component for component in outside if len(component['colors']) == 2]
    if len(glyphs) + len(legends) != len(outside):
        return None, {'failure': 'outside_component_has_no_role'}
    glyph_by_color = {color: [] for color in key_colors}
    for glyph in glyphs:
        color = glyph['colors'][0]
        if color not in key_colors:
            return None, {'failure': 'glyph_key_unresolved'}
        glyph_by_color[color].append(glyph)
    legends_by_color = {color: [] for color in key_colors}
    eligible_sources = []
    for legend in legends:
        sources = key_colors & set(legend['colors'])
        height, width = bbox_shape_for_bbox(legend['bbox'])
        if (not sources or len(legend['cells']) != height * width
                or (not complete_legend_ownership and len(sources) != 1)):
            return None, {'failure': 'legend_not_bicolor_rectangular_pair'}
        eligible_sources.append(tuple(sorted(sources)))
        if len(sources) == 1:
            source = next(iter(sources))
            legends_by_color[source].append({
                'color': next(iter(set(legend['colors']) - {source})),
                'bbox': list(legend['bbox']), 'cells': sorted(legend['cells'])})
    ownerships = []
    if complete_legend_ownership:
        # Only complete the old rejection of a filled card with two key colors.
        # Every physical card has one owner; keys may own multiple cards.
        if not any(len(sources) == 2 for sources in eligible_sources):
            return None, {'failure': 'legend_key_ambiguity_absent'}
        for owners in product(*eligible_sources):
            if set(owners) != key_colors:
                continue
            assigned = {color: [] for color in key_colors}
            for legend, source in zip(legends, owners):
                assigned[source].append({
                    'color': next(iter(set(legend['colors']) - {source})),
                    'bbox': list(legend['bbox']), 'cells': sorted(legend['cells'])})
            ownerships.append({'owners': list(owners), 'legends': assigned})
        if not ownerships:
            return None, {'failure': 'incomplete_color_relation'}
    if any(not glyph_by_color[color] or (not complete_legend_ownership
               and not legends_by_color[color]) for color in key_colors):
        return None, {'failure': 'incomplete_color_relation'}
    masks = {}
    for source, components in glyph_by_color.items():
        masks[source] = []
        for glyph in components:
            row0, col0, _, _ = glyph['bbox']
            height, width = bbox_shape_for_bbox(glyph['bbox'])
            exact = [[bg] * width for _ in range(height)]
            for row, col in glyph['cells']:
                exact[row - row0][col - col0] = source
            mask = binary_template_from_grid(exact, bg)
            if sum(sum(row) for row in mask) != len(glyph['cells']):
                raise ValueError('glyph_component_mask_ownership_failed')
            masks[source].append({'mask': mask, 'bbox': list(glyph['bbox']),
                                  'cells': sorted(glyph['cells'])})
    if complete_legend_ownership:
        return {'background': bg, 'frame': frame, 'slots': slots,
                'masks': masks, 'legend_ownerships': ownerships}, {
                    'background': bg, 'frame_bbox': list(frame['bbox']),
                    'slot_count': len(slots), 'glyph_count': len(glyphs),
                    'legend_count': len(legends),
                    'glyph_alternatives': {color: len(values) for color, values in masks.items()},
                    'eligible_legend_sources': [list(values) for values in eligible_sources],
                    'legend_ownership_count': len(ownerships),
                    'legend_owners': [entry['owners'] for entry in ownerships],
                    'foreground_cells': len(owned)}
    return {'background': bg, 'frame': frame, 'slots': slots,
            'masks': masks, 'legends': legends_by_color}, {
                'background': bg, 'frame_bbox': list(frame['bbox']),
                'slot_count': len(slots), 'glyph_count': len(glyphs),
                'legend_count': len(legends),
                'glyph_alternatives': {color: len(values) for color, values in masks.items()},
                'palette_alternatives': {color: [entry['color'] for entry in values]
                                         for color, values in legends_by_color.items()},
                'foreground_cells': len(owned)}


def render_assignment(grid, observed, program, assignment):
    if tuple(program) not in PROGRAMS:
        return None, {'failure': 'unknown_program'}
    transform, polarity, palette = program
    bg = observed['background']
    frame = observed['frame']
    out = crop_bbox(grid, frame['bbox'])
    before = [row[:] for row in out]
    fr, fc, _, _ = frame['bbox']
    changed_region = set()
    placements = []
    for slot in observed['slots']:
        source = slot['colors'][0]
        glyph, legend = assignment[source]
        mask = transform_grid_by_name(glyph['mask'], transform)
        if mask is None:
            raise ValueError('accepted_transform_missing')
        if (len(mask), len(mask[0])) != bbox_shape_for_bbox(slot['bbox']):
            return None, {'failure': 'transformed_glyph_does_not_fit_slot'}
        if polarity == 'erase':
            mask = [[1 - value for value in row] for row in mask]
        color = source if palette == 'identity' else legend['color']
        tile = colorize_binary_template(mask, bg, color)
        sr, sc, _, _ = slot['bbox']
        for r, row in enumerate(tile):
            for c, value in enumerate(row):
                cell = (sr - fr + r, sc - fc + c)
                if cell in changed_region:
                    raise ValueError('slot_ownership_overlap')
                changed_region.add(cell)
                out[cell[0]][cell[1]] = value
        placements.append({'source_color': source, 'output_color': color,
                           'slot_bbox': list(slot['bbox']),
                           'glyph_bbox': glyph['bbox'], 'legend_bbox': legend['bbox']})
    if any(value != before[r][c] for r, row in enumerate(out)
           for c, value in enumerate(row) if (r, c) not in changed_region):
        raise ValueError('crop_context_changed')
    return out, {'program': list(program), 'placements': placements,
                 'slot_cells': len(changed_region), 'output_shape': [len(out), len(out[0])]}


def render_observed(grid, observed, program):
    if tuple(program) not in PROGRAMS:
        return None, {'failure': 'unknown_program'}
    if 'legend_ownerships' in observed:
        return render_legend_ownerships(grid, observed, program)
    keys = sorted(observed['masks'])
    choices = [tuple(product(observed['masks'][color], observed['legends'][color]))
               for color in keys]
    outputs, records = [], []
    for alternatives in product(*choices):
        assignment = dict(zip(keys, alternatives))
        output, record = render_assignment(grid, observed, program, assignment)
        outputs.append(output)
        records.append(record)
    summary = {'program': list(program), 'assignment_count': len(outputs),
               'assignments': records}
    if not outputs:
        return None, {**summary, 'failure': 'no_complete_role_assignment'}
    if any(output is None for output in outputs):
        return None, {**summary, 'failure': 'physical_assignment_unresolved'}
    if any(output != outputs[0] for output in outputs[1:]):
        return None, {**summary, 'failure': 'physical_assignment_grids_disagree'}
    return outputs[0], summary


def render_legend_ownerships(grid, observed, program):
    outputs, records = [], []
    for ownership in observed['legend_ownerships']:
        local = {key: value for key, value in observed.items() if key != 'legend_ownerships'}
        local['legends'] = ownership['legends']
        output, record = render_observed(grid, local, program)
        outputs.append(output)
        records.append({'owners': ownership['owners'], 'execution': record})
    summary = {'program': list(program), 'legend_ownership_count': len(outputs),
               'assignment_count': sum(entry['execution']['assignment_count'] for entry in records),
               'ownerships': records}
    if not outputs:
        return None, {**summary, 'failure': 'no_complete_legend_ownership'}
    if any(output is None for output in outputs):
        return None, {**summary, 'failure': 'legend_ownership_unresolved'}
    if any(output != outputs[0] for output in outputs[1:]):
        return None, {**summary, 'failure': 'legend_ownership_grids_disagree'}
    return outputs[0], summary


def render_strict111(grid, models):
    observed, record = observe(grid)
    if observed is None and record.get('failure') == 'legend_not_bicolor_rectangular_pair':
        completed, completion_record = observe(grid, complete_legend_ownership=True)
        if completed is not None:
            observed, record = completed, completion_record
    if observed is None:
        return None, record
    if not models:
        return None, {'failure': 'no_retained_programs'}
    outputs, executions = [], []
    for model in models:
        output, execution = render_observed(grid, observed, model)
        executions.append(execution)
        outputs.append(output)
    if any(output is None for output in outputs):
        return None, {**record, 'failure': 'retained_program_unresolved',
                      'executions': executions}
    if any(output != outputs[0] for output in outputs[1:]):
        return None, {**record, 'failure': 'retained_program_grids_disagree',
                      'executions': executions}
    return outputs[0], {**record, 'retained_program_count': len(models),
                        'executions': executions}


def fit_teachers(teachers):
    if (not isinstance(teachers, (list, tuple)) or len(teachers) < 2
            or any(not isinstance(pair, dict) or not valid_grid(pair.get('input'))
                   or not valid_grid(pair.get('output')) for pair in teachers)):
        return None, {'failure': 'invalid_teachers', 'complete': True}
    if len({tuple(map(tuple, pair['input'])) for pair in teachers}) != len(teachers):
        return None, {'failure': 'duplicate_teacher_inputs', 'complete': True}
    observations = [observe(pair['input']) for pair in teachers]
    if any(observed is None for observed, _ in observations):
        return None, {'failure': 'teacher_input_contract', 'complete': True,
                      'observations': [record for _, record in observations]}
    models, trials = [], []
    for program in PROGRAMS:
        fits = []
        for pair, (observed, _) in zip(teachers, observations):
            output, _ = render_observed(pair['input'], observed, program)
            fits.append(output == pair['output'])
        trials.append({'program': list(program), 'teacher_fits': fits})
        if all(fits):
            models.append(program)
    record = {'complete': True, 'program_count': len(PROGRAMS),
              'retained_program_count': len(models), 'trials': trials,
              'observations': [record for _, record in observations]}
    if not models:
        return None, {**record, 'failure': 'no_shared_program'}
    for pair in teachers:
        output, _ = render(pair['input'], models)
        if output != pair['output']:
            raise ValueError('teacher_consensus_invariant_failed')
    return models, record


def incomplete_glyph_size_only(record):
    failures = []
    def visit(value):
        if isinstance(value, dict):
            if 'failure' in value:
                failures.append(value['failure'])
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
    visit(record)
    return ('transformed_glyph_does_not_fit_slot' in failures
            and set(failures) <= {'retained_program_unresolved',
                'legend_ownership_unresolved', 'physical_assignment_unresolved',
                'transformed_glyph_does_not_fit_slot'})


def complete_glyph_partitions(grid, observed):
    """Every tight slot-shape window and exact partition of original glyphs."""
    bg = observed['background']
    per_key, records = {}, {}
    for color, glyphs in observed['masks'].items():
        shapes = set()
        for slot in observed['slots']:
            if slot['colors'][0] == color:
                height, width = bbox_shape_for_bbox(slot['bbox'])
                shapes.update(((height, width), (width, height)))
        supports = [set(map(tuple, glyph['cells'])) for glyph in glyphs]
        candidates = []
        for height, width in sorted(shapes):
            for row0 in range(len(grid) - height + 1):
                for col0 in range(len(grid[0]) - width + 1):
                    bbox = (row0, col0, row0 + height - 1, col0 + width - 1)
                    window = {(r, c) for r in range(row0, row0 + height)
                              for c in range(col0, col0 + width)}
                    members, cells = [], set()
                    for index, (glyph, support) in enumerate(zip(glyphs, supports)):
                        if not support & window:
                            continue
                        if not bbox_relation_for_bboxes(bbox, tuple(glyph['bbox'])).first_contains_second:
                            break
                        members.append(index)
                        cells.update(support)
                    else:
                        if not cells or scaffold_legend_bbox(cells) != bbox:
                            continue
                        foreground = {(r, c) for r, c in window if grid[r][c] != bg}
                        if foreground != cells:
                            continue
                        exact = [[bg] * width for _ in range(height)]
                        for r, c in cells:
                            exact[r - row0][c - col0] = color
                        mask = binary_template_from_grid(exact, bg)
                        if sum(sum(row) for row in mask) != len(cells):
                            raise ValueError('glyph_window_mask_ownership_failed')
                        candidates.append({'mask': mask, 'bbox': list(bbox),
                                           'cells': sorted(cells), 'components': members})
        partitions = []
        def visit(remaining, selected):
            if not remaining:
                partitions.append(list(selected))
                return
            first = min(remaining)
            for candidate in candidates:
                members = set(candidate['components'])
                if first in members and members <= remaining:
                    visit(remaining - members, selected + [candidate])
        visit(set(range(len(glyphs))), [])
        per_key[color] = partitions
        records[color] = {'original_component_count': len(glyphs),
                          'window_count': len(candidates), 'windows': candidates,
                          'partition_count': len(partitions),
                          'partitions': [[window['components'] for window in partition]
                                         for partition in partitions]}
    keys = sorted(per_key)
    complete = [dict(zip(keys, values))
                for values in product(*(per_key[key] for key in keys))]
    return complete, records


def render_complete_glyph_windows(grid, observed, models, strict_record):
    partitions, partition_record = complete_glyph_partitions(grid, observed)
    if not partitions:
        return None, strict_record
    outputs, records = [], []
    for partition in partitions:
        local = {**observed, 'masks': partition}
        executions = []
        for model in models:
            output, execution = render_observed(grid, local, model)
            outputs.append(output)
            executions.append(execution)
        records.append({'glyph_windows': partition, 'executions': executions})
    summary = {'strict111': strict_record, 'glyph_window_partitions': partition_record,
               'complete_partition_count': len(partitions),
               'retained_program_count': len(models), 'partitions': records}
    if any(output is None for output in outputs):
        return None, {**summary, 'failure': 'complete_glyph_partition_unresolved'}
    if any(output != outputs[0] for output in outputs[1:]):
        return None, {**summary, 'failure': 'complete_glyph_partition_grids_disagree'}
    return outputs[0], summary


def render(grid, models):
    output, record = render_strict111(grid, models)
    if output is not None or not incomplete_glyph_size_only(record):
        return output, record
    observed, observation = observe(grid)
    if observed is None and observation.get('failure') == 'legend_not_bicolor_rectangular_pair':
        observed, observation = observe(grid, complete_legend_ownership=True)
    if observed is None:
        return None, record
    return render_complete_glyph_windows(grid, observed, models, record)
