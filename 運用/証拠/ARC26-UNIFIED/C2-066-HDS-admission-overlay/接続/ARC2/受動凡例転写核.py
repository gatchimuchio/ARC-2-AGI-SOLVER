"""Input-owned keyed stamps with explicit passive-cell preservation prior.
Reuses the old C8/bbox-edge/code parser and simultaneous clipped renderer.
All teacher-fit background models survive. Partial roles are fully inventoried;
background rules are applied before rendering, never from output success.
The three background heuristics and identity outside owned edits are additional
priors, not logical consequences of the four observed teacher pairs.
"""

from collections import Counter, defaultdict

def cells(points):
    return [list(p) for p in sorted(points)]

def box(points):
    return [min(r for r, _ in points), min(c for _, c in points),
            max(r for r, _ in points), max(c for _, c in points)]

def components(points, diagonal):
    todo = set(points)
    result = []
    steps = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
             if (dr or dc) and (diagonal or not (dr and dc))]
    while todo:
        root = min(todo)
        todo.remove(root)
        part = {root}
        stack = [root]
        while stack:
            r, c = stack.pop()
            for dr, dc in steps:
                q = r + dr, c + dc
                if q in todo:
                    todo.remove(q)
                    part.add(q)
                    stack.append(q)
        result.append(part)
    return result


def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30
            and type(grid[0]) is list and 1 <= len(grid[0]) <= 30
            and all(type(row) is list and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))


def colour_prefix(grid, colour):
    height, width = len(grid), len(grid[0])
    prefix = [[0] * (width + 1) for _ in range(height + 1)]
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            prefix[r + 1][c + 1] = (prefix[r][c + 1] + prefix[r + 1][c]
                                      - prefix[r][c] + (value == colour))
    return prefix


def rectangle_count(prefix, bounds):
    top, left, bottom, right = bounds
    return (prefix[bottom + 1][right + 1] - prefix[top][right + 1]
            - prefix[bottom + 1][left] + prefix[top][left])


def diagnostic_bitmap(points, width):
    bits = 0
    for r, c in points:
        bits |= 1 << (r * width + c)
    return hex(bits)


