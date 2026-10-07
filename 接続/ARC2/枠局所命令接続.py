"""Same-family binding after a complete instruction-parser contract rejection."""
from .厳密枠局所命令 import valid_grid
from .周期補色局所命令 import fit as fit_embedded, render as render_embedded


STRUCTURAL_FAILURES = frozenset((
    'background_tie', 'separator_not_unique', 'not_three_cell_glyph_lattice',
    'nonblank_instruction_gaps', 'canvas_not_one_top_start',
    'empty_or_multicolour_instruction'))


def fit_after_complete_instruction_no_fit(teachers, old_models, old_record):
    if (old_models is not None or not isinstance(old_record, dict)
            or old_record.get('complete') is not True
            or old_record.get('failure') != 'teacher_input_contract'
            or not isinstance(teachers, list)
            or not isinstance(old_record.get('teacher_parse_records'), list)
            or len(old_record['teacher_parse_records']) != len(teachers)
            or any(not isinstance(record, dict)
                   for record in old_record['teacher_parse_records'])
            or not any(record.get('failure') in STRUCTURAL_FAILURES
                       for record in old_record['teacher_parse_records'])
            or any('failure' in record and record['failure'] not in STRUCTURAL_FAILURES
                   for record in old_record['teacher_parse_records'])):
        return None, {'failure': 'old_completed_structural_no_fit_required'}
    # Validate the whole distinct teacher set before making any area inference.
    if len(teachers) < 2:
        return None, {'failure': 'insufficient_teachers'}
    if any(not isinstance(pair, dict) or not valid_grid(pair.get('input'))
           or not valid_grid(pair.get('output')) for pair in teachers):
        return None, {'failure': 'invalid_teachers'}
    if len({tuple(map(tuple, pair['input'])) for pair in teachers}) != len(teachers):
        return None, {'failure': 'duplicate_teachers'}
    witnesses = []
    for index, pair in enumerate(teachers):
        ih, iw = len(pair['input']), len(pair['input'][0])
        oh, ow = len(pair['output']), len(pair['output'][0])
        required = 4 * (oh + 2) * (ow + 2)
        witnesses.append({'teacher_index': index, 'input_shape': [ih, iw],
                          'output_shape': [oh, ow], 'input_area': ih * iw,
                          'four_framed_panels_area': required,
                          'necessary_area_holds': ih * iw >= required})
    # Every successful core output is one D4-transformed panel interior.
    # parse owns >=4 disjoint equal-size framed panels. D4 preserves the
    # product (panel_height+2)*(panel_width+2), including rectangular rotation.
    # Thus a violation disproves the entire fit, without parsing any input.
    if any(not witness['necessary_area_holds'] for witness in witnesses):
        return None, {'failure': 'four_framed_panels_area_necessity',
                      'complete': True, 'teacher_area_witnesses': witnesses,
                      'parsed_teacher_count': 0, 'rendered_teacher_count': 0}
    fitted, record = fit_embedded(teachers)
    return (('embedded_local_actions',) if fitted else None), {
        'teacher_area_witnesses': witnesses, 'embedded_fit': record}
