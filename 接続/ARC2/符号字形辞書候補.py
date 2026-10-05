"""Teacher-fitted sparse command dictionary. No dataset I/O or HDS dependencies."""
from collections import Counter
from itertools import product

# Inject direct existing helper functions at construction, without importing HDS.
class Grammar:
    def __init__(self, valid_grid, color_components):
        self.valid_grid = valid_grid
        self.components = color_components

    def mode(self, grid):
        counts = Counter(v for row in grid for v in row)
        modes = [v for v, n in counts.items() if n == max(counts.values())]
        return modes[0] if len(modes) == 1 else None

    def parse(self, grid, bg, keys, shape, anchor, corner):
        if not self.valid_grid(grid):
            return None, {'failure': 'invalid_grid'}
        if self.mode(grid) != bg:
            return None, {'failure': 'background_mismatch_or_tie'}
        height, width = len(grid), len(grid[0])
        gh, gw = shape
        tokens = {(r, c): v for r, row in enumerate(grid)
                  for c, v in enumerate(row) if v in keys}
        payload = sorted({v for row in grid for v in row} - {bg} - set(keys))
        samples, sample_boxes, sample_pixels, labels = [], set(), set(), set()
        for color in payload:
            for component in self.components(grid, color, include_diagonal=True):
                top, left, bottom, right = component['bbox']
                found_shape = (bottom-top+1, right-left+1)
                if component['size'] < 2 or found_shape != tuple(shape):
                    return None, {'failure': 'payload_not_glyph', 'color': color,
                                  'bbox': component['bbox'], 'size': component['size'],
                                  'expected_shape': shape}
                box = {(r, c) for r in range(top, bottom+1)
                       for c in range(left, right+1)}
                if box & sample_boxes:
                    return None, {'failure': 'sample_rectangles_overlap'}
                sample_boxes.update(box)
                label = (top-1 if corner[0] < 0 else bottom+1,
                         left-1 if corner[1] < 0 else right+1)
                if label not in tokens:
                    return None, {'failure': 'sample_label_missing', 'label': label}
                if label in labels:
                    return None, {'failure': 'sample_label_shared', 'label': label}
                labels.add(label)
                cells = component['cells']
                sample_pixels.update(cells)
                tile = tuple(tuple(color if (r, c) in cells else bg
                                   for c in range(left, right+1))
                             for r in range(top, bottom+1))
                samples.append({'label': label, 'key': tokens[label],
                                'origin': (top, left), 'tile': tile})
        # Every foreground cell is either sample paint or a key token.
        foreground = {(r, c) for r, row in enumerate(grid)
                      for c, v in enumerate(row) if v != bg}
        if sample_pixels & set(tokens) or sample_pixels | set(tokens) != foreground:
            return None, {'failure': 'foreground_ownership_failed'}
        commands, rectangles = [], set()
        for (r, c), key in sorted(tokens.items()):
            if (r, c) in labels:
                continue
            top, left = r-anchor[0], c-anchor[1]
            if top < 0 or left < 0 or top+gh > height or left+gw > width:
                return None, {'failure': 'command_out_of_bounds',
                              'token': (r, c), 'origin': (top, left)}
            box = {(y, x) for y in range(top, top+gh)
                   for x in range(left, left+gw)}
            if box & rectangles:
                return None, {'failure': 'command_rectangles_overlap',
                              'token': (r, c), 'overlap': sorted(box & rectangles)}
            rectangles.update(box)
            commands.append({'token': (r, c), 'key': key, 'origin': (top, left)})
        if not commands:
            return None, {'failure': 'no_commands'}
        parsed = {'samples': samples, 'commands': commands}
        return parsed, {'samples': samples, 'commands': commands,
                        'input_foreground': len(foreground),
                        'sample_pixels': len(sample_pixels),
                        'label_count': len(labels),
                        'command_rectangles_cells': len(rectangles)}

    def glyph_valid(self, tile, bg, keys):
        colors = {v for row in tile for v in row} - {bg}
        if len(colors) != 1 or colors & set(keys):
            return False
        parts = self.components([list(row) for row in tile], next(iter(colors)),
                                include_diagonal=True)
        return (len(parts) == 1 and parts[0]['size'] >= 2 and
                parts[0]['bbox'] == (0, 0, len(tile)-1, len(tile[0])-1))

    def render(self, grid, model):
        bg, shape, anchor, corner, entries = model
        dictionary = dict(entries)
        parsed, record = self.parse(grid, bg, dictionary, shape, anchor, corner)
        if parsed is None:
            return None, record
        for sample in parsed['samples']:
            if dictionary[sample['key']] != sample['tile']:
                return None, {**record, 'failure': 'sample_dictionary_mismatch',
                              'key': sample['key']}
        output = [[bg]*len(grid[0]) for _ in grid]
        for command in parsed['commands']:
            top, left = command['origin']
            for r, row in enumerate(dictionary[command['key']]):
                for c, value in enumerate(row):
                    output[top+r][left+c] = value
        return output, {**record,
                        'output_foreground': sum(v != bg for row in output for v in row),
                        'output_counts': sorted(Counter(v for row in output for v in row).items()),
                        'checked_output_cells': len(grid)*len(grid[0])}

    def fit(self, teachers, sink=None):
        if (len(teachers) < 2 or any(not self.valid_grid(p.get('input')) or
                                    not self.valid_grid(p.get('output')) for p in teachers)):
            return (), {'failure': 'insufficient_or_invalid_teachers'}
        if len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers):
            return (), {'failure': 'duplicate_teacher_inputs'}
        if any((len(p['input']), len(p['input'][0])) !=
               (len(p['output']), len(p['output'][0])) for p in teachers):
            return (), {'failure': 'output_shape_changed'}
        backgrounds = {self.mode(p['input']) for p in teachers}
        if None in backgrounds or len(backgrounds) != 1:
            return (), {'failure': 'background_not_shared_unique_mode'}
        bg = next(iter(backgrounds))
        input_colors = {v for p in teachers for row in p['input'] for v in row}
        output_colors = {v for p in teachers for row in p['output'] for v in row}
        keys = tuple(sorted(input_colors - output_colors - {bg}))
        if not keys:
            return (), {'failure': 'no_disjoint_command_keys'}
        models, reasons, count = [], Counter(), 0
        max_h = min(len(p['input']) for p in teachers)
        max_w = min(len(p['input'][0]) for p in teachers)
        for gh, gw in product(range(1, max_h+1), range(1, max_w+1)):
            for ar, ac, dr, dc in product(range(gh), range(gw), (-1, 1), (-1, 1)):
                shape, anchor, corner = (gh, gw), (ar, ac), (dr, dc)
                count += 1
                parsed_returns = [self.parse(p['input'], bg, keys, shape, anchor, corner)
                                  for p in teachers]
                returns = [{'parsed': parsed, 'parse_record': record,
                            'output': None, 'render_record': None}
                           for parsed, record in parsed_returns]
                hypothesis = {'shape': shape, 'anchor': anchor, 'label_corner': corner,
                              'keys': keys, 'teacher_returns': returns}
                failures = [r['failure'] for parsed, r in parsed_returns if parsed is None]
                dictionary, extraction = {}, []
                if not failures:
                    for ti, (p, (parsed, _)) in enumerate(zip(teachers, parsed_returns)):
                        for command in parsed['commands']:
                            top, left = command['origin']
                            tile = tuple(tuple(row[left:left+gw])
                                         for row in p['output'][top:top+gh])
                            key = command['key']
                            reason = None
                            if not self.glyph_valid(tile, bg, keys):
                                reason = 'output_tile_not_tight_connected_glyph'
                            elif key in dictionary and dictionary[key] != tile:
                                reason = 'same_key_tile_conflict'
                            extraction.append({'teacher': ti, 'command': command,
                                               'tile': tile, 'failure': reason})
                            if reason:
                                failures.append(reason)
                            else:
                                dictionary[key] = tile
                    hypothesis['tile_extraction_returns'] = extraction
                    if set(dictionary) != set(keys):
                        failures.append('key_without_command_example')
                if not failures:
                    model = (bg, shape, anchor, corner, tuple(sorted(dictionary.items())))
                    for ti, p in enumerate(teachers):
                        output, record = self.render(p['input'], model)
                        returns[ti].update(output=output, render_record=record,
                                           teacher_equal=output == p['output'])
                        if output != p['output']:
                            failures.append(record.get('failure', 'whole_teacher_mismatch'))
                    hypothesis['model'] = model
                    if not failures:
                        models.append(model)
                hypothesis.update(accepted=not failures, failures=failures)
                reasons.update(set(failures))
                if sink:
                    sink(hypothesis)
        return tuple(models), {'exhausted': True, 'hypotheses': count,
                               'models': len(models), 'background': bg, 'keys': keys,
                               'rejections_by_reason': dict(reasons)}

    def consensus(self, grid, models):
        returns = [self.render(grid, model) for model in models]
        if not returns or any(output is None for output, _ in returns):
            return None, {'failure': 'one_or_more_models_failed', 'returns': returns}
        if any(output != returns[0][0] for output, _ in returns[1:]):
            return None, {'failure': 'models_disagree', 'returns': returns}
        return returns[0][0], {'returns': returns}

# Direct unchanged helper imports; no HDS dependency.
from .記号命令教材 import valid_grid
from .既存物体特徴 import color_components
