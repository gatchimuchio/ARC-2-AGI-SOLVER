"""Rule040 input view: complete target-C8 bodies and unranked reciprocal docking.

The ownership grammar is fixed; only the old three-color roles fit teachers.
This module does not alter the accepted side-grouping view or HDS core.
"""
from itertools import product

from . import 既存標識組立 as old
from .標識組立教材 import valid_grid


NEIGHBORS_8 = tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                    if (dr, dc) != (0, 0))
PROVENANCE = {
    'fixed_prior': 'two complete target-only C8 bodies; owned opposing strip normals',
    'teacher_fit': 'old disappearing/preserved-count/remaining color inference; all teachers',
    'reused_operation': 'rigid marker-footprint translation, support union, old.tight_render',
    'rotation': False,
    'hds_core_change': False,
}


def _cells(cells):
    return [list(cell) for cell in sorted(cells)]


def _shift(cells, vector):
    dr, dc = vector
    return {(r + dr, c + dc) for r, c in cells}


def _bodies(all_target):
    """A disjoint exhaustive C8 partition, independent of translation or markers."""
    unseen = set(all_target)
    result = []
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        body, pending = {seed}, [seed]
        while pending:
            r, c = pending.pop()
            for dr, dc in NEIGHBORS_8:
                neighbor = (r + dr, c + dc)
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    body.add(neighbor)
                    pending.append(neighbor)
        result.append(body)
    return result


def guarded_render(grid, colors):
    record = {'provenance': dict(PROVENANCE), 'alternatives': []}

    def hold(reason):
        return None, {**record, 'failure': reason}

    if not valid_grid(grid):
        return hold('invalid_arc_grid')
    if (not isinstance(colors, dict) or set(colors) != {'marker', 'target', 'background'}
            or any(type(v) is not int or not 0 <= v <= 9 for v in colors.values())
            or len(set(colors.values())) != 3):
        return hold('invalid_roles')
    if {v for row in grid for v in row} - set(colors.values()):
        return hold('unknown_input_color')
    marker, target, background = (colors[k] for k in ('marker', 'target', 'background'))
    all_target = {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row)
                  if value == target}
    all_marker = {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row)
                  if value == marker}
    bodies = _bodies(all_target)
    markers = old.same_color_components(grid, marker)
    record.update({'roles': dict(colors), 'target_pixels': len(all_target),
                   'body_cells': [_cells(body) for body in bodies],
                   'marker_cells': [_cells(item['cells']) for item in markers]})
    if len(bodies) != 2:
        return hold('whole_target_body_count_out_of_scope')
    if (set().union(*bodies) != all_target
            or sum(map(len, bodies)) != len(all_target)):
        return hold('target_coverage_incomplete_or_overlapping')
    if len(markers) != 2:
        return hold('marker_component_count_out_of_scope')
    if (set().union(*(item['cells'] for item in markers)) != all_marker
            or sum(len(item['cells']) for item in markers) != len(all_marker)):
        return hold('marker_coverage_incomplete_or_overlapping')
    normalized = [{(r - item['bbox'][0], c - item['bbox'][1]) for r, c in item['cells']}
                  for item in markers]
    if normalized[0] != normalized[1]:
        return hold('marker_shapes_differ')

    attachments, probes = [], []
    for marker_index, item in enumerate(markers):
        top, left, bottom, right = item['bbox']
        if top == bottom and left == right:
            normals = old.NEIGHBORS_4
        elif top == bottom and len(item['cells']) == right - left + 1:
            normals = ((1, 0), (-1, 0))
        elif left == right and len(item['cells']) == bottom - top + 1:
            normals = ((0, 1), (0, -1))
        else:
            return hold('marker_not_straight_strip')
        owned = []
        for direction in normals:
            footprint = _shift(item['cells'], direction)
            owners = [index for index, body in enumerate(bodies) if footprint <= body]
            probe = {'marker_index': marker_index, 'inward_normal': list(direction),
                     'footprint': _cells(footprint), 'body_owners': owners,
                     'complete_target_footprint': footprint <= all_target,
                     'target_contact_pixels': len(footprint & all_target)}
            probes.append(probe)
            if footprint <= all_target:
                # A complete footprint cannot be silently dropped for bad ownership.
                owned.append(probe)
        attachments.append(owned)
    record['attachment_probes'] = probes
    record['complete_attachment_counts'] = [len(options) for options in attachments]
    if any(not options for options in attachments):
        return hold('marker_attachment_incomplete')

    outputs = []
    for pair_index, pair in enumerate(product(*attachments)):
        pair_errors = []
        if any(len(attachment['body_owners']) != 1 for attachment in pair):
            pair_errors.append('attachment_ownership_incomplete_or_ambiguous')
        owner_indices = [attachment['body_owners'][0]
                         if len(attachment['body_owners']) == 1 else None
                         for attachment in pair]
        if set(owner_indices) != {0, 1}:
            pair_errors.append('marker_owners_do_not_partition_bodies')
        normal0, normal1 = (tuple(attachment['inward_normal']) for attachment in pair)
        if normal0 != (-normal1[0], -normal1[1]):
            pair_errors.append('attachment_normals_not_opposed')
        for source_index in (0, 1):
            dest_index = 1 - source_index
            alternative = {'pair_index': pair_index, 'source_marker_index': source_index,
                           'dest_marker_index': dest_index, 'attachments': list(pair),
                           'moving_body_index': owner_indices[source_index],
                           'fixed_body_index': owner_indices[dest_index],
                           'errors': list(pair_errors), 'output': None}
            record['alternatives'].append(alternative)
            if pair_errors:
                continue
            source, dest = markers[source_index], markers[dest_index]
            dr, dc = pair[source_index]['inward_normal']
            vector = (dest['bbox'][0] - source['bbox'][0] - dr,
                      dest['bbox'][1] - source['bbox'][1] - dc)
            alternative['translation_vector'] = list(vector)
            attached = {tuple(cell) for cell in pair[source_index]['footprint']}
            dest_attached = {tuple(cell) for cell in pair[dest_index]['footprint']}
            if (_shift(attached, vector) != dest['cells']
                    or _shift(source['cells'], vector) != dest_attached):
                alternative['errors'].append('reciprocal_marker_footprint_mismatch')
            moved = _shift(bodies[owner_indices[source_index]], vector)
            fixed = bodies[owner_indices[dest_index]]
            overlap = moved & fixed
            if overlap:
                alternative['errors'].append('target_pixels_overlap')
                alternative['overlap_cells'] = _cells(overlap)
            assembled = moved | fixed
            if len(assembled) != len(all_target):
                alternative['errors'].append('target_pixel_count_changed')
            output, bbox = old.tight_render(assembled, background, target)
            alternative.update({'output': output, 'output_bbox': list(bbox),
                                'output_shape': [len(output), len(output[0])],
                                'output_target_pixels': len(assembled)})
            if not valid_grid(output):
                alternative['errors'].append('raw_candidate_out_of_arc_bounds')
            outputs.append(output)
    if any(alternative['errors'] for alternative in record['alternatives']):
        return hold('invalid_complete_alternative')
    if not outputs:
        return hold('no_complete_alternative')
    if any(output != outputs[0] for output in outputs[1:]):
        return hold('complete_alternative_grids_disagree')
    record['certificate'] = {'complete_pairs': len(record['alternatives']) // 2,
                             'reciprocal_candidates': len(outputs),
                             'distinct_complete_grids': 1,
                             'target_pixels_preserved': len(all_target)}
    return outputs[0], record

