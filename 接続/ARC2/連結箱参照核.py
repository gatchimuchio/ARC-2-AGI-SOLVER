"""Input-only composition diagnostic; no IO, identifiers, or fixed role colors."""
from collections import Counter
from itertools import combinations, product

from 接続.ARC2.凡例旋回教材 import body_components
from 接続.ARC2.既存成分最短経路 import component_adjacency_8
from 接続.ARC2.境界点周期候補 import valid_grid, merge_proposals

PROGRAMS = tuple(product(('C4', 'C8', 'C8_no_corner_shortcut'),
                         ('C4', 'C8', 'cardinal_side_midpoint')))


def ownerships(grid):
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
