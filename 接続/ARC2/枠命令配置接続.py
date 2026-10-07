"""Completed legacy no-fit gate and exact strict-fit necessity prepass."""
from . import 全枠命令配置 as view
from . import 並列枠命令配置 as parallel


def complete_raw_record(record):
    if not isinstance(record, dict):
        return False
    failure_fields = {
        'macro_tile_foreground_component_count_not_two': {'foreground_component_count'},
        'macro_tile_pair_not_unique': {'valid_pair_count', 'foreground_component_count'},
        'macro_tile_output_exceeds_arc_limit': {'macro_tile_shape', 'macro_layout_shape', 'macro_tiled_shape'},
        'macro_tile_layout_has_no_active_cells': set(),
        'identity_macro_tile_render': set(),
    }
    if record.get('failure') in failure_fields:
        return set(record) == failure_fields[record['failure']] | {'failure'}
    return (record.get('renderer_case') == 'layout_mask_macro_tile_expander'
            and set(record) == {'renderer_case', 'background', 'macro_background_color',
                                'macro_motif_bbox', 'macro_layout_bbox', 'macro_tile_shape',
                                'macro_layout_shape', 'macro_tiled_shape', 'macro_layout_color',
                                'macro_active_cell_count', 'macro_motif_colors'})


def completed_no_fit(teachers, fitted, record):
    if fitted is not False or not isinstance(record, dict):
        return False
    if set(record) != {'failure', 'raw_pair_fits', 'raw_records'}:
        return False
    fits, records = record['raw_pair_fits'], record['raw_records']
    return (record['failure'] == 'original_teacher_reproduction_failed'
            and isinstance(fits, list) and isinstance(records, list)
            and len(fits) == len(records) == len(teachers) and len(teachers) >= 2
            and all(type(value) is bool for value in fits) and not all(fits)
            and all(complete_raw_record(value) for value in records))


def fit(teachers):
    strict = view.strict
    if (not isinstance(teachers, list) or len(teachers) < 2
            or any(not isinstance(p, dict) or not strict.valid_grid(p.get('input'))
                   or not strict.valid_grid(p.get('output')) for p in teachers)
            or len({tuple(map(tuple, p['input'])) for p in teachers}) != len(teachers)):
        return strict.fit(teachers)
    witnesses = []
    for index, pair in enumerate(teachers):
        roles, record = strict.parse(pair['input'])
        if (set(record) != {'roles', 'probes'} or record['roles'] != len(roles)
                or not isinstance(record['probes'], list)):
            raise RuntimeError('strict_parse_completion_unrecognized')
        witnesses.append({'teacher_index': index, 'role_count': len(roles),
                          'complete': True, 'record': record})
    rejected = [w['teacher_index'] for w in witnesses if w['role_count'] == 0]
    count = len(strict.MODELS)
    common = {'complete': True, 'teacher_count': len(teachers), 'model_count': count,
              'proof_parse_calls': len(witnesses), 'teacher_parse_witnesses': witnesses}
    if rejected:
        return (), {**common, 'status': 'proven_empty', 'retained_count': 0,
                    'retained_models': (), 'teacher_fit_exact': False,
                    'rejected_teacher_indices': rejected, 'evaluated_teacher_calls': 0,
                    'symbolic_unexecuted_teacher_calls': count * len(teachers)}
    models, record = view.fit(teachers)
    if record.get('complete') is not True:
        raise RuntimeError('strict_fit_completion_unrecognized')
    return models, {**common, 'status': 'fitted' if models else 'completed_no_fit',
                    'retained_count': len(models), 'retained_models': models,
                    'teacher_fit_exact': bool(models), 'rejected_teacher_indices': [],
                    'evaluated_teacher_calls': sum(len(r['teacher_returns'])
                                                    for r in record['all_model_returns']),
                    'symbolic_unexecuted_teacher_calls': 0}


def compact(record):
    return {key: value for key, value in record.items() if key != 'teacher_parse_witnesses'}


def completed_relational_disagreement(output, record, models):
    """Only a completed disagreement of every original retained program qualifies."""
    if (output is not None or not isinstance(models, (list, tuple)) or not models
            or not isinstance(record, dict)
            or set(record) != {'complete', 'model_returns', 'failure'}
            or record['complete'] is not True
            or record['failure'] != 'retained_model_failed'):
        return False
    returned = record['model_returns']
    if not isinstance(returned, list) or len(returned) != len(models):
        return False
    for model, entry in zip(models, returned):
        if (not isinstance(entry, dict) or set(entry) != {'model', 'return', 'record'}
                or entry['model'] != model or entry['return'] is not None):
            return False
        role_record = entry['record']
        if (not isinstance(role_record, dict)
                or set(role_record) != {'complete', 'roles', 'view_probes', 'original_parse',
                                       'model', 'role_returns', 'failure'}
                or role_record['complete'] is not True or role_record['model'] != model
                or role_record['failure'] != 'relational_role_disagreement'
                or type(role_record['roles']) is not int or role_record['roles'] < 2
                or not isinstance(role_record['view_probes'], list)):
            return False
        original = role_record['original_parse']
        if (not isinstance(original, dict) or set(original) != {'roles', 'probes'}
                or type(original['roles']) is not int or original['roles'] != 0
                or not isinstance(original['probes'], list)):
            return False
        roles = role_record['role_returns']
        if not isinstance(roles, list) or len(roles) != role_record['roles']:
            return False
        inventory = []
        for probe in role_record['view_probes']:
            if not isinstance(probe, dict) or not isinstance(probe.get('background_returns'), list):
                return False
            for entry in probe['background_returns']:
                if not isinstance(entry, dict):
                    return False
                if 'role_index' in entry:
                    if type(entry['role_index']) is not int:
                        return False
                    inventory.append(entry['role_index'])
        if sorted(inventory) != list(range(len(roles))):
            return False
        for index, role in enumerate(roles):
            if (not isinstance(role, dict) or set(role) != {'role_index', 'return', 'record'}
                    or type(role['role_index']) is not int or role['role_index'] != index
                    or not view.strict.valid_grid(role['return'])):
                return False
            action = role['record']
            if (not isinstance(action, dict)
                    or set(action) != {'macro', 'turns', 'offset', 'painted_cells', 'canvas_cells'}
                    or not complete_raw_record(action['macro'])
                    or action['macro'].get('renderer_case') != 'layout_mask_macro_tile_expander'
                    or type(action['turns']) is not int or action['turns'] not in range(4)
                    or not isinstance(action['offset'], list) or len(action['offset']) != 2
                    or any(type(value) is not int or value < 0 for value in action['offset'])
                    or type(action['painted_cells']) is not int
                    or type(action['canvas_cells']) is not int
                    or action['canvas_cells'] != len(role['return']) * len(role['return'][0])
                    or not 0 < action['painted_cells'] <= action['canvas_cells']):
                return False
        if all(role['return'] == roles[0]['return'] for role in roles[1:]):
            return False
    return True


def predict(grid, models):
    """Preserve accepted113 results; add only the disclosed foreach-command grammar."""
    original = view.consensus(grid, models)
    if not completed_relational_disagreement(*original, models):
        return original
    output, record = parallel.consensus(grid, models)
    return output, {**record, 'input_view': 'foreach_command_composition',
                    'new_control_grammar': True, 'accepted113_record': original[1]}
