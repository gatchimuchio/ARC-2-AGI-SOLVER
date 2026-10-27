"""全出力座標の所有と元格子同値を証明する象限配色教材。"""
from __future__ import annotations
from collections import Counter
from .既存象限配色 import _quadrant_template_palette_render

def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(value) is int and 0 <= value <= 9 for value in row)
                    for row in grid))

def guarded_render(grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    side = len(grid)
    if side != len(grid[0]) or side < 2 or side % 2:
        return None, {'failure': 'requires_even_square'}
    n = side // 2
    tl = [[grid[r][c] for c in range(n)] for r in range(n)]
    tr = [[grid[r][n+c] for c in range(n)] for r in range(n)]
    palette = [[grid[n+r][c] for c in range(n)] for r in range(n)]
    template = [[grid[n+r][n+c] for c in range(n)] for r in range(n)]
    height = sum(value != 0 for row in tl for value in row)
    width = sum(value != 0 for row in tr for value in row)
    base = {'quadrant_side': n, 'extent_counts': [height, width],
            'extent_zero_counts': [n*n-height, n*n-width]}
    if not (1 <= height <= 30 and 1 <= width <= 30):
        return None, {**base, 'failure': 'output_extent_outside_arc'}
    template_blank = all(value == 0 for row in template for value in row)
    palette_uniform = len({value for row in palette for value in row}) == 1
    mode = ('blank_template_payload' if template_blank else
            'scalar_palette' if palette_uniform else 'cellwise_payload')
    output = []
    counts = Counter()
    palette_positions = set()
    template_positions = set()
    for row in range(height):
        output_row = []
        for column in range(width):
            tile_r, within_r = divmod(row, n)
            tile_c, within_c = divmod(column, n)
            if not template_blank and template[within_r][within_c] != 0:
                value = template[within_r][within_c]
                template_positions.add((within_r, within_c))
                counts['template'] += 1
            else:
                pr, pc = ((within_r, within_c) if template_blank
                          else (tile_r % n, tile_c % n))
                if not (0 <= pr < n and 0 <= pc < n):
                    return None, {**base, 'failure': 'palette_index_outside'}
                value = palette[pr][pc]
                palette_positions.add((pr, pc))
                counts['palette'] += 1
            output_row.append(value)
        output.append(output_row)
    if sum(counts.values()) != height * width or not valid_grid(output):
        return None, {**base, 'failure': 'output_coverage_invalid'}
    expected_record = {
        'renderer_case': 'quadrant_template_palette_tiler',
        'quadrant_template_size': n,
        'quadrant_template_output_shape': [height, width],
        'quadrant_template_payload_mode': mode,
    }
    original, original_record = _quadrant_template_palette_render(grid)
    if original is None:
        return None, {**base, 'failure': 'original_renderer_failed',
                      'raw_record': original_record}
    if original != output:
        return None, {**base, 'failure': 'original_grid_disagrees'}
    if original_record != expected_record:
        return None, {**base, 'failure': 'original_record_disagrees'}
    if original == grid:
        return None, {**base, 'failure': 'original_no_change'}
    record = {**base, 'raw_record': original_record,
              'template_blank': template_blank, 'palette_uniform': palette_uniform,
              'template_nonzero_cells': sum(v != 0 for row in template for v in row),
              'output_cells': height * width,
              'template_owned_output_cells': counts['template'],
              'palette_owned_output_cells': counts['palette'],
              'independent_formula_palette_positions': [list(v) for v in sorted(palette_positions)],
              'template_positions_used': [list(v) for v in sorted(template_positions)],
              'original_palette_positions': ([[0, 0]] if mode == 'scalar_palette' and counts['palette']
                                             else [list(v) for v in sorted(palette_positions)]),
              'output_color_counts': [[color, count] for color, count in sorted(Counter(v for row in output for v in row).items())]}
    return original, record

def fit_teachers(train):
    if not isinstance(train, list) or len(train) < 2:
        return None, {'failure': 'too_few_teachers'}
    if any(not isinstance(pair, dict) or not valid_grid(pair.get('input'))
           or not valid_grid(pair.get('output')) for pair in train):
        return None, {'failure': 'invalid_teachers'}
    inputs = [tuple(map(tuple, pair['input'])) for pair in train]
    if len(set(inputs)) != len(inputs):
        return None, {'failure': 'duplicate_teacher_inputs'}
    raw_records = []
    for pair in train:
        output, record = _quadrant_template_palette_render(pair['input'])
        raw_records.append({'exact': output == pair['output'], 'record': record})
    if not all(row['exact'] for row in raw_records):
        return None, {'failure': 'raw_teacher_mismatch', 'raw_records': raw_records}
    teacher_records = []
    for pair in train:
        output, record = guarded_render(pair['input'])
        teacher_records.append(record)
        if output != pair['output']:
            return None, {'failure': 'teacher_certificate_failed',
                          'raw_records': raw_records, 'teacher_records': teacher_records}
    return {'renderer': 'quadrant_template_palette_tiler'}, {
        'raw_records': raw_records, 'teacher_records': teacher_records}

class 象限配色教材:
    def __init__(self, 教師群):
        model, _ = fit_teachers(教師群)
        self.適合 = model is not None

    def 候補(self, 格子, _policy):
        if not self.適合:
            return None, {"failure": "全教師を再現する四象限符号なし"}
        return guarded_render(格子)

    def 記録(self):
        return {"全教師の符号再現": self.適合}
