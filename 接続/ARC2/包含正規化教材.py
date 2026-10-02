"""Certify component identity and containment under the old canonical layout."""
from collections import Counter
from . import 既存包含正規化 as old


def certified_external_axis(component, root, axis):
    index = 0 if axis == 'row' else 1
    size = root['render_height'] if axis == 'row' else root['render_width']
    interval = (component['bbox'][index], component['bbox'][index + 2])
    root_interval = (root['bbox'][index], root['bbox'][index + 2])
    if interval[1] < root_interval[0]:
        expected = (-2, 'before')
    elif interval[0] > root_interval[1]:
        expected = (size + 1, 'after')
    else:
        groups = [g for g in root['axis_groups'][axis]
                  if old.intervals_overlap(interval, g['interval'])]
        if groups:
            keys = [(abs(sum(g['interval']) - sum(interval)),
                     g['interval'][1] - g['interval'][0]) for g in groups]
            minimum = min(keys)
            if keys.count(minimum) != 1:
                return None
            expected = (groups[keys.index(minimum)]['output_center'], 'aligned')
        else:
            expected = ((size - 1) // 2, 'root_center')
    return expected if old.map_external_axis(component, root, axis) == expected else None


def guarded_render(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row) for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    counts = Counter(v for row in grid for v in row)
    if sum(n == max(counts.values()) for n in counts.values()) != 1:
        return None, {'failure': 'background_tie'}
    background = old.dominant_color(grid)
    colors = old.foreground_colors(grid, background)
    if len(colors) != 1:
        return None, {'failure': 'not_single_foreground_color'}
    foreground = colors[0]
    components = old.foreground_components(grid, background)
    if not 2 <= len(components) <= 8:
        return None, {'failure': 'component_count_out_of_range'}
    ids = {c['id'] for c in components}
    source_cells = {(r, c) for r, row in enumerate(grid) for c, v in enumerate(row) if v != background}
    union = set().union(*(c['cells'] for c in components))
    if (len(ids) != len(components) or union != source_cells
            or sum(len(c['cells']) for c in components) != len(union)):
        return None, {'failure': 'input_component_coverage_invalid'}
    expected_parents, containment = {}, set()
    for child in components:
        containers = [c for c in components if c['id'] != child['id']
                      and old.bbox_contains(c['bbox'], child['bbox'])]
        for i, left in enumerate(containers):
            for right in containers[i + 1:]:
                if not (old.bbox_contains(left['bbox'], right['bbox'])
                        or old.bbox_contains(right['bbox'], left['bbox'])):
                    return None, {'failure': 'containers_not_strict_chain'}
        containment.update((c['id'], child['id']) for c in containers)
        expected_parents[child['id']] = (min(containers,
            key=lambda c: (c['height'] * c['width'], c['size']))['id'] if containers else None)
    components = old.build_containment_tree(components)
    by_id = {c['id']: c for c in components}
    if any(c['parent'] != expected_parents[c['id']]
           or sorted(c['children']) != sorted(i for i, parent in expected_parents.items() if parent == c['id'])
           for c in components):
        return None, {'failure': 'source_parent_or_children_disagree'}
    roots = [c for c in components if c['parent'] is None]
    frame_roots = [c for c in roots if c['children']]
    if len(frame_roots) != 1:
        return None, {'failure': 'expected_one_root_frame'}
    root = old.render_node(frame_roots[0]['id'], by_id, background, foreground)
    placements = {}

    def trace(node_id, top, left):
        if node_id in placements:
            return False
        node = by_id[node_id]
        height, width = node['render_height'], node['render_width']
        if height < 1 or width < 1:
            return False
        placements[node_id] = ({(top + r, left + c) for r in range(height) for c in range(width)
                                if r in (0, height - 1) or c in (0, width - 1)}
                               if node['children'] else {(top, left)})
        for child_id in node['children']:
            row, col = node['child_positions'][child_id]
            if not trace(child_id, top + row, left + col):
                return False
        return True

    if not trace(root['id'], 0, 0):
        return None, {'failure': 'canonical_component_coverage_invalid'}
    external_records = []
    min_row = min_col = 0
    max_row, max_col = root['render_height'] - 1, root['render_width'] - 1
    for component in roots:
        if component['id'] == root['id']:
            continue
        row_result = certified_external_axis(component, root, 'row')
        col_result = certified_external_axis(component, root, 'col')
        if row_result is None or col_result is None:
            return None, {'failure': 'external_axis_tie_or_source_disagrees'}
        row, row_relation = row_result
        col, col_relation = col_result
        if component['id'] in placements:
            return None, {'failure': 'canonical_component_coverage_invalid'}
        placements[component['id']] = {(row, col)}
        external_records.append({'component_id': component['id'], 'output_cell': [row, col],
                                 'row_relation': row_relation, 'col_relation': col_relation})
        if row < 0:
            min_row = min(min_row, row - 1)
        if col < 0:
            min_col = min(min_col, col - 1)
        if row > max_row:
            max_row = max(max_row, row + 1)
        if col > max_col:
            max_col = max(max_col, col + 1)
    if set(placements) != ids:
        return None, {'failure': 'canonical_component_coverage_invalid'}
    output_height, output_width = max_row - min_row + 1, max_col - min_col + 1
    if not (1 <= output_height <= 30 and 1 <= output_width <= 30
            and output_height < len(grid) and output_width < len(grid[0])):
        return None, {'failure': 'canonical_output_size_invalid'}
    owners, canonical_boxes = {}, {}
    for component_id, cells in placements.items():
        for row, col in cells:
            if not (min_row <= row <= max_row and min_col <= col <= max_col):
                return None, {'failure': 'canonical_component_out_of_bounds'}
            if (row, col) in owners:
                return None, {'failure': 'canonical_components_overlap'}
            owners[row, col] = component_id
        canonical_boxes[component_id] = (min(r for r, _ in cells), min(c for _, c in cells),
                                          max(r for r, _ in cells), max(c for _, c in cells))
    for (row, col), owner in owners.items():
        for dr, dc in old.NEIGHBORS_4:
            adjacent = owners.get((row + dr, col + dc))
            if adjacent is not None and adjacent != owner:
                return None, {'failure': 'canonical_components_touch'}
    canonical_containment = {(i, j) for i in ids for j in ids if i != j
                             and old.bbox_contains(canonical_boxes[i], canonical_boxes[j])}
    if canonical_containment != containment:
        return None, {'failure': 'canonical_containment_disagrees'}
    expected = [[background] * output_width for _ in range(output_height)]
    for row, col in owners:
        expected[row - min_row][col - min_col] = foreground
    expected_record = {'background': background, 'foreground': foreground,
        'input_shape': [len(grid), len(grid[0])], 'output_shape': [output_height, output_width],
        'component_count': len(components),
        'components': [old.serializable_component(c) for c in components],
        'root_component_id': root['id'],
        'root_render_shape': [root['render_height'], root['render_width']],
        'root_axis_groups': {axis: [{'interval': list(g['interval']), 'output_center': g['output_center']}
                                    for g in groups] for axis, groups in root['axis_groups'].items()},
        'external_placements': external_records}
    output, source_record = old.render_nested_frame_inventory(grid)
    if output != expected or source_record != expected_record:
        return None, {'failure': 'source_output_or_record_disagrees'}
    return output, {'source_record': source_record, 'certificate': {
        'physical_components': len(components), 'canonical_components': len(placements),
        'strict_containment_pairs': len(containment), 'external_components': len(external_records),
        'input_foreground_cells': len(source_cells), 'output_foreground_cells': len(owners)}}


def fit_guarded(teachers):
    if not teachers or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
        return False
    if not all(old.render_nested_frame_inventory(p['input'])[0] == p['output'] for p in teachers):
        return False
    return all(guarded_render(p['input'])[0] == p['output'] for p in teachers)


class 包含正規化教材:
    def __init__(self, 教師群):
        self.適合 = fit_guarded(教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する包含正規化なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師再現": self.適合}