def parse_input(grid, background_rule):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    height, width = len(grid), len(grid[0])
    palette = sorted({v for row in grid for v in row})
    supports = {colour: {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v == colour}
                for colour in palette}
    groups = {colour: components(supports[colour], True) for colour in palette}
    prefixes = {colour: colour_prefix(grid, colour) for colour in palette}
    bounds = {colour: [box(part) for part in groups[colour]] for colour in palette}
    records, complete_roles = [], []
    ray_visits = 0
    for background in palette:
        foreground = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != background}
        for shape_colour in palette:
            if shape_colour == background:
                continue
            parts = groups[shape_colour]
            dictionaries, per_part, foreign_counts = [], [], []
            for component, part in enumerate(parts):
                top, left, bottom, right = bounds[shape_colour][component]
                boundary = ([((top, c), (-1, 0)) for c in range(left, right + 1)]
                            + [((bottom, c), (1, 0)) for c in range(left, right + 1)]
                            + [((r, left), (0, -1)) for r in range(top, bottom + 1)]
                            + [((r, right), (0, 1)) for r in range(top, bottom + 1)])
                foreign = ((bottom - top + 1) * (right - left + 1)
                           - rectangle_count(prefixes[background], (top, left, bottom, right)) - len(part))
                foreign_counts.append(foreign)
                raw_ids = []
                for anchor, outward in boundary:
                    ray_visits += 1
                    r, c = anchor; dr, dc = outward
                    value_cell, key_cell = (r + dr, c + dc), (r + 2 * dr, c + 2 * dc)
                    if not all(0 <= y < height and 0 <= x < width for y, x in (value_cell, key_cell)):
                        continue
                    value, key = grid[value_cell[0]][value_cell[1]], grid[key_cell[0]][key_cell[1]]
                    if value == key or value in (background, shape_colour) or key in (background, shape_colour):
                        continue
                    raw_id = len(dictionaries)
                    dictionaries.append({'raw_id': raw_id, 'component': component,
                                         'anchor': list(anchor), 'outward': list(outward),
                                         'key_cell': list(key_cell), 'value_cell': list(value_cell),
                                         'key': key, 'value': value,
                                         'anchor_in_own_support': anchor in part,
                                         'anchor_is_background': grid[r][c] == background,
                                         'bbox_foreign_foreground_count': foreign})
                    raw_ids.append(raw_id)
                per_part.append(raw_ids)
            active_shapes = set().union(*(parts[i] for i, ids in enumerate(per_part) if ids)) if any(per_part) else set()
            code_counter = Counter(tuple(d[field]) for d in dictionaries for field in ('key_cell', 'value_cell'))
            dictionary_union = active_shapes | set(code_counter)
            keys = Counter(d['key'] for d in dictionaries)
            remaining = sorted(foreground - dictionary_union)
            flags = {
                'every_shape_component_has_one_raw_ray': all(len(ids) == 1 for ids in per_part),
                'all_shape_pixels_in_raw_dictionary_union': supports[shape_colour] <= dictionary_union,
                'raw_dictionary_cell_ownership_disjoint': (all(len(ids) <= 1 for ids in per_part)
                    and all(count == 1 for count in code_counter.values())
                    and not (active_shapes & set(code_counter))),
                'distinct_raw_key_colors': len(keys) == len(dictionaries),
                'every_remaining_foreground_cell_has_one_raw_key_match': all(keys[grid[r][c]] == 1 for r, c in remaining),
                'every_raw_anchor_is_shape_or_background': all(d['anchor_in_own_support'] or d['anchor_is_background'] for d in dictionaries),
                'no_other_foreground_inside_raw_shape_bboxes': all(d['bbox_foreign_foreground_count'] == 0 for d in dictionaries),
            }
            marker_counts = Counter(grid[r][c] for r, c in remaining)
            record = {'background': background, 'shape_colour': shape_colour,
                      'raw_codes': dictionaries, 'per_component_raw_ids': per_part,
                      'bbox_foreign_counts': foreign_counts, 'partition_facts': flags,
                      'dictionary_cells_bitmap': diagnostic_bitmap(dictionary_union, width),
                      'remaining_foreground_by_colour': {
                          colour: {'cells_bitmap': diagnostic_bitmap(((r, c) for r, c in remaining if grid[r][c] == colour), width),
                                   'raw_key_match_count': keys[colour]}
                          for colour in sorted(marker_counts)},
                      'code_ownership_conflicts': [[r, c, count] for (r, c), count in sorted(code_counter.items()) if count != 1],
                      'unused_raw_ids': [d['raw_id'] for d in dictionaries if marker_counts[d['key']] == 0],
                      'complete_role': bool(dictionaries) and all(value for flag, value in flags.items() if flag != 'every_remaining_foreground_cell_has_one_raw_key_match')}
            records.append(record)
            if record['complete_role']:
                templates = []
                for d in dictionaries:
                    ar, ac = d['anchor']
                    part = parts[d['component']]
                    templates.append({**d, 'shape_cells': tuple(sorted(part)),
                                      'offsets': tuple(sorted((r - ar, c - ac) for r, c in part)),
                                      'markers': tuple((r, c) for r, c in remaining if grid[r][c] == d['key'])})
                complete_roles.append({'background': background, 'shape_colour': shape_colour,
                                       'templates': templates, 'metadata': frozenset(dictionary_union),
                                       'shape': (height, width), 'shape_cell_count': len(supports[shape_colour]),
                                       'marker_count': len(remaining), 'unmatched': tuple((r,c,grid[r][c]) for r,c in remaining if grid[r][c] not in keys)})
    raw_complete_roles = complete_roles
    scores = background_scores(grid, background_rule)
    winners = [colour for colour, value in scores.items() if value == max(scores.values())]
    complete_roles = [role for role in raw_complete_roles if winners == [role['background']]]
    record = {'background_rule': background_rule, 'background_scores': scores,
              'background_winners': winners, 'unfiltered_partial_role_count': len(raw_complete_roles),
              'shape': [height, width], 'palette': palette,
              'diagnostic_bitmap_encoding': 'hex integer; bit r*width+c owns the input cell(r,c); no predictive lookup',
              'shape_components': {colour: [{'component': i, 'bbox': bounds[colour][i], 'cells': cells(part)}
                                            for i, part in enumerate(groups[colour])] for colour in palette},
              'pair_count': len(records), 'all_pairs': records, 'complete_role_count': len(complete_roles),
              'raw_ray_visits': ray_visits, 'raw_ray_upper_bound': 36 * height * width,
              'all_pairs_completed_before_render': True}
    if ray_visits > 36 * height * width:
        return None, {**record, 'failure': 'raw_ray_bound_invariant_failed'}
    if len(complete_roles) != 1:
        return None, {**record, 'failure': 'complete_input_role_not_unique'}
    selected = complete_roles[0]
    record['selected_colours'] = [selected['background'], selected['shape_colour']]
    return selected, record


