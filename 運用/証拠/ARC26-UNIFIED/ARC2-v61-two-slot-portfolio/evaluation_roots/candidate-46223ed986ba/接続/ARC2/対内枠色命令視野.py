"""Query-only ownership view: paired panel rims also name their local ink.

The accepted teacher fit and finite action inventories are unchanged.  A
monochrome panel witnesses blank and shape; every complete frame with that
shape and a nonblank rim belongs to the cohort.  Complete disjoint outer
group covers are enumerated before any action is interpreted.
"""
from itertools import combinations

from . import 厳密枠局所命令 as strict
from . import 周期補色局所命令 as accepted


def parse(grid):
    if not strict.valid_grid(grid):
        return [], {'failure': 'invalid_grid'}
    raw = strict.frames(grid)
    seeds = set()
    for panel in raw:
        palette = {v for row in panel['interior'] for v in row}
        if len(palette) == 1:
            blank = next(iter(palette))
            if blank != panel['color']:
                seeds.add((blank, len(panel['interior']),
                           len(panel['interior'][0])))
    roles, cohort_records = [], []
    tested = 0
    for blank, height, width in sorted(seeds):
        panels = [p for p in raw if p['color'] != blank
                  and (len(p['interior']), len(p['interior'][0]))
                  == (height, width)]
        record = {'blank': blank, 'panel_shape': (height, width),
                  'panels': [p['bbox'] for p in panels],
                  'panel_colors': [p['color'] for p in panels]}
        cohort_records.append(record)
        if len(panels) < 4 or len(panels) % 2:
            record['failure'] = 'panel_count_or_parity'
            continue
        if any(not strict.bbox_relation_for_bboxes(a['bbox'], b['bbox']).disjoint
               for a, b in combinations(panels, 2)):
            record['failure'] = 'overlapping_cohort_panels'
            continue
        blank_panels = [i for i, p in enumerate(panels)
                        if len({v for row in p['interior'] for v in row}) == 1]
        if len(blank_panels) != 1 or \
                panels[blank_panels[0]]['interior'][0][0] != blank:
            record['failure'] = 'blank_panel_not_unique'
            continue
        if all(p['leaf'] for p in panels):
            record['failure'] = 'no_panel_rim_ink_witness'
            continue
        blank_id = blank_panels[0]
        groups = []
        for outer in raw:
            if outer['color'] == blank:
                continue
            members = tuple(i for i, p in enumerate(panels)
                            if strict.bbox_relation_for_bboxes(
                                outer['bbox'], p['bbox'])
                            .first_strictly_contains_second)
            if len(members) != 2:
                continue
            colors = {panels[i]['color'] for i in members}
            if len(colors) != 1 or outer['color'] in colors:
                continue
            groups.append({'bbox': outer['bbox'],
                           'outer_color': outer['color'],
                           'color': next(iter(colors)), 'members': members})
        record['groups'] = groups
        start_count = len(roles)

        def visit(owned, selected):
            nonlocal tested
            tested += 1
            if tested > 10000:
                raise strict.ResourceLimit('frame_group_cover_limit')
            if len(owned) == len(panels):
                targets = [g for g in selected if blank_id in g['members']]
                if len(targets) != 1:
                    raise AssertionError('exact_cover_target_ownership')
                roles.append({'frame_color': tuple(sorted(
                                  {p['color'] for p in panels})),
                              'blank': blank, 'blank_id': blank_id,
                              'panels': panels, 'groups': selected,
                              'target': targets[0]})
                return
            first = min(set(range(len(panels))) - owned)
            for group in groups:
                members = set(group['members'])
                if first not in members or members & owned:
                    continue
                if any(not strict.bbox_relation_for_bboxes(
                        group['bbox'], old['bbox']).disjoint for old in selected):
                    continue
                visit(owned | members, selected + [group])

        visit(set(), [])
        record['roles'] = len(roles) - start_count
    return roles, {'raw_frames': len(raw), 'roles': len(roles),
                   'cover_nodes': tested, 'cohorts': cohort_records,
                   'view': 'complete_pair_local_rim_ink'}


def render(grid):
    original = accepted.render(grid)
    output, record = original
    # Success, ambiguity, and every action-bearing structural result survive.
    if output is not None or record.get('failure') != 'no_structural_role':
        return original
    result, result_record = accepted.render(grid, parser=parse)
    return result, dict(result_record, old_record=record,
                        extension='complete_pair_local_rim_ink')
