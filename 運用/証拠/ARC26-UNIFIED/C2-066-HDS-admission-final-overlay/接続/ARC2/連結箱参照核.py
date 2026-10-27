"""Input-only composition diagnostic; no IO, identifiers, or fixed role colors."""
from collections import Counter
from itertools import combinations, product

from 接続.ARC2.凡例旋回教材 import body_components
from 接続.ARC2.既存物体特徴 import color_components
from 接続.ARC2.既存成分最短経路 import component_adjacency_8
from 接続.ARC2.境界点周期候補 import valid_grid, merge_proposals

PROGRAMS = tuple(product(('C4', 'C8', 'C8_no_corner_shortcut'),
                         ('C4', 'C8', 'cardinal_side_midpoint')))


def physical_objects(grid, bg):
    """Observed complete symmetric shells bind a common physical mask."""
    h, w = len(grid), len(grid[0])
    colors = sorted({v for row in grid for v in row} - {bg})
    components = [obj for color in colors for obj in color_components(grid, color, True)]
    templates = set()
    for obj in components:
        t, l, b, r = obj['bbox']
        if b-t != r-l or b-t < 2 or (b-t) % 2:
            continue
        cr, cc = (t+b)//2, (l+r)//2
        shell = {(y-cr, x-cc) for y, x in obj['cells']} - {(0, 0)}
        if ({(-dc, dr) for dr, dc in shell} != shell
                or {(dr, -dc) for dr, dc in shell} != shell):
            continue
        radius = (b-t)//2
        if not {(radius, 0), (-radius, 0), (0, radius), (0, -radius)} <= shell:
            continue
        templates.add(tuple(sorted(shell | {(0, 0)})))
    candidates = []
    for offsets in sorted(templates):
        radius = max(max(abs(dr), abs(dc)) for dr, dc in offsets)
        for cr in range(h):
            for cc in range(w):
                if not (radius <= cr < h-radius and radius <= cc < w-radius):
                    continue
                footprint = {(cr+dr, cc+dc) for dr, dc in offsets
                             if 0 <= cr+dr < h and 0 <= cc+dc < w}
                shell = footprint - {(cr, cc)}
                if len(shell) < 3:
                    continue
                keys = {grid[y][x] for y, x in shell}
                if len(keys) != 1 or bg in keys:
                    continue
                key = next(iter(keys))
                if not any(obj['color'] == key and obj['cells'] - {(cr, cc)} == shell
                           for obj in components):
                    continue
                candidates.append(dict(bbox=(cr-radius, cc-radius, cr+radius, cc+radius),
                                       center=(cr, cc), side=2*radius+1, key=key,
                                       value=grid[cr][cc], footprint=sorted(footprint),
                                       template=offsets))
    return candidates


def _ownerships(grid, clipped=False):
    if not valid_grid(grid):
        return [], {'failure': 'invalid_grid'}
    counts = Counter(v for row in grid for v in row)
    modes = sorted(v for v, n in counts.items() if n == max(counts.values()))
    if len(modes) != 1:
        return [], {'failure': 'background_not_unique_mode'}
    bg = modes[0]
    candidates = []
    for obj in body_components(grid, bg):
        t, l, b, r = obj['bbox']
        side = b - t + 1
        if side < 3 or side % 2 == 0 or side != r - l + 1:
            continue
        center = ((t+b)//2, (l+r)//2)
        footprint = {(y, x) for y in range(t, b+1) for x in range(l, r+1)}
        if obj['cells'] - {center} != footprint - {center}:
            continue
        candidates.append(dict(bbox=obj['bbox'], center=center, side=side,
                               key=obj['color'], value=grid[center[0]][center[1]],
                               footprint=sorted(footprint)))
    # Preserve the original C4 recognition domain exactly. Only absence of
    # every original square candidate opens the distinct complete-shell view.
    shell_view = not candidates
    if shell_view:
        candidates = physical_objects(grid, bg)
    if clipped:
        candidates += clipped_square_objects(grid, bg, candidates)
    fg = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != bg}
    # Every selected ownership is contained in this over-approximated union.
    # Cells outside it must remain wire for every possible candidate subset.
    candidate_union = set().union(*(set(box['footprint']) for box in candidates))
    unavoidable_wire = fg - candidate_union
    unavoidable_colors = sorted({grid[r][c] for r, c in unavoidable_wire})
    if len(unavoidable_colors) > 1:
        return [], dict(background=bg, candidate_boxes=candidates, ownership_count=0,
                        failure='unavoidable_wire_has_multiple_colors',
                        proof=dict(kind='foreground_outside_all_candidate_footprints', complete=True,
                                   candidate_union=sorted(candidate_union),
                                   unavoidable_wire_cells=sorted(unavoidable_wire),
                                   unavoidable_wire_colors=unavoidable_colors,
                                   subset_enumeration_started=False, enumerated_subsets=0))
    roles = []
    for n in range(2, len(candidates)+1):
        for indices in combinations(range(len(candidates)), n):
            boxes = [candidates[i] for i in indices]
            if len({x['side'] for x in boxes}) != 1:
                continue
            if shell_view and len({x['template'] for x in boxes}) != 1:
                continue
            owned = set().union(*(set(x['footprint']) for x in boxes))
            if len(owned) != sum(len(x['footprint']) for x in boxes):
                continue
            wire = fg - owned
            colors = {grid[r][c] for r, c in wire}
            if len(colors) != 1:
                continue
            roles.append(dict(background=bg, boxes=boxes, wire=sorted(wire),
                              wire_color=next(iter(colors))))
    return roles, dict(background=bg, candidate_boxes=candidates, ownership_count=len(roles))


