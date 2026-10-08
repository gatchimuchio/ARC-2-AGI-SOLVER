"""Input contact constraints, colour deletion, and a bounded least fixed point."""

from collections import Counter, defaultdict

WORK_LIMIT = 100000

D4 = ((-1, 0), (1, 0), (0, -1), (0, 1))

def coords(points):
    return [list(point) for point in sorted(points)]

def box(points):
    return ([min(r for r, c in points), min(c for r, c in points),
             max(r for r, c in points), max(c for r, c in points)] if points else None)

def components(points):
    todo, result = set(points), []
    while todo:
        start = min(todo)
        todo.remove(start)
        queue, group = [start], {start}
        while queue:
            r, c = queue.pop()
            for dr, dc in D4:
                q = (r + dr, c + dc)
                if q in todo:
                    todo.remove(q)
                    group.add(q)
                    queue.append(q)
        result.append(group)
    return result

def edges(points, height, width):
    return [name for name, yes in [("top", any(r == 0 for r, c in points)),
                                  ("bottom", any(r == height - 1 for r, c in points)),
                                  ("left", any(c == 0 for r, c in points)),
                                  ("right", any(c == width - 1 for r, c in points))] if yes]

def rotate_point(point, height, width, turns):
    r, c = point
    for _ in range(turns):
        r, c, height, width = c, height - 1 - r, width, height
    return (r, c), height, width

def detailed_type(scene, height, width, material_bits=None):
    """scene is only canonicalized observed input coordinates, not a generated grid."""
    posts, beams, owners = [], [], {}
    for r, c in sorted(scene):
        colour = scene[(r, c)]
        if scene.get((r - 1, c)) == colour:
            continue
        bottom = r
        while scene.get((bottom + 1, c)) == colour:
            bottom += 1
        if bottom == r:
            continue
        name = f"P{len(posts)}"
        cells = [(rr, c) for rr in range(r, bottom + 1)]
        posts.append({"id": name, "kind": "post", "colour": colour, "column": c,
                      "top": r, "visible_bottom": bottom, "visible_length": len(cells),
                      "visible_cells": coords(cells)})
        for point in cells:
            owners[point] = name
    remaining = set(scene) - owners.keys()
    post_owners = dict(owners)
    failures = []
    for r, c in sorted(remaining):
        colour = scene[(r, c)]
        if (r, c - 1) in remaining and scene[(r, c - 1)] == colour:
            continue
        last = c
        while (r, last + 1) in remaining and scene[(r, last + 1)] == colour:
            last += 1
        name = f"B{len(beams)}"
        cells = [(r, cc) for cc in range(c, last + 1)]
        endpoints = [(r, c - 1), (r, last + 1)]
        endpoint_ids = [post_owners.get(point) for point in endpoints]
        b = {"id": name, "kind": "beam", "colour": colour, "row": r,
             "body_columns": list(range(c, last + 1)), "body_cells": coords(cells),
             "body_length": len(cells), "full_span_columns": list(range(c - 1, last + 2)),
             "original_endpoint_cells": [list(p) for p in endpoints],
             "original_endpoint_post_ids": endpoint_ids,
             "both_endpoints_unique_original_posts": all(p is not None for p in endpoint_ids)}
        beams.append(b)
        if not b["both_endpoints_unique_original_posts"]:
            failures.append({"code": "beam_endpoint_not_a_post", "beam": name,
                             "endpoint_cells": b["original_endpoint_cells"], "post_ids": endpoint_ids,
                             "observed_endpoint_colours": [scene.get(point) for point in endpoints]})
        for point in cells:
            owners[point] = name
    obj = {x["id"]: x for x in posts + beams}
    for p in posts:
        below = (p["visible_bottom"] + 1, p["column"])
        under = owners.get(below)
        joined = any(p['id'] in b['original_endpoint_post_ids'] and p['colour'] == b['colour'] for b in beams)
        p['material_context'] = p['visible_length']
        p['same_colour_beam_attachment'] = joined
        p['hidden_bottom_bit'] = bool(material_bits.get(p['material_context'], False)) if material_bits is not None else False
        latent = bool(under and obj[under]["kind"] == "beam" and p['hidden_bottom_bit'])
        p.update({"latent_length": p["visible_length"] + int(latent),
                  "latent_bottom": p["visible_bottom"] + int(latent),
                  "declared_latent_cell": list(below) if latent else None,
                  "occluding_body": under if latent else None})
    if set(owners) != set(scene):
        failures.append({"code": "visible_ownership_incomplete"})
    incidence = defaultdict(list)
    for p in posts:
        for r in range(p["top"], p["latent_bottom"] + 1):
            incidence[(r, p["column"])].append(p["id"])
    for b in beams:
        for point in map(tuple, b["body_cells"]):
            incidence[point].append(b["id"])
    hidden = []
    for point, ids in sorted(incidence.items()):
        ps = [i for i in ids if obj[i]["kind"] == "post"]
        bs = [i for i in ids if obj[i]["kind"] == "beam"]
        valid = len(ps) <= 1 and len(bs) <= 1
        if len(ids) > 1:
            valid = valid and len(ps) == len(bs) == 1 and point[0] == obj[ps[0]]["latent_bottom"]
            if valid:
                hidden.append({"cell": list(point), "post": ps[0], "beam": bs[0]})
        if not valid:
            failures.append({"code": "latent_ownership_collision", "cell": list(point), "owners": ids})
        painted = bs[0] if bs else ids[0]
        if scene.get(point) != obj[painted]["colour"]:
            failures.append({"code": "source_incidence_colour_mismatch", "cell": list(point), "owners": ids})
    if set(incidence) != set(scene):
        failures.append({"code": "foreground_coverage_mismatch", "missing": coords(set(scene) - incidence.keys()),
                         "extra": coords(incidence.keys() - set(scene))})
    record = {"posts": posts, "beams": beams,
              "visible_ownership": [{"cell": list(point), "owner": who} for point, who in sorted(owners.items())],
              "visible_scene_count": len(scene), "visible_assigned_once": len(owners) == len(scene),
              "declared_hidden_bottoms": hidden, "declared_hidden_count": len(hidden),
              "declared_material_count": sum(p["latent_length"] for p in posts) + sum(b["body_length"] for b in beams),
              "type_failures": failures, "type_holds": not failures,
              "stability_checked": False, "stability_holds": None,
              "input_rows_only": True, "candidate_selection_was_already_frozen": True}
    return record


