"""Column-scan reconstruction oracle and predeclared fixtures, no model imports."""
import copy
import json
from itertools import product
from pathlib import Path

HERE = Path(__file__).resolve().parent


def oracle(grid):
    if (not isinstance(grid, list) or not 1 <= len(grid) <= 30
            or not isinstance(grid[0], list) or not 1 <= len(grid[0]) <= 30
            or any(not isinstance(line, list) or len(line) != len(grid[0])
                   or any(type(v) is not int or not 0 <= v <= 9 for v in line)
                   for line in grid)):
        return None, []
    h, w = len(grid), len(grid[0])
    palette = sorted({v for line in grid for v in line})
    counts = {v: sum(x == v for line in grid for x in line) for v in palette}
    backgrounds = [v for v in palette if counts[v] == max(counts.values())]
    if len(backgrounds) != 1:
        return None, []
    bg = backgrounds[0]
    xs = [x for y in range(h) for x in range(w) if grid[y][x] != bg]
    if not xs:
        return None, []
    left, right = min(xs), max(xs)
    roles = []
    for row in range(1, h - 1):
        for axis in [v for v in palette if v != bg]:
            if (grid[row].count(axis) < 3
                    or bg in grid[row][left:right + 1]
                    or any(grid[y][x] == axis for y in range(h) if y != row for x in range(w))):
                continue
            slots, intervals, valid = [], [], True
            col = left
            while col <= right:
                if grid[row][col] == axis:
                    col += 1
                    continue
                color, start = grid[row][col], col
                while col < right and grid[row][col + 1] == color:
                    col += 1
                end = col
                column_intervals = []
                for x in range(start, end + 1):
                    ys = [y for y in range(h) if grid[y][x] != bg]
                    if (any(grid[y][x] != color for y in ys)
                            or ys != list(range(min(ys), max(ys) + 1))):
                        valid = False
                    column_intervals.append(tuple(y - row for y in ys))
                if any(fp != column_intervals[0] for fp in column_intervals):
                    valid = False
                slots.append((start, end, color))
                intervals.append(column_intervals[0])
                col += 1
            if not valid or len(slots) < 3:
                continue
            def build(fps):
                result = [[bg] * w for _ in range(h)]
                for x in range(w):
                    if grid[row][x] == axis:
                        result[row][x] = axis
                for (start, end, color), fp in zip(slots, fps):
                    for dy in fp:
                        for x in range(start, end + 1):
                            result[row + dy][x] = color
                return result
            if build(intervals) != grid:
                continue
            sorted_intervals = sorted(intervals, key=lambda fp: (len(fp), fp[0], fp[-1]))
            roles.append({'axis_row': row, 'axis_color': axis, 'background': bg,
                          'extent': [left, right], 'tokens': slots,
                          'original_footprints': intervals, 'sorted_footprints': sorted_intervals,
                          'status': 'no_op' if intervals == sorted_intervals else 'success',
                          'output': build(sorted_intervals)})
    if not roles or any(role['status'] != 'success' for role in roles):
        return None, roles
    if any(role['output'] != roles[0]['output'] for role in roles):
        return None, roles
    return roles[0]['output'], roles


def construct(config, sorted_intervals=False):
    h, w, row, bg, axis = (config[k] for k in ('h', 'w', 'row', 'bg', 'axis'))
    grid = [[bg] * w for _ in range(h)]
    for x in range(config['extent'][0], config['extent'][1] + 1):
        grid[row][x] = axis
    intervals = list(config['intervals'])
    if sorted_intervals:
        intervals.sort(key=lambda fp: (fp[1] - fp[0] + 1, fp[0], fp[1]))
    for (left, right, color), (lo, hi) in zip(config['slots'], intervals):
        for y in range(row + lo, row + hi + 1):
            for x in range(left, right + 1):
                grid[y][x] = color
    return grid


def fixture_cases():
    spec = json.loads((HERE / 'fixtures.json').read_text())
    base, cases, positives = spec['base'], [], {}
    def positive(name, changes, category='constructed_domain'):
        config = dict(base, **changes)
        grid, expected = construct(config), construct(config, sorted_intervals=True)
        case = {'name': name, 'input': grid, 'expected_output': expected if expected != grid else None,
                'category': category, 'config': config}
        cases.append(case)
        positives[name] = case
    for case in spec['positive_variants']:
        positive(case['name'], case['changes'])
    sweep = spec['bounded_combinations']
    for i, intervals in enumerate(product(sweep['interval_options'], repeat=sweep['product_repeat'])):
        positive('%s_%02d' % (sweep['name_prefix'], i), {'slots': sweep['slots'], 'intervals': intervals}, 'bounded_product')
    for transform in spec['transforms']:
        target = positives[transform['target']]
        if transform['name'] == 'palette_shift':
            for shift in transform['values']:
                remap = lambda g: [[(v + shift) % 10 for v in line] for line in g]
                cases.append({'name': 'palette_shift_%d' % shift, 'input': remap(target['input']),
                              'expected_output': remap(target['expected_output']), 'category': 'palette_bijection'})
        elif transform['name'] == 'vertical_shift':
            for shift in transform['values']:
                positive('vertical_shift_%+d' % shift, dict(target['config'], row=target['config']['row'] + shift), 'translation')
        else:
            cfg = copy.deepcopy(target['config'])
            cfg['slots'] = [[cfg['w'] - 1 - r, cfg['w'] - 1 - l, color]
                            for l, r, color in reversed(cfg['slots'])]
            cfg['intervals'] = list(reversed(cfg['intervals']))
            cfg['extent'] = [cfg['w'] - 1 - cfg['extent'][1], cfg['w'] - 1 - cfg['extent'][0]]
            positive(transform['name'], cfg, 'fresh_directional_sort')
    for case in spec['negative_variants']:
        cfg = dict(base, **case.get('changes', {}))
        grid = copy.deepcopy(case['literal']) if 'literal' in case else construct(cfg)
        for y, x, color in case.get('edits', []):
            grid[y][x] = color
        if case.get('operation') == 'transpose':
            grid = list(map(list, zip(*grid)))
        cases.append({'name': case['name'], 'input': grid, 'expected_output': None, 'category': 'declared_negative'})
    for case in spec['ambiguities']:
        grid = [[0] * len(case['axis_row']) for _ in range(case['h'])]
        grid[case['row']] = list(case['axis_row'])
        for col, top, bottom, color in case['extensions']:
            for row in range(top, bottom + 1):
                grid[row][col] = color
        expected = None
        if case['outcome'] == 'EMIT':
            expected = copy.deepcopy(grid)
            expected[2][6] = expected[6][6] = 0
            expected[2][7] = expected[6][7] = 4
        cases.append({'name': case['name'], 'input': grid, 'expected_output': expected,
                      'category': 'all_role_aggregation', 'role_expectation': case})
    invalid = {'empty': [], 'empty_row': [[]], 'ragged': [[0, 0], [0]], 'bool': [[True]],
               'float': [[0.0]], 'negative': [[-1]], 'large_color': [[10]],
               'height31': [[0]] * 31, 'width31': [[0] * 31], 'outer_tuple': ((0,),), 'row_tuple': [(0,)]}
    for name in spec['arc_invalid']:
        cases.append({'name': 'invalid_' + name, 'input': invalid[name], 'expected_output': None,
                      'category': 'arc_envelope'})
    return cases