def clipped_square_objects(grid, bg, complete):
    """Input-observed complete C4 squares supply masks for boundary fragments."""
    h, w = len(grid), len(grid[0])
    components = body_components(grid, bg)
    candidates = []
    for side in sorted({box['side'] for box in complete}):
        radius = side // 2
        for cr in range(h):
            for cc in range(w):
                t, l, b, r = cr-radius, cc-radius, cr+radius, cc+radius
                if 0 <= t and 0 <= l and b < h and r < w:
                    continue
                footprint = {(y, x) for y in range(max(0, t), min(h, b+1))
                             for x in range(max(0, l), min(w, r+1))}
                shell = footprint - {(cr, cc)}
                if len(shell) < 3:
                    continue
                keys = {grid[y][x] for y, x in shell}
                if len(keys) != 1 or bg in keys:
                    continue
                key = next(iter(keys))
                if not any(obj['color'] == key and obj['cells'] - {(cr, cc)} == shell
                           for obj in components):
                    continue
                candidates.append(dict(bbox=(t, l, b, r), center=(cr, cc), side=side,
                    key=key, value=grid[cr][cc], footprint=sorted(footprint), clipped=True))
    return candidates


def ownerships(grid):
    # Domain decision is entirely before graph traversal and rendering.
    roles, record = _ownerships(grid)
    if roles or record.get('failure') != 'unavoidable_wire_has_multiple_colors':
        return roles, record
    complete = record.get('candidate_boxes', [])
    if not complete or any('template' in box for box in complete):
        return roles, record
    if not clipped_square_objects(grid, record['background'], complete):
        return roles, record
    extended, extension = _ownerships(grid, clipped=True)
    extension['complete_ownership_failure'] = record
    for role in extended:
        # No old ownership exists in this domain. Every retained extension
        # must use a clipped object rather than silently replace old ownership.
        if not any(box.get('clipped') for box in role['boxes']):
            raise AssertionError('extension_without_clipped_object')
        role['reference_domain_binding'] = True
    return extended, extension


def path_graph(wire, connectivity):
    points = sorted(wire)
    raw = component_adjacency_8([{'cells': {p}} for p in points])
    cells = set(points)
    adjacency = {p: [] for p in points}
    for i, p in enumerate(points):
        for j in raw[i]:
            q = points[j]
            dr, dc = q[0]-p[0], q[1]-p[1]
            if connectivity == 'C4' and dr and dc:
                continue
            if connectivity == 'C8_no_corner_shortcut' and dr and dc:
                if (p[0], q[1]) in cells or (q[0], p[1]) in cells:
                    continue
            adjacency[p].append(q)
    ends = [p for p, adj in adjacency.items() if len(adj) == 1]
    rec = dict(degrees=[dict(cell=p, neighbors=adj) for p, adj in adjacency.items()], ends=ends)
    if len(ends) != 2:
        return None, dict(rec, failure='wire_not_exactly_two_ends')
    seen, pending = set(), [ends[0]]
    while pending:
        p = pending.pop()
        if p not in seen:
            seen.add(p)
            pending.extend(adjacency[p])
    if seen != cells:
        return None, dict(rec, failure='wire_not_connected')
    return ends, rec