def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30
            and type(grid[0]) is list and 1 <= len(grid[0]) <= 30
            and all(type(row) is list and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row) for row in grid))


def parse_input(grid, material_bits=None):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    height, width = len(grid), len(grid[0])
    counts = Counter(v for row in grid for v in row)
    modes = sorted(c for c, n in counts.items() if n == max(counts.values()))
    rec = {'shape': [height, width], 'background_candidates': modes,
           'raw_candidates': [], 'raw_count': 0, 'type_entered': False}
    if len(modes) != 1:
        return None, {**rec, 'failure': 'background_not_unique'}
    background = modes[0]
    foreground = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != background}
    groups = components(foreground)
    rec.update(background=background, foreground_count=len(foreground),
               components=[coords(group) for group in groups])
    for group in groups:
        if len(group) != 1:
            continue
        cue = next(iter(group))
        scene = foreground - group
        bounds = box(scene)
        outside = bool(bounds and not (bounds[0] <= cue[0] <= bounds[2]
                                       and bounds[1] <= cue[1] <= bounds[3]))
        touched = edges(scene, height, width)
        rec['raw_candidates'].append({'cue': list(cue), 'colour': grid[cue[0]][cue[1]],
                                      'scene_bbox': bounds, 'outside': outside, 'edges': touched,
                                      'eligible': outside and len(touched) == 1})
    eligible = [c for c in rec['raw_candidates'] if c['eligible']]
    rec['raw_count'] = len(eligible)
    # Preserve every eligible original scalar interpretation, including ambiguity.
    # A multi-control component is a separately declared syntax extension only
    # when the scalar grammar has no eligible interpretation.
    if not eligible:
        extended = []
        for group in groups:
            if len(group) <= 1:
                continue
            scene = foreground - group
            bounds = box(scene)
            outside = bool(bounds and all(not (bounds[0] <= r <= bounds[2]
                                              and bounds[1] <= c <= bounds[3])
                                          for r,c in group))
            touched = edges(scene, height, width)
            candidate = {'cue': list(min(group)), 'colour': grid[min(group)[0]][min(group)[1]],
                         'cue_cells': coords(group), 'scene_bbox': bounds,
                         'outside': outside, 'edges': touched,
                         'eligible': outside and len(touched) == 1}
            extended.append(candidate)
        rec['extended_control_candidates'] = extended
        eligible = [candidate for candidate in extended if candidate['eligible']]
        rec['extended_control_count'] = len(eligible)
    if len(eligible) != 1:
        return None, {**rec, 'failure': 'raw_cue_floor_not_unique'}
    selected = eligible[0]
    cue = tuple(selected['cue'])
    cue_cells = set(map(tuple, selected.get('cue_cells', [selected['cue']])))
    turns = {'bottom': 0, 'right': 1, 'top': 2, 'left': 3}[selected['edges'][0]]
    scene = {}
    for point in foreground - cue_cells:
        point2, ch, cw = rotate_point(point, height, width, turns)
        scene[point2] = grid[point[0]][point[1]]
    canonical_cue, ch, cw = rotate_point(cue, height, width, turns)
    details = detailed_type(scene, ch, cw, material_bits)
    rec.update(type_entered=True, turns=turns, canonical_shape=[ch, cw],
               canonical_cue=list(canonical_cue), details=details)
    if not details['type_holds']:
        return None, {**rec, 'failure': 'whole_scene_type_failed'}
    pieces = {p['id']: dict(p) for p in details['posts'] + details['beams']}
    for p in details['posts']:
        pieces[p['id']]['lower_posts'] = tuple(q['id'] for q in details['posts']
            if q['id'] != p['id'] and q['column'] == p['column'] and q['top'] > p['latent_bottom'])
        pieces[p['id']]['lower_beams'] = tuple(b['id'] for b in details['beams']
            if p['column'] in b['full_span_columns'] and b['row'] >= p['latent_bottom'])
    for b in details['beams']:
        pieces[b['id']]['lower_beams'] = tuple(q['id'] for q in details['beams']
            if q['row'] > b['row'] and set(q['body_columns']) & set(b['body_columns']))
        pieces[b['id']]['lower_posts'] = tuple(p['id'] for p in details['posts']
            if p['top'] > b['row'] and p['column'] in b['body_columns'])
    rows = {name: p['top'] if p['kind'] == 'post' else p['row'] for name, p in pieces.items()}
    payload = {'height': ch, 'width': cw, 'original_shape': (height, width), 'turns': turns,
               'background': background, 'cue': canonical_cue, 'cue_colour': selected['colour'],
               'cue_cells': {rotate_point(point,height,width,turns)[0]: grid[point[0]][point[1]]
                             for point in cue_cells},
               'pieces': pieces, 'original_rows': rows,
               'input_colour_counts': dict(sorted(counts.items()))}
    rec['static_pieces'] = pieces
    return payload, rec


