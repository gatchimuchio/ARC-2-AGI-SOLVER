"""凡例の色集合と全前景成分の集合関係を同じHDSへ渡す。"""
from __future__ import annotations
from collections import Counter
from .既存物体特徴 import color_component_dicts_for_grid
from .既存領域転写 import mixed_region_dicts_for_grid
from .既存凡例穴対応 import grid_shape, clone_grid

MODELS = tuple(relation + ':' + action
               for relation in ('intersects', 'contains', 'equals')
               for action in ('erase_matching', 'erase_nonmatching'))

def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(value) is int and 0 <= value <= 9 for value in row)
                    for row in grid))

def parse_input(grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_grid'}
    height, width = grid_shape(grid)
    raw_frames = []
    monochrome_coverage = set()
    monochrome_count = 0
    for colour in sorted({v for row in grid for v in row}):
        for component in color_component_dicts_for_grid(grid, colour, include_diagonal=False):
            cells = set(component['cells'])
            monochrome_coverage.update(cells)
            monochrome_count += len(cells)
            r0, c0, r1, c1 = component['bbox']
            if r1 == r0 or c1 == c0:
                continue
            orientations = (
                ('tl', r1, c1, r0 == 0 and c0 == 0),
                ('tr', r1, c0, r0 == 0 and c1 == width-1),
                ('bl', r0, c1, r1 == height-1 and c0 == 0),
                ('br', r0, c0, r1 == height-1 and c1 == width-1),
            )
            for corner, row_side, col_side, attached in orientations:
                expected = ({(row_side, c) for c in range(c0, c1+1)}
                            | {(r, col_side) for r in range(r0, r1+1)})
                if attached and cells == expected:
                    raw_frames.append({'colour': colour, 'bbox': [r0, c0, r1, c1],
                                       'corner': corner, 'row_side': row_side,
                                       'col_side': col_side, 'frame_cells': len(cells)})
    all_cells = {(r, c) for r in range(height) for c in range(width)}
    if monochrome_coverage != all_cells or monochrome_count != height*width:
        return None, {'failure': 'monochrome_component_coverage_invalid'}
    record = {'raw_frames': raw_frames}
    if len(raw_frames) != 1:
        return None, {**record, 'failure': 'raw_frame_unresolved'}
    frame = raw_frames[0]
    r0, c0, r1, c1 = frame['bbox']
    legend_cells = {(r, c) for r in range(r0, r1+1) for c in range(c0, c1+1)}
    interior = {(r, c) for r, c in legend_cells
                if r != frame['row_side'] and c != frame['col_side']}
    counts = Counter(grid[r][c] for r, c in interior)
    if not counts:
        return None, {**record, 'failure': 'empty_legend_interior'}
    most = max(counts.values())
    modes = sorted(colour for colour, count in counts.items() if count == most)
    record.update(interior_counts=[[c, n] for c, n in sorted(counts.items())],
                  background_candidates=modes)
    if len(modes) != 1:
        return None, {**record, 'failure': 'legend_background_tie'}
    background = modes[0]
    if background == frame['colour']:
        return None, {**record, 'failure': 'background_frame_alias'}
    palette = set(counts) - {background}
    if not palette:
        return None, {**record, 'failure': 'empty_palette'}
    record.update(background=background, palette=sorted(palette))
    objects = []
    foreground_coverage = set()
    foreground_count = 0
    inside_components = 0
    for component in mixed_region_dicts_for_grid(grid, background, include_diagonal=False):
        cells = set(component['cells'])
        foreground_coverage.update(cells)
        foreground_count += len(cells)
        inside = cells & legend_cells
        if inside and inside != cells:
            return None, {**record, 'failure': 'component_crosses_legend',
                          'component_bbox': list(component['bbox'])}
        if inside:
            inside_components += 1
        else:
            colours = {grid[r][c] for r, c in cells}
            objects.append({'cells': cells, 'colours': colours,
                            'bbox': list(component['bbox'])})
    expected_foreground = {(r, c) for r, c in all_cells if grid[r][c] != background}
    if (foreground_coverage != expected_foreground
            or foreground_count != len(expected_foreground)):
        return None, {**record, 'failure': 'mixed_component_coverage_invalid'}
    if not objects:
        return None, {**record, 'failure': 'no_outside_objects'}
    record.update(inside_components=inside_components, outside_components=len(objects),
                  outside_foreground_cells=sum(len(obj['cells']) for obj in objects),
                  preserved_legend_cells=len(legend_cells),
                  original_background_cells=height*width-len(expected_foreground))
    return {'background': background, 'palette': palette, 'objects': objects,
            'legend_cells': legend_cells}, record

def render_model(grid, model):
    if type(model) is not str or model not in MODELS:
        return None, {'failure': 'unknown_model'}
    parsed, record = parse_input(grid)
    if parsed is None:
        return None, record
    relation, action = model.split(':')
    palette = parsed['palette']
    background = parsed['background']
    output = clone_grid(grid)
    removed = set()
    objects = []
    for obj in parsed['objects']:
        colours = obj['colours']
        match = (bool(colours & palette) if relation == 'intersects' else
                 palette <= colours if relation == 'contains' else palette == colours)
        erase = match if action == 'erase_matching' else not match
        if erase:
            removed.update(obj['cells'])
        objects.append({'bbox': obj['bbox'], 'size': len(obj['cells']),
                        'colours': sorted(colours), 'match': match, 'erase': erase})
    for r, c in removed:
        output[r][c] = background
    if any(output[r][c] != value for r, row in enumerate(grid) for c, value in enumerate(row)
           if (r, c) not in removed):
        return None, {**record, 'failure': 'unselected_cell_changed'}
    if removed & parsed['legend_cells']:
        return None, {**record, 'failure': 'legend_changed'}
    changed = sum(output[r][c] != value for r, row in enumerate(grid) for c, value in enumerate(row))
    if changed != len(removed):
        return None, {**record, 'failure': 'removal_count_mismatch'}
    return output, {**record, 'model': model, 'objects': objects,
                    'removed_cells': len(removed),
                    'retained_outside_foreground_cells': record['outside_foreground_cells']-len(removed)}

def consensus(grid, models):
    if (not isinstance(models, (list, tuple)) or not models
            or any(type(model) is not str or model not in MODELS for model in models)
            or len(set(models)) != len(models)):
        return None, {'failure': 'invalid_models'}
    outputs = []
    rows = []
    for model in models:
        output, record = render_model(grid, model)
        rows.append({'model': model, 'record': record})
        if output is None:
            return None, {'failure': 'retained_model_unresolved', 'models': rows}
        outputs.append(output)
    if any(output != outputs[0] for output in outputs[1:]):
        return None, {'failure': 'retained_model_grids_disagree', 'models': rows}
    if outputs[0] == grid:
        return None, {'failure': 'no_change', 'models': rows}
    return outputs[0], {'models': rows, 'agreed_models': len(models)}

def fit_models(train):
    if not isinstance(train, list) or len(train) < 2:
        return None, {'failure': 'too_few_teachers'}
    if any(not isinstance(pair, dict) or not valid_grid(pair.get('input'))
           or not valid_grid(pair.get('output')) for pair in train):
        return None, {'failure': 'invalid_teachers'}
    inputs = [tuple(map(tuple, pair['input'])) for pair in train]
    if len(set(inputs)) != len(inputs):
        return None, {'failure': 'duplicate_teacher_inputs'}
    models = []
    model_records = []
    for model in MODELS:
        teachers = []
        for pair in train:
            output, record = render_model(pair['input'], model)
            teachers.append({'exact': output == pair['output'], 'record': record})
        exact = all(row['exact'] for row in teachers)
        model_records.append({'model': model, 'fit': exact, 'teachers': teachers})
        if exact:
            models.append(model)
    if not models:
        return None, {'failure': 'no_common_model', 'model_records': model_records}
    teacher_records = []
    for pair in train:
        output, record = consensus(pair['input'], models)
        teacher_records.append(record)
        if output != pair['output']:
            return None, {'failure': 'teacher_consensus_unresolved',
                          'model_records': model_records, 'teacher_records': teacher_records}
    return models, {'model_records': model_records, 'teacher_records': teacher_records}

class 凡例集合教材:
    def __init__(self, 教師群):
        self.モデル, _ = fit_models(教師群)

    def 候補(self, 格子, _policy):
        if self.モデル is None:
            return None, {"failure": "全教師を再現する凡例集合モデルなし"}
        return consensus(格子, self.モデル)

    def 記録(self):
        return {"全教師共通モデル": list(self.モデル or [])}
