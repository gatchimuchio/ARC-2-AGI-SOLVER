"""元の最大成分選択と色modeを保ち、BG/main同率と内部prototypeを保留する。"""
from collections import Counter
from .既存形状色転写 import connected_components_for_colors, render_template_hole_shape_recolorer


def guarded_template_shape_color(grid):
    if not grid or not grid[0] or len(grid) > 30 or len(grid[0]) > 30 or any(len(row) != len(grid[0]) for row in grid):
        return None, {'failure': 'invalid_grid'}
    counts = Counter(v for row in grid for v in row)
    backgrounds = [v for v, n in counts.items() if n == max(counts.values())]
    if len(backgrounds) != 1:
        return None, {'failure': 'background_tie'}
    background = backgrounds[0]
    components = connected_components_for_colors(grid, set(counts) - {background})
    if not components:
        return None, {'failure': 'no_template_components'}
    largest_size = max(len(component['cells']) for component in components)
    largest = [component for component in components if len(component['cells']) == largest_size]
    if len(largest) != 1:
        return None, {'failure': 'largest_template_size_tie'}
    main = largest[0]
    row0, col0, row1, col1 = main['bbox']
    prototypes = [component for component in components if component is not main]
    if any(row0 <= row <= row1 and col0 <= col <= col1 for component in prototypes for row, col in component['cells']):
        return None, {'failure': 'prototype_enters_selected_template_bbox'}
    output, record = render_template_hole_shape_recolorer(grid)
    if output is None:
        return None, record
    if (len(output), len(output[0])) != (row1 - row0 + 1, col1 - col0 + 1):
        return None, {'failure': 'template_output_shape_mismatch'}
    if any(output[row - row0][col - col0] != grid[row][col] for row, col in main['cells']):
        return None, {'failure': 'template_foreground_changed'}
    return output, {**record, 'prototype_component_count': len(prototypes), 'selected_template_pixels': largest_size}


class 形状色教材:
    def __init__(self, 教師群):
        self.全教師再現 = False
        if not 教師群 or len({tuple(map(tuple, p['input'])) for p in 教師群}) != len(教師群):
            return
        self.全教師再現 = all(guarded_template_shape_color(p['input'])[0] == p['output'] for p in 教師群)

    def 候補(self, 格子, _policy):
        if not self.全教師再現:
            return None, {'failure': '全教師を再現する形状色転写なし'}
        return guarded_template_shape_color(格子)

    def 記録(self):
        return {'全教師再現': self.全教師再現}