class IncompleteContactWork(Exception):
    pass


class WorkBudget:
    def __init__(self, limit):
        if type(limit) is not int or not 0 <= limit <= WORK_LIMIT:
            raise ValueError('Work limit must be an integer in0..100000')
        self.limit = limit
        self.used = 0
        self.counts = {'piece': 0, 'bound': 0}

    def charge(self, kind):
        if self.used >= self.limit:
            raise IncompleteContactWork()
        self.used += 1
        self.counts[kind] += 1


def evaluate_map(payload, alive, rows, budget):
    pieces, height = payload['pieces'], payload['height']
    result, records = {}, []
    for name in sorted(alive):
        budget.charge('piece')
        p = pieces[name]
        terms = []
        budget.charge('bound')
        if p['kind'] == 'post':
            length = p['latent_length']
            terms.append({'source': 'floor', 'value': height - length})
            for lower in p['lower_posts']:
                if lower in alive:
                    budget.charge('bound')
                    terms.append({'source': lower, 'relation': 'below_post', 'value': rows[lower] - length})
            for lower in p['lower_beams']:
                if lower in alive:
                    budget.charge('bound')
                    terms.append({'source': lower, 'relation': 'below_full_span_beam', 'value': rows[lower] - length + int(p['hidden_bottom_bit'] or p['column'] not in pieces[lower]['body_columns'])})
        else:
            terms.append({'source': 'floor', 'value': height - 1})
            budget.charge('bound')
            left, right = p['original_endpoint_post_ids']
            both = left in alive and right in alive
            side = max(rows[left], rows[right]) if both else height - 1
            terms.append({'source': 'original_endpoint_side', 'value': side,
                          'both_original_endpoints_survive': both})
            for lower in p['lower_beams']:
                if lower in alive:
                    budget.charge('bound')
                    terms.append({'source': lower, 'relation': 'below_body_overlap_beam', 'value': rows[lower] - 1})
            for lower in p['lower_posts']:
                if lower in alive:
                    budget.charge('bound')
                    terms.append({'source': lower, 'relation': 'below_body_column_post', 'value': rows[lower] - 1})
        result[name] = min(term['value'] for term in terms)
        records.append({'piece': name, 'old_row': rows[name], 'all_terms': terms, 'new_row': result[name]})
    return result, records


