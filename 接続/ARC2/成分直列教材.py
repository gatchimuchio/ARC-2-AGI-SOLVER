"""Certify complete component-path serialization under the fixed endpoint order."""
from collections import Counter
from . import 既存成分直列 as old


def guarded_render(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_arc_grid'}
    counts = Counter(v for row in grid for v in row)
    if sum(n == max(counts.values()) for n in counts.values()) != 1:
        return None, {'failure': 'background_tie'}
    bg = old.dominant_color(grid)
    foreground = {(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value != bg}
    if not 1 <= len(foreground) <= 30:
        return None, {'failure': 'output_height_out_of_arc_bounds'}
    components = old.same_color_components_excluding_background(grid)
    if not components:
        return None, {'failure': 'no_components'}
    owner = {}
    for index, component in enumerate(components):
        cells = component['cells']
        if (not cells or len(cells) != component['size'] or len(set(cells)) != len(cells)
                or component['bbox'] != old.component_bbox(cells)):
            return None, {'failure': 'component_record_inconsistent'}
        for cell in cells:
            if cell not in foreground or cell in owner or grid[cell[0]][cell[1]] != component['color']:
                return None, {'failure': 'component_coverage_invalid'}
            owner[cell] = index
    if set(owner) != foreground:
        return None, {'failure': 'component_coverage_incomplete'}
    adjacency = {index: set() for index in range(len(components))}
    for (r, c), index in owner.items():
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            other = owner.get((r + dr, c + dc))
            if other is not None and other != index:
                adjacency[index].add(other)
    endpoints = []
    if len(components) == 1:
        start = 0
    else:
        endpoints = [i for i, neighbors in adjacency.items() if len(neighbors) == 1]
        if len(endpoints) != 2 or any(len(n) not in (1, 2) for n in adjacency.values()):
            return None, {'failure': 'contact_graph_not_simple_path'}
        if components[endpoints[0]]['bbox'] == components[endpoints[1]]['bbox']:
            return None, {'failure': 'endpoint_geometry_tie'}
        start = min(endpoints, key=lambda i: components[i]['bbox'])
    ordered, seen = [], set()
    previous, current = None, start
    while current not in seen:
        seen.add(current)
        ordered.append(current)
        next_nodes = adjacency[current] - ({previous} if previous is not None else set())
        if not next_nodes:
            break
        if len(next_nodes) != 1:
            return None, {'failure': 'contact_graph_not_simple_path'}
        previous, current = current, next(iter(next_nodes))
    if len(seen) != len(components):
        return None, {'failure': 'contact_graph_disconnected_or_cyclic'}
    expected = [[components[i]['color']] for i in ordered for _ in range(components[i]['size'])]
    if Counter(row[0] for row in expected) != Counter(grid[r][c] for r, c in foreground):
        return None, {'failure': 'foreground_color_counts_changed'}
    output = old.panel_shape_ordering_compress(grid)
    if output is None or output != expected:
        return None, {'failure': 'source_output_disagrees'}
    return output, {'background': bg, 'components': len(components),
                    'foreground_pixels': len(foreground),
                    'endpoint_bboxes': [components[i]['bbox'] for i in endpoints],
                    'ordered_color_sizes': [[components[i]['color'], components[i]['size']] for i in ordered],
                    'output_shape': [len(output), 1]}


class 成分直列教材:
    def __init__(self, 教師群):
        self.適合 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        if not all(old.panel_shape_ordering_compress(p['input']) == p['output'] for p in 教師群):
            return
        self.適合 = all(guarded_render(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {'failure': '全教師を再現する成分path直列化なし'}
        return guarded_render(格子)

    def 記録(self):
        return {'全教師再現': self.適合}