def render_role(payload, passive_policy="preserve"):
    if passive_policy not in ("preserve", "erase"):
        raise ValueError("unknown passive policy")
    height, width = payload['shape']
    colours, origins = defaultdict(set), defaultdict(list)
    clipped, marker_records = [], []
    proposal_count = 0
    for d in payload['templates']:
        for marker_index, (mr, mc) in enumerate(d['markers']):
            visible = 0
            for source_index, (dr, dc) in enumerate(d['offsets']):
                r, c = mr + dr, mc + dc
                proposal_count += 1
                witness = [d['raw_id'], marker_index, source_index]
                if 0 <= r < height and 0 <= c < width:
                    colours[(r, c)].add(d['value'])
                    origins[(r, c)].append(witness)
                    visible += 1
                else:
                    clipped.append([*witness, r, c])
            marker_records.append({'dictionary': d['raw_id'], 'marker': [mr, mc],
                                   'source_pixel_count': len(d['offsets']), 'in_bounds_proposals': visible,
                                   'clipped_proposals': len(d['offsets']) - visible})
    conflicts = [{'cell': list(point), 'colours': sorted(values), 'origins': origins[point]}
                 for point, values in sorted(colours.items()) if len(values) != 1]
    footprint = [{'cell': list(point), 'colours': sorted(values), 'origins': origins[point]}
                 for point, values in sorted(colours.items())]
    record = {'passive_policy': passive_policy, 'passive_cells': [list(p) for p in payload['unmatched']],
              'background': payload['background'], 'shape_colour': payload['shape_colour'],
              'templates': payload['templates'], 'all_markers': marker_records,
              'proposal_count': proposal_count, 'proposal_product_bound': payload['shape_cell_count'] * payload['marker_count'],
              'proposal_canvas_bound': (height * width) ** 2 // 4,
              'clipped_count': len(clipped), 'clipped_proposals': clipped,
              'in_bounds_proposal_count': proposal_count - len(clipped),
              'union_cell_count': len(colours), 'all_in_bounds_ownership': footprint,
              'multiple_proposal_coordinates': [list(point) for point in sorted(origins) if len(origins[point]) > 1],
              'conflicts': conflicts, 'all_proposals_complete': True}
    if not proposal_count <= record['proposal_product_bound'] <= record['proposal_canvas_bound']:
        return None, {**record, 'failure': 'proposal_bound_invariant_failed'}
    if conflicts:
        return None, {**record, 'failure': 'different_colours_overlap'}
    if passive_policy == 'preserve':
        passive_conflicts = [[r,c,value,sorted(colours[(r,c)])] for r,c,value in payload['unmatched']
                             if (r,c) in colours and colours[(r,c)] != {value}]
        if passive_conflicts:
            return None, {**record, 'failure': 'passive_ownership_conflict', 'passive_conflicts': passive_conflicts}
    output = [[payload['background']] * width for _ in range(height)]
    if passive_policy == 'preserve':
        for r,c,value in payload['unmatched']:
            output[r][c] = value
    for (r, c), values in colours.items():
        output[r][c] = next(iter(values))
    markers = {point for d in payload['templates'] for point in d['markers']}
    record.update(metadata_cell_count=len(payload['metadata']),
                  metadata_repainted_cells=cells(payload['metadata'] & colours.keys()),
                  target_pixel_count=len(markers), marker_foreground_count=len(markers & colours.keys()),
                  marker_background_count=len(markers - colours.keys()),
                  output_colour_counts=dict(sorted(Counter(v for row in output for v in row).items())))
    return output, record