def final_geometry(payload, alive, rows):
    height, width, pieces = payload['height'], payload['width'], payload['pieces']
    incidence = defaultdict(list)
    material = Counter()
    failures = []
    for name in sorted(alive):
        p = pieces[name]
        if rows[name] < payload['original_rows'][name]:
            failures.append({'piece': name, 'failure': 'upward_motion'})
        if p['kind'] == 'post':
            cells = [(r, p['column']) for r in range(rows[name], rows[name] + p['latent_length'])]
        else:
            cells = [(rows[name], c) for c in p['body_columns']]
        for point in cells:
            incidence[point].append(name)
            material[p['colour']] += 1
    hidden, ownership = [], []
    for point, names in sorted(incidence.items()):
        if not (0 <= point[0] < height and 0 <= point[1] < width) or (point == payload['cue'] or point in payload.get('cue_cells', {})):
            failures.append({'cell': list(point), 'owners': names, 'failure': 'bounds_or_cue_collision'})
        posts = [n for n in names if pieces[n]['kind'] == 'post']
        beams = [n for n in names if pieces[n]['kind'] == 'beam']
        valid = len(posts) <= 1 and len(beams) <= 1
        if len(names) > 1:
            valid = valid and len(posts) == len(beams) == 1
            valid = valid and point[0] == rows[posts[0]] + pieces[posts[0]]['latent_length'] - 1
            if valid:
                hidden.append({'cell': list(point), 'post': posts[0], 'beam': beams[0],
                               'hidden_colour': pieces[posts[0]]['colour']})
        if not valid:
            failures.append({'cell': list(point), 'owners': names, 'failure': 'forbidden_material_collision'})
        winner = beams[0] if beams else names[0]
        ownership.append({'cell': list(point), 'owners': names, 'painted_by': winner,
                          'colour': pieces[winner]['colour']})
    record = {'failures': failures, 'all_ownership': ownership, 'hidden_bottoms': hidden,
              'material_by_colour': dict(sorted(material.items())),
              'material_count': sum(material.values()), 'hidden_count': len(hidden),
              'visible_scene_count': len(incidence)}
    record['hidden_by_colour'] = dict(sorted(Counter(x['hidden_colour'] for x in hidden).items()))
    record['visible_by_colour'] = dict(sorted(Counter(x['colour'] for x in ownership).items()))
    if failures:
        return None, record
    canonical = [[payload['background']] * width for _ in range(height)]
    for cell in ownership:
        r, c = cell['cell'];canonical[r][c] = cell['colour']
    for (r,c), colour in payload.get('cue_cells', {payload['cue']:payload['cue_colour']}).items():
        canonical[r][c] = colour
    oh, ow = payload['original_shape']
    output = [[payload['background']] * ow for _ in range(oh)]
    for r, row in enumerate(canonical):
        for c, colour in enumerate(row):
            (rr, cc), _, _ = rotate_point((r, c), height, width, (-payload['turns']) % 4)
            output[rr][cc] = colour
    record['output_colour_counts'] = dict(sorted(Counter(v for row in output for v in row).items()))
    return output, record


