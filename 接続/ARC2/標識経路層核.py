"""Diagnostic path-layer composition: repair marks toggle input layer relations.
Pure explicit-role kernel; no task identities, stored answers or fit-dependent branches.
Geometry primitives are reused without edits from the frozen staged path kernel.
"""
from . import 標識経路幾何 as core
from 接続.ARC2.二軸補完教材 import valid_grid


def render(grid, background, repair, control):
    if not valid_grid(grid) or len({background, repair, control}) != 3:
        return None, {'failure': 'invalid_grid_roles'}
    original, record = core.paths(grid, background, repair, control)
    if original is None:
        return None, record
    if not all(core.complete_path(path) for path in original.values()):
        return None, {'failure': 'repaired_geometry_not_complete_simple_paths'}
    marked = {color for cell, color in record['marker_owners']}
    colors = sorted(original)
    # Learn layer relations before controls can delete their witnesses.
    relations = set()
    witnesses = []
    for i, left in enumerate(colors):
        for right in colors[i + 1:]:
            visible = set()
            observed = []
            for row, col in sorted(original[left] & original[right]):
                value = grid[row][col]
                if value in (left, right):
                    visible.add(value)
                    observed.append(((row, col), value))
            if len(visible) > 1:
                return None, {'failure': 'inconsistent_input_layer_relation',
                              'pair': (left, right), 'witnesses': observed}
            if not visible:
                continue
            above = next(iter(visible))
            below = right if above == left else left
            if left in marked and right in marked:
                return None, {'failure': 'both_intersecting_paths_marked',
                              'pair': (left, right)}
            toggled = (left in marked) != (right in marked)
            if toggled:
                above, below = below, above
            relations.add((above, below))
            witnesses.append({'pair': (left, right), 'witnesses': observed,
                              'toggled': toggled, 'above': above, 'below': below})
    # Transitive order is geometric evidence, never color-index precedence.
    for middle in colors:
        for above in colors:
            for below in colors:
                if (above, middle) in relations and (middle, below) in relations:
                    relations.add((above, below))
    if any((color, color) in relations for color in colors):
        return None, {'failure': 'cyclic_layer_relation', 'witnesses': witnesses}
    changed, controls = core.controls(grid, original, control)
    if changed is None:
        return None, controls
    if not all(core.complete_path(path) for path in changed.values()):
        return None, {'failure': 'controlled_geometry_not_complete_simple_paths'}
    footprints = controls['footprints']
    for i, left in enumerate(footprints):
        for j, right in enumerate(footprints):
            if i != j and left['color'] == right['color']:
                if set(map(tuple, left['removed'])) & set(map(tuple, right['extended'])):
                    return None, {'failure': 'control_erase_write_conflict'}
    output = [[background] * len(grid[0]) for row in grid]
    for row in range(len(grid)):
        for col in range(len(grid[0])):
            occupying = {color for color, path in changed.items() if (row, col) in path}
            if not occupying:
                continue
            if len(occupying & marked) >= 2:
                return None, {'failure': 'both_intersecting_paths_marked',
                              'cell': (row, col), 'colors': sorted(occupying & marked)}
            top = [color for color in occupying
                   if all(other == color or (color, other) in relations for other in occupying)]
            if len(top) != 1:
                return None, {'failure': 'unresolved_output_layer_relation',
                              'cell': (row, col), 'colors': sorted(occupying)}
            output[row][col] = top[0]
    return output, {**record, **controls, 'marked_paths': sorted(marked),
                    'layer_witnesses': witnesses, 'layer_relations': sorted(relations)}