BACKGROUND_RULES = ('area_mode', 'border_mode', 'largest_c4')

def background_scores(grid, rule):
    h,w = len(grid),len(grid[0])
    palette = sorted({v for row in grid for v in row})
    if rule == 'area_mode':
        return dict(Counter(v for row in grid for v in row))
    if rule == 'border_mode':
        counts = Counter(grid[r][c] for r in range(h) for c in range(w)
                         if r in (0,h-1) or c in (0,w-1))
        return {v: counts[v] for v in palette}
    if rule == 'largest_c4':
        return {v: max(map(len, components({(r,c) for r in range(h) for c in range(w)
                                             if grid[r][c] == v}, False))) for v in palette}
    raise ValueError('unknown background rule')

def render_model(grid, background_rule, passive_policy='preserve'):
    payload, parse_record = parse_input(grid, background_rule)
    if payload is None:
        return None, {'failure': 'input_not_interpretable', 'parse': parse_record}
    output, render_record = render_role(payload, passive_policy)
    record = {'parse': parse_record, 'render': render_record}
    if output is None:
        return None, {**record, 'failure': 'unique_role_render_failed'}
    return output, record

def fit_teachers(teachers):
    if (type(teachers) not in (list,tuple) or len(teachers)<2
        or any(type(pair) is not dict or not valid_grid(pair.get('input'))
               or not valid_grid(pair.get('output')) for pair in teachers)):
        return None, {'failure': 'invalid_teachers'}
    if len({tuple(map(tuple,pair['input'])) for pair in teachers}) < 2:
        return None, {'failure': 'insufficient_distinct_teachers'}
    retained, records = [], []
    for rule in BACKGROUND_RULES:
        evaluations = [render_model(pair['input'],rule) for pair in teachers]
        fits = [out == pair['output'] for (out,_),pair in zip(evaluations,teachers)]
        records.append({'rule':rule,'teacher_fit':fits,'records':[d for _,d in evaluations]})
        if all(fits):
            retained.append(rule)
    if not retained:
        return None, {'failure':'no_teacher_fit','all_candidates':records}
    return {'kind':'passive_keyed_stamp','version':1,'background_rules':retained}, {'all_candidates':records}

def predict(grid, model):
    if (not isinstance(model,dict) or model.get('kind') != 'passive_keyed_stamp'
        or model.get('version') != 1 or not model.get('background_rules')
        or any(rule not in BACKGROUND_RULES for rule in model['background_rules'])):
        return None, {'failure':'invalid_model'}
    evaluations = [render_model(grid,rule) for rule in model['background_rules']]
    records = [{'rule':rule,'record':d} for rule,(_,d) in zip(model['background_rules'],evaluations)]
    outputs = [out for out,_ in evaluations]
    if any(out is None for out in outputs):
        return None, {'failure':'retained_candidate_failed','all_candidates':records}
    if any(out != outputs[0] for out in outputs):
        return None, {'failure':'retained_candidates_disagree','all_candidates':records}
    return outputs[0], {'all_candidates':records,'all_retained_agree':True}
