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


def support_boundary_role(grid, background_rule):
    """Find a fully-owned multi-key stamp using rays from actual support pixels."""
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    height, width = len(grid), len(grid[0])
    palette = sorted({v for row in grid for v in row})
    scores = background_scores(grid, background_rule)
    winners = [colour for colour, value in scores.items() if value == max(scores.values())]
    if len(winners) != 1:
        return None, {'failure': 'ambiguous_background', 'background_scores': scores,
                      'background_winners': winners}
    background = winners[0]
    supports = {colour: {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row)
                         if value == colour} for colour in palette}
    foreground = {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row)
                  if value != background}
    role_candidates, role_records = [], []
    for shape_colour in palette:
        if shape_colour == background:
            continue
        parts = components(supports[shape_colour], True)
        raw_codes, per_component = [], []
        for component, part in enumerate(parts):
            component_codes, seen = [], set()
            for anchor in sorted(part):
                for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    value_cell = (anchor[0] + dr, anchor[1] + dc)
                    key_cell = (anchor[0] + 2 * dr, anchor[1] + 2 * dc)
                    if not all(0 <= r < height and 0 <= c < width
                               for r, c in (value_cell, key_cell)):
                        continue
                    value = grid[value_cell[0]][value_cell[1]]
                    key = grid[key_cell[0]][key_cell[1]]
                    if (value == key or value in (background, shape_colour)
                            or key in (background, shape_colour)):
                        continue
                    signature = (key, value, key_cell, value_cell, anchor)
                    if signature in seen:
                        continue
                    seen.add(signature)
                    component_codes.append({'raw_id': len(raw_codes) + len(component_codes),
                                            'component': component, 'anchor': anchor,
                                            'key_cell': key_cell, 'value_cell': value_cell,
                                            'key': key, 'value': value})
            per_component.append(component_codes)
            raw_codes.extend(component_codes)
        reason = None
        if len(raw_codes) < 2:
            reason = 'fewer_than_two_support_rays'
        elif any(not codes for codes in per_component):
            reason = 'shape_component_without_support_ray'
        elif len({item['key'] for item in raw_codes}) != len(raw_codes):
            reason = 'non_unique_support_ray_keys'
        code_cells = {cell for item in raw_codes for cell in (item['key_cell'], item['value_cell'])}
        if reason is None and (supports[shape_colour] & code_cells
                               or len(code_cells) != 2 * len(raw_codes)):
            reason = 'support_ray_code_ownership_overlap'
        remaining = foreground - supports[shape_colour] - code_cells
        keys = {item['key'] for item in raw_codes}
        if reason is None and any(grid[r][c] not in keys for r, c in remaining):
            reason = 'unmatched_foreground_outside_support_rays'
        if reason is None:
            for part in parts:
                top, left, bottom, right = box(part)
                if any(grid[r][c] != background
                       and (r, c) not in supports[shape_colour]
                       and (r, c) not in code_cells
                       for r in range(top, bottom + 1) for c in range(left, right + 1)):
                    reason = 'unowned_foreground_inside_template_box'
                    break
        if reason is not None:
            role_records.append({'shape_colour': shape_colour, 'raw_code_count': len(raw_codes),
                                 'per_component_ray_counts': [len(codes) for codes in per_component],
                                 'rejection': reason})
            continue
        markers = {key: tuple(sorted((r, c) for r, c in remaining if grid[r][c] == key))
                   for key in keys}
        if any(not points for points in markers.values()):
            role_records.append({'shape_colour': shape_colour, 'raw_code_count': len(raw_codes),
                                 'per_component_ray_counts': [len(codes) for codes in per_component],
                                 'rejection': 'support_ray_key_without_markers'})
            continue
        templates = []
        for item in raw_codes:
            anchor = item['anchor']
            part = parts[item['component']]
            templates.append({**item, 'anchor': tuple(anchor),
                              'shape_cells': tuple(sorted(part)),
                              'offsets': tuple(sorted((r - anchor[0], c - anchor[1])
                                                      for r, c in part)),
                              'markers': markers[item['key']]})
        role_candidates.append({'background': background, 'shape_colour': shape_colour,
                                'templates': templates, 'metadata': frozenset(
                                    supports[shape_colour] | code_cells),
                                'unmatched': (), 'shape': (height, width),
                                'shape_cell_count': len(supports[shape_colour]),
                                'marker_count': len(remaining)})
        role_records.append({'shape_colour': shape_colour, 'raw_code_count': len(raw_codes),
                             'per_component_ray_counts': [len(codes) for codes in per_component],
                             'keys': sorted(keys), 'markers_by_key': {
                                 str(key): len(points) for key, points in sorted(markers.items())}})
    record = {'background_rule': background_rule, 'background_scores': scores,
              'background_winners': winners, 'support_boundary_roles': role_records,
              'support_boundary_role_count': len(role_candidates)}
    if len(role_candidates) != 1:
        return None, {**record, 'failure': 'support_boundary_role_not_unique'}
    return role_candidates[0], record