def render(grid, work_limit=WORK_LIMIT, material_bits=None):
    try:
        budget = WorkBudget(work_limit)
    except ValueError:
        return None, {'failure': 'invalid_work_limit'}
    try:
        payload, parse_record = parse_input(grid, material_bits)
    except Exception as error:
        return None, {'failure': 'input_interpretation_exception', 'error_type': type(error).__name__,
                      'work': 0, 'work_limit': work_limit, 'complete': False,
                      'partial_state_discarded': True}
    record = {'parse': parse_record, 'work_limit': work_limit, 'work': 0,
              'complete': False, 'rounds': []}
    if payload is None:
        return None, {**record, 'failure': 'input_not_interpretable'}
    pieces, original = payload['pieces'], payload['original_rows']
    try:
        source_value, terms = evaluate_map(payload, set(pieces), original, budget)
        record['source_stability_terms'] = terms
        if source_value != original:
            return None, {**record, 'failure': 'source_not_stable', 'work': budget.used,
                          'work_counts': budget.counts, 'source_map': source_value}
        # Compose the original unary equality selection pointwise, before gravity.
        # Union is independent of control-cell enumeration and duplicate colors.
        selections = [{'cue_cell': list(point), 'colour': colour,
                       'selected_pieces': sorted(name for name,p in pieces.items()
                                                 if p['colour'] == colour)}
                      for point,colour in sorted(payload['cue_cells'].items())]
        removed_by_controls = set().union(*(set(row['selected_pieces']) for row in selections))
        alive = set(pieces) - removed_by_controls
        record['pointwise_control_selections'] = selections
        removed = sorted(set(pieces) - alive)
        state = {name: original[name] for name in sorted(alive)}
        upper = {name: payload['height'] - (pieces[name]['latent_length'] if pieces[name]['kind'] == 'post' else 1)
                 for name in alive}
        potential_bound = sum(upper[name] - state[name] for name in alive)
        source_material, removed_material = Counter(), Counter()
        for name, p in pieces.items():
            size = p['latent_length'] if p['kind'] == 'post' else p['body_length']
            source_material[p['colour']] += size
            if name not in alive:
                removed_material[p['colour']] += size
        record.update(removed_pieces=removed, surviving_pieces=sorted(alive),
                      initial_surviving_rows=state.copy(), potential_increase_bound=potential_bound,
                      source_material_by_colour=dict(sorted(source_material.items())),
                      removed_material_by_colour=dict(sorted(removed_material.items())),
                      source_material_count=sum(source_material.values()),
                      removed_material_count=sum(removed_material.values()))
        while True:
            next_state, terms = evaluate_map(payload, alive, state, budget)
            if any(not state[name] <= next_state[name] <= upper[name] for name in alive):
                return None, {**record, 'failure': 'monotone_floor_invariant_failed',
                              'work': budget.used, 'work_counts': budget.counts}
            record['rounds'].append({'rows': state, 'terms': terms, 'next_rows': next_state,
                                     'potential_increase': sum(next_state.values()) - sum(state.values()),
                                     'work_after': budget.used})
            if next_state == state:
                break
            state = next_state
        output, geometry = final_geometry(payload, alive, state)
        record.update(work=budget.used, work_counts=budget.counts, complete=True,
                      least_fixed_point_rows=state, geometry=geometry)
        if output is None:
            return None, {**record, 'failure': 'final_geometry_failed'}
        record['changed_cells'] = [[r, c] for r, row in enumerate(grid) for c, v in enumerate(row) if output[r][c] != v]
        record['changed_cell_count'] = len(record['changed_cells'])
        record['input_colour_counts'] = payload['input_colour_counts']
        return output, record
    except IncompleteContactWork:
        return None, {**record, 'failure': 'contact_work_incomplete', 'work': budget.used,
                      'work_counts': budget.counts, 'partial_state_discarded': True}
    except Exception as error:
        return None, {**record, 'failure': 'contact_evaluation_exception', 'work': budget.used,
                      'work_counts': budget.counts, 'error_type': type(error).__name__,
                      'partial_state_discarded': True}


def fit_teachers(teachers):
    if (type(teachers) not in (list, tuple) or not teachers
            or any(type(pair) is not dict or 'input' not in pair or 'output' not in pair for pair in teachers)):
        return None, {'failure': 'invalid_teachers'}
    try:
        rendered = [render(pair['input']) for pair in teachers]
    except Exception as error:
        return None, {'failure': 'teacher_evaluation_exception', 'error_type': type(error).__name__,
                      'partial_fit_discarded': True, 'fit': False}
    distinct = len({tuple(tuple(row) for row in pair['input']) for pair in teachers if valid_grid(pair['input'])})
    equal = [out is not None and valid_grid(pair['output']) and out == pair['output']
             for (out, rec), pair in zip(rendered, teachers)]
    model = True if distinct >= 2 and all(equal) else None
    return model, {'teacher_records': [rec for out, rec in rendered], 'teacher_equal': equal,
                   'distinct_inputs': distinct, 'all_teachers_evaluated': True, 'fit': model is True}


class 支持構造教材:
    def __init__(self, 教師群):
        self.適合, _ = fit_teachers(教師群)

    def 候補(self, 格子, _policy):
        if self.適合 is not True:
            return None, {"failure": "全教師を再現する支持構造規約なし"}
        return render(格子)

    def 記録(self):
        return {"適合": self.適合 is True}
