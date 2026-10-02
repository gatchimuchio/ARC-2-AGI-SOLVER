"""最大treeとshiftの一意性・全crop同時一致を証明して元格子だけ返す。"""
from collections import Counter
from . import 既存重畳組立 as old


def maximum_overlap_offsets(left, right, background):
    best_weight = None
    offsets = []
    for dr in range(-right['height'] + 1, left['height']):
        for dc in range(-right['width'] + 1, left['width']):
            row0, col0 = max(0, dr), max(0, dc)
            row1 = min(left['height'], dr + right['height'])
            col1 = min(left['width'], dc + right['width'])
            area, foreground, exact = 0, 0, True
            for row in range(row0, row1):
                for col in range(col0, col1):
                    value = left['crop'][row][col]
                    if value != right['crop'][row - dr][col - dc]:
                        exact = False
                        break
                    area += 1
                    foreground += value != background
                if not exact:
                    break
            if not exact or foreground < 1:
                continue
            weight = (area, foreground)
            if best_weight is None or weight > best_weight:
                best_weight, offsets = weight, [(dr, dc)]
            elif weight == best_weight:
                offsets.append((dr, dc))
    return None if best_weight is None else {'weight': best_weight, 'offsets': offsets}


def path_minimum_weight(adjacency, start, goal):
    stack, seen = [(start, None)], {start}
    while stack:
        vertex, minimum = stack.pop()
        if vertex == goal:
            return minimum
        for neighbor, weight in adjacency[vertex]:
            if neighbor in seen:
                continue
            seen.add(neighbor)
            stack.append((neighbor, weight if minimum is None else min(minimum, weight)))
    return None


def guarded_overlap_mosaic(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(row, list) or len(row) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in row)
                   for row in grid)):
        return None, {'failure': 'invalid_grid'}
    counts = Counter(v for row in grid for v in row)
    backgrounds = [v for v, n in counts.items() if n == max(counts.values())]
    if len(backgrounds) != 1:
        return None, {'failure': 'background_tie'}
    background = backgrounds[0]
    components = old.extract_foreground_components(grid)
    if len(components) < 2:
        return None, {'failure': 'too_few_fragments'}
    if any(sum(v != background for row in part['crop'] for v in row) != part['size']
           for part in components):
        return None, {'failure': 'foreign_foreground_in_fragment_bbox'}
    output, record = old.overlap_mosaic_assembly(grid)
    if output is None:
        return None, record or {'failure': 'source_no_candidate'}
    positions = {int(key): tuple(value) for key, value in record['positions'].items()}
    count = len(components)
    if set(positions) != set(range(count)):
        return None, {'failure': 'source_fragment_positions_incomplete'}
    height = max(positions[i][0] + p['height'] for i, p in enumerate(components))
    width = max(positions[i][1] + p['width'] for i, p in enumerate(components))
    if not 1 <= height <= 30 or not 1 <= width <= 30:
        return None, {'failure': 'output_outside_arc_bounds'}
    if any(r < 0 or c < 0 for r, c in positions.values()):
        return None, {'failure': 'negative_normalized_position'}
    pairs = {}
    for i in range(count):
        for j in range(i + 1, count):
            info = maximum_overlap_offsets(components[i], components[j], background)
            if info is not None:
                pairs[i, j] = info
    selected, adjacency = set(), [[] for _ in components]
    for edge in record['selected_edges']:
        i, j = edge['left_index'], edge['right_index']
        key = (i, j)
        info = pairs.get(key)
        if (info is None or key in selected or len(info['offsets']) != 1
                or info['offsets'][0] != (edge['delta_row'], edge['delta_col'])):
            return None, {'failure': 'selected_edge_offset_not_unique', 'edge': edge}
        dr, dc = info['offsets'][0]
        if (positions[j][0] - positions[i][0], positions[j][1] - positions[i][1]) != (dr, dc):
            return None, {'failure': 'source_position_edge_disagreement'}
        selected.add(key)
        adjacency[i].append((j, info['weight']))
        adjacency[j].append((i, info['weight']))
    if len(selected) != count - 1 or any(path_minimum_weight(adjacency, 0, i) is None for i in range(1, count)):
        return None, {'failure': 'source_edges_not_spanning_tree'}
    unused = []
    for (i, j), info in pairs.items():
        if (i, j) in selected:
            continue
        minimum = path_minimum_weight(adjacency, i, j)
        if minimum is None or info['weight'] >= minimum:
            return None, {'failure': 'unresolved_maximum_tree', 'edge': [i, j],
                          'weight': info['weight'], 'tree_path_minimum': minimum,
                          'offsets': info['offsets']}
        unused.append({'edge': [i, j], **info, 'tree_path_minimum': minimum})
    proposals = {}
    for i, part in enumerate(components):
        row0, col0 = positions[i]
        for r, row in enumerate(part['crop']):
            for c, value in enumerate(row):
                cell = (row0 + r, col0 + c)
                if cell in proposals and proposals[cell] != value:
                    return None, {'failure': 'simultaneous_crop_conflict', 'cell': list(cell)}
                proposals[cell] = value
    simultaneous = [[background] * width for _ in range(height)]
    for (r, c), value in proposals.items():
        simultaneous[r][c] = value
    if simultaneous != output:
        return None, {'failure': 'source_output_disagrees'}
    return output, {**record, 'maximum_tree_certificate': {
        'selected_offset_counts': [1] * len(selected), 'unused_edges': unused,
        'fragment_count': count, 'primary_score': ['overlap_area', 'foreground_overlap'],
    }}


class 重畳組立教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        self.全教師再現 = all(guarded_overlap_mosaic(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する一意な重畳組立なし'}
        return guarded_overlap_mosaic(格子)

    def 記録(self):
        return {'全教師再現': self.全教師再現}
