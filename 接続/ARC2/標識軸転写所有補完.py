"""Complete free marker ownership with existing exact-support transfer primitives.

The original object connectivity, teacher grammar, and renderer are unchanged.
Only the original sole free-anchor count failure permits this input-view extension.
All whole-component covers and all complete assignments remain in consensus.
"""
from . import 標識軸転写候補 as core


def component_partitions(component_count, group_count):
    """Enumerate every unlabeled partition into exactly group_count nonempty groups."""
    groups = []

    def visit(index):
        if len(groups) > group_count or len(groups) + component_count - index < group_count:
            return
        if index == component_count:
            yield tuple(tuple(group) for group in groups)
            return
        for group in groups:
            group.append(index)
            yield from visit(index + 1)
            group.pop()
        if len(groups) < group_count:
            groups.append([index])
            yield from visit(index + 1)
            groups.pop()

    yield from visit(0)


def eligible(record):
    views = record.get('views')
    return (record.get('failure') == 'no_admitted_role_view' and bool(views)
            and all(view.get('failure') == 'raw_role_view_out_of_scope'
                    and view.get('roles', {}).get('failures') == ['object_anchor_counts_differ']
                    and 0 < len(view['roles']['objects']) < len(view['roles']['anchors'])
                    for view in views))


def complete_failed_render(grid, program, output, original):
    if output is not None or not eligible(original):
        return output, original
    trace = dict(program=program, views=[], output=None, original_return=original,
                 input_view_extension='complete_marker_support_ownership')
    try:
        for raw_view in original['views']:
            roles, partition = raw_view['roles'], raw_view['partition']
            view = dict(partition=partition, original_roles=roles, cover_returns=[],
                        output=None, admitted=True, stage='component_partitions')
            trace['views'].append(view)
            for groups in component_partitions(len(roles['anchors']), len(roles['objects'])):
                cover = dict(component_groups=groups, anchors=[], proposals=[],
                             output=None, admitted=False, complete=False,
                             stage='chamber_ownership')
                view['cover_returns'].append(cover)
                for group in groups:
                    parts = [roles['anchors'][index] for index in group]
                    chambers = {anchor['chamber'] for anchor in parts}
                    cells = sorted({tuple(cell) for anchor in parts for cell in anchor['cells']})
                    cover['anchors'].append(dict(index=len(cover['anchors']), cells=cells,
                        bbox=core.bbox(cells), chamber=next(iter(chambers)) if len(chambers) == 1 else None,
                        source_component_indices=group))
                if any(anchor['chamber'] is None for anchor in cover['anchors']):
                    cover.update(failure='component_chamber_ownership_not_unique',
                                 stage='complete', complete=True)
                    continue
                # The full original components and foreground inventory remain owned.
                # Only the sole count failure is resolved by this complete partition.
                composed = dict(roles, anchors=cover['anchors'], failures=[])
                cover['stage'] = 'enumerate_proposals'
                core.enumerate_proposals(grid, original['background'], program, partition,
                                         composed, cover['proposals'])
                cover['stage'] = 'all_assignments'
                cover['output'], failure = core.all_assignments(
                    grid, original['background'], program, partition, composed,
                    cover['proposals'], cover)
                # A group partition without any constraint-satisfying bijection is
                # structurally impossible. Every complete assignment, even a failed
                # render, makes this a retained cover and participates in consensus.
                cover['admitted'] = (bool(cover['assignments'])
                                     or failure != 'no_complete_bijective_assignment')
                if failure:
                    cover['failure'] = failure
                cover.update(stage='complete', complete=True)
            retained = [cover for cover in view['cover_returns'] if cover['admitted']]
            view['complete_cover_count'] = len(retained)
            if not retained:
                view['failure'] = 'no_complete_marker_support_cover'
            elif any(cover['output'] is None for cover in retained):
                view['failure'] = 'complete_marker_support_cover_failed'
            elif len({tuple(map(tuple, cover['output'])) for cover in retained}) != 1:
                view['failure'] = 'complete_marker_support_cover_outputs_disagree'
            else:
                view['output'] = retained[0]['output']
            view['stage'] = 'complete'
        if any(view['output'] is None for view in trace['views']):
            trace['failure'] = 'admitted_role_view_failed'
        elif len({tuple(map(tuple, view['output'])) for view in trace['views']}) != 1:
            trace['failure'] = 'admitted_role_outputs_disagree'
        else:
            trace['output'] = trace['views'][0]['output']
        return trace['output'], trace
    except core.RESOURCE_ERRORS as error:
        trace['resource_exception'] = type(error).__name__
        trace['interrupted_inner_return'] = getattr(error, 'partial_full_return', None)
        error.partial_full_return = trace
        raise