def render_conflict_candidates(payload):
    """Return nearest-owner outputs with first/last input-order tie handling."""
    height, width = payload['shape']
    proposals, clipped = defaultdict(list), []
    proposal_order = 0
    for template in payload['templates']:
        for marker_index, (marker_r, marker_c) in enumerate(template['markers']):
            for source_index, (dr, dc) in enumerate(template['offsets']):
                r, c = marker_r + dr, marker_c + dc
                if 0 <= r < height and 0 <= c < width:
                    proposals[(r, c)].append({'value': template['value'],
                                              'marker': (marker_r, marker_c),
                                              'key': template['key'],
                                              'raw_id': template['raw_id'],
                                              'order': proposal_order})
                else:
                    clipped.append([template['raw_id'], marker_index, source_index, r, c])
                proposal_order += 1
    mixed_conflicts = {point: values for point, values in proposals.items()
                       if len({item['value'] for item in values}) > 1}
    if not mixed_conflicts:
        return None, {'failure': 'no_different_colour_overlap',
                      'proposal_count': proposal_order,
                      'mixed_colour_conflict_count': 0}
    outputs, tied_owner_cells = [], 0
    for choose_last in (False, True):
        output = [[payload['background']] * width for _ in range(height)]
        for r, c, value in payload['unmatched']:
            output[r][c] = value
        for (r, c), values in proposals.items():
            distances = [abs(item['marker'][0] - r) + abs(item['marker'][1] - c)
                         for item in values]
            nearest = min(distances)
            owners = [item for item, distance in zip(values, distances) if distance == nearest]
            if len({item['value'] for item in owners}) > 1 and not choose_last:
                tied_owner_cells += 1
            chosen = (max if choose_last else min)(owners, key=lambda item: item['order'])
            output[r][c] = chosen['value']
        outputs.append(output)
    record = {'policies': ['nearest_manhattan_first_input_order',
                           'nearest_manhattan_last_input_order'],
              'proposal_count': proposal_order, 'clipped_count': len(clipped),
              'mixed_colour_conflict_count': len(mixed_conflicts),
              'nearest_owner_tie_cell_count': tied_owner_cells,
              'distinct_outputs': outputs[0] != outputs[1]}
    if outputs[0] == outputs[1]:
        return None, {**record, 'failure': 'nearest_owner_policies_agree'}
    return outputs, record


def render_support_model(grid, background_rule):
    payload, parse_record = support_boundary_role(grid, background_rule)
    if payload is None:
        return None, {'failure': 'support_boundary_input_not_interpretable',
                      'parse': parse_record}
    output, render_record = render_role(payload)
    if output is not None:
        return output, {'parse': parse_record, 'render': render_record,
                        'support_boundary_role': True}
    candidates, candidate_record = render_conflict_candidates(payload)
    if candidates is None:
        return None, {'failure': 'support_boundary_render_failed',
                      'parse': parse_record, 'render': render_record,
                      'candidate_render': candidate_record}
    return None, {'failure': 'support_boundary_overlap_requires_attempt_choice',
                  'parse': parse_record, 'render': render_record,
                  'candidate_attempts': candidates,
                  'candidate_attempt_policies': candidate_record['policies'],
                  'candidate_render': candidate_record}

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
        if all(out is None for out in outputs):
            support_evaluations = [render_support_model(grid, rule)
                                   for rule in model['background_rules']]
            support_outputs = [out for out, _ in support_evaluations]
            support_records = [{'rule': rule, 'record': record}
                               for rule, (_, record) in zip(model['background_rules'],
                                                           support_evaluations)]
            if support_outputs and all(out is not None for out in support_outputs):
                if all(out == support_outputs[0] for out in support_outputs):
                    return support_outputs[0], {'all_candidates': records,
                                                'support_boundary_candidates': support_records,
                                                'all_support_boundary_rules_agree': True}
            pairs = [record.get('candidate_attempts')
                     if isinstance(record, dict) else None
                     for _, record in support_evaluations]
            valid_pairs = [isinstance(pair, list) and len(pair) == 2
                           and all(valid_grid(grid) for grid in pair)
                           and pair[0] != pair[1] for pair in pairs]
            if pairs and all(valid_pairs) and all(pair == pairs[0] for pair in pairs):
                return None, {'failure': 'overlap_requires_attempt_choice',
                              'candidate_attempts': pairs[0],
                              'candidate_attempt_policies': support_evaluations[0][1][
                                  'candidate_attempt_policies'],
                              'all_candidates': records,
                              'support_boundary_candidates': support_records,
                              'all_support_boundary_rules_agree': True}
        return None, {'failure':'retained_candidate_failed','all_candidates':records}
    if any(out != outputs[0] for out in outputs):
        return None, {'failure':'retained_candidates_disagree','all_candidates':records}
    return outputs[0], {'all_candidates':records,'all_retained_agree':True}
