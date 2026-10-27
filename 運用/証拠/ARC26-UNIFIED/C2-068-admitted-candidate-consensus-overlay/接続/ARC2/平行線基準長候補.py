"""NEW reconstruction: resize whole parallel components from middle references.

This is newly written source, not recovered adopted072 code. The only declared
program uses all middle reference identities and all common endpoint planes.
No target is read during prediction, and no applicable interpretation is dropped.
"""
from collections import Counter

from .既存物体特徴 import color_components
from .既存疎点転写 import straight_octilinear_segment, shifted_sparse_point_mask

PROGRAM = ('spatial_middle_reference', 'all_common_endpoint_planes')
PLANES = ((1, 0), (0, 1), (1, 1), (1, -1))


def inspect_parallel_components(grid, valid_grid):
    if not valid_grid(grid):
        return None, {'failure': 'invalid_arc_grid'}
    counts = Counter(value for row in grid for value in row)
    backgrounds = [color for color, count in counts.items()
                   if count == max(counts.values())]
    if len(backgrounds) != 1:
        return None, {'failure': 'background_tie'}
    background = backgrounds[0]
    components = []
    for color in sorted(set(counts) - {background}):
        components.extend(color_components(grid, color, include_diagonal=True))
    components.sort(key=lambda component: (component['bbox'], component['color']))
    if len(components) < 2:
        return None, {'failure': 'too_few_whole_components'}
    directions = set()
    segments = []
    owned = set()
    for identity, component in enumerate(components):
        cells = component['cells']
        first, last = min(cells), max(cells)
        if straight_octilinear_segment(first, last) != cells:
            return None, {'failure': 'component_is_not_full_line', 'component': identity}
        if first != last:
            directions.add(((last[0] > first[0]) - (last[0] < first[0]),
                            (last[1] > first[1]) - (last[1] < first[1])))
        if owned & cells:
            return None, {'failure': 'component_ownership_overlap'}
        owned.update(cells)
        segments.append({'identity': identity, 'color': component['color'],
                         'cells': cells, 'start': first, 'end': last})
    foreground = {(r, c) for r, row in enumerate(grid)
                  for c, value in enumerate(row) if value != background}
    if owned != foreground:
        return None, {'failure': 'whole_foreground_not_owned'}
    if len(directions) != 1:
        return None, {'failure': 'parallel_direction_not_unique'}
    dr, dc = next(iter(directions))
    for segment in segments:
        r, c = segment['start']
        segment['position'] = -dc * r + dr * c
    positions = sorted(segment['position'] for segment in segments)
    middle_positions = {positions[(len(positions) - 1) // 2],
                        positions[len(positions) // 2]}
    references = [segment['identity'] for segment in segments
                  if segment['position'] in middle_positions]
    planes = []
    for normal in PLANES:
        nr, nc = normal
        if nr * dr + nc * dc == 0:
            continue
        for side in ('start', 'end'):
            offsets = {nr * segment[side][0] + nc * segment[side][1]
                       for segment in segments}
            if len(offsets) == 1:
                planes.append({'normal': normal, 'offset': next(iter(offsets)),
                               'side': side})
    if not planes:
        return None, {'failure': 'no_common_endpoint_plane'}
    record = {'background': background, 'direction': (dr, dc),
              'component_count': len(segments), 'foreground_cells': len(owned),
              'reference_identities': references, 'endpoint_planes': planes,
              'components': [{'identity': segment['identity'],
                              'color': segment['color'],
                              'length': len(segment['cells']),
                              'position': segment['position'],
                              'start': segment['start'], 'end': segment['end']}
                             for segment in segments]}
    return {'background': background, 'segments': segments,
            'references': references, 'planes': planes}, record


def render_length_reference(grid, fitted, valid_grid):
    if fitted != {'programs': [PROGRAM]}:
        return None, {'failure': 'invalid_length_reference_programs'}
    parsed, record = inspect_parallel_components(grid, valid_grid)
    if parsed is None:
        return None, record
    height, width = len(grid), len(grid[0])
    results = []
    interpretations = []
    for reference_id in parsed['references']:
        reference = parsed['segments'][reference_id]
        for plane in parsed['planes']:
            side = plane['side']
            output = [[parsed['background']] * width for _ in range(height)]
            occupied = set()
            interpretation = {'reference_identity': reference_id, 'plane': plane}
            for segment in parsed['segments']:
                dr = segment[side][0] - reference[side][0]
                dc = segment[side][1] - reference[side][1]
                copied = shifted_sparse_point_mask(reference['cells'], dr, dc,
                                                   height, width)
                if copied is None or occupied & copied:
                    return None, dict(record, failure='reference_copy_failed',
                                      interpretation=interpretation,
                                      component=segment['identity'])
                occupied.update(copied)
                for r, c in copied:
                    output[r][c] = segment['color']
            results.append(output)
            interpretations.append(interpretation)
    record.update(interpretations=interpretations,
                  interpretation_count=len(interpretations), enumeration_complete=True)
    if any(output != results[0] for output in results[1:]):
        return None, dict(record, failure='length_reference_whole_grids_disagree')
    record['renderer_case'] = 'new_reconstruction_parallel_length_reference'
    return results[0], record


def fit_length_reference(teachers, valid_grid):
    if (len(teachers) < 2 or
            any(not valid_grid(pair['input']) or not valid_grid(pair['output'])
                for pair in teachers)):
        return None, {'failure': 'insufficient_or_invalid_teachers'}
    if len({tuple(map(tuple, pair['input'])) for pair in teachers}) != len(teachers):
        return None, {'failure': 'duplicate_teacher_inputs'}
    fitted = {'programs': [PROGRAM]}
    results = [render_length_reference(pair['input'], fitted, valid_grid)
               for pair in teachers]
    matches = [output is not None and output == pair['output']
               for pair, (output, _) in zip(teachers, results)]
    record = {'declared_program_count': 1, 'enumeration_complete': True,
              'teacher_matches': matches, 'teacher_records': [r for _, r in results]}
    if not all(matches):
        return None, dict(record, failure='length_reference_teacher_mismatch')
    if all(pair['input'] == pair['output'] for pair in teachers):
        return None, dict(record, failure='identity_only_teachers')
    return fitted, record