def adjacent(point, footprint, connectivity):
    return any((abs(point[0]-r)+abs(point[1]-c) == 1 if connectivity == 'C4'
                else max(abs(point[0]-r), abs(point[1]-c)) == 1)
               for r, c in footprint)


def attaches(point, box, attachment):
    if attachment == 'cardinal_side_midpoint':
        t, l, b, r = box['bbox']
        cr, cc = box['center']
        return point in ((t-1, cc), (b+1, cc), (cr, l-1), (cr, r+1))
    return adjacent(point, box['footprint'], attachment)


def execute_role(grid, role, program):
    connectivity, attachment = program
    ends, graph = path_graph(role['wire'], connectivity)
    rec = dict(role=role, graph=graph, alternatives=[])
    if ends is None:
        return None, dict(rec, failure=graph['failure'])
    boxes = role['boxes']
    contacts = [[i for i, box in enumerate(boxes) if attaches(p, box, attachment)]
                for p in ends]
    rec['endpoint_attachments'] = [dict(endpoint=p, boxes=choices) for p, choices in zip(ends, contacts)]
    if role.get('reference_domain_binding'):
        # New clipped interpretation requires each endpoint to name a defined
        # input reference. Retain rejection evidence before any action occurs.
        keys = {box['key'] for box in boxes}
        rec['reference_domain_bindings'] = [dict(endpoint=p,
            retained=[i for i in choices if boxes[i]['value'] in keys],
            rejected=[dict(box=i, value=boxes[i]['value'], failure='missing_lookup_key')
                      for i in choices if boxes[i]['value'] not in keys])
            for p, choices in zip(ends, contacts)]
        spatial_missing = any(not choices for choices in contacts)
        contacts = [binding['retained'] for binding in rec['reference_domain_bindings']]
        if not spatial_missing and any(not choices for choices in contacts):
            return None, dict(rec, failure='wire_endpoint_reference_domain_empty')

    if any(not choices for choices in contacts):
        return None, dict(rec, failure='wire_endpoint_has_no_box')
    alternatives = rec['alternatives']
    for terminals in product(*contacts):
        if len(set(terminals)) != len(terminals):
            continue
        sources = [[i for i, box in enumerate(boxes) if box['key'] == boxes[t]['value']]
                   for t in terminals]
        if any(not choices for choices in sources):
            alternatives.append(dict(terminals=terminals, output=None, failure='missing_lookup_key'))
            continue
        for selected_sources in product(*sources):
            proposals = [(r, c, role['background']) for i, box in enumerate(boxes)
                         if i not in terminals for r, c in box['footprint']]
            proposals.extend((*boxes[t]['center'], boxes[s]['value'])
                             for t, s in zip(terminals, selected_sources))
            output, merge = merge_proposals(grid, proposals)
            alternatives.append(dict(terminals=terminals, lookup_sources=selected_sources,
                                     output=output, merge=merge))
    if not alternatives or any(a['output'] is None for a in alternatives):
        return None, dict(rec, failure='retained_terminal_or_lookup_failed')
    if any(a['output'] != alternatives[0]['output'] for a in alternatives):
        return None, dict(rec, failure='retained_terminal_attachments_disagree')
    return alternatives[0]['output'], dict(rec, complete=True)


def render(grid, program):
    if tuple(program) not in PROGRAMS:
        raise ValueError('undeclared_program')
    roles, parse = ownerships(grid)
    results = [execute_role(grid, role, program) for role in roles]
    rec = dict(program=program, parse=parse,
               ownership_alternatives=[dict(output=o, record=r) for o, r in results])
    if not results or any(o is None for o, r in results):
        return None, dict(rec, failure='retained_ownership_or_terminal_failed')
    if any(o != results[0][0] for o, r in results):
        return None, dict(rec, failure='retained_ownerships_disagree')
    return results[0][0], dict(rec, complete=True)
