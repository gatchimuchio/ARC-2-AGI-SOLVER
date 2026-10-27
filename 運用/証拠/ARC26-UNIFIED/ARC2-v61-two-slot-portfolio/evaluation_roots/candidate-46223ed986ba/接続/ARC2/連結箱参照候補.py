"""Generic teacher fit and input-only consensus around the frozen renderer.

No IO, task identifiers, teacher storage, runtime hash checks, or exception
conversion. Resource and software exceptions propagate to the caller.
"""
from .連結箱参照核 import PROGRAMS, render, valid_grid

STATE_SCHEMA = 'linked_box_lookup.v1'


def successful(output, record):
    return (valid_grid(output) and isinstance(record, dict)
            and record.get('complete') is True and not record.get('failure'))


def fit(teachers):
    """Return (retained_state_or_None, complete_fit_record).

    A nonempty list/tuple of {'input': grid, 'output': grid} teachers is required.
    Every teacher is validated before any rendering. For valid teachers all nine
    programs and all teacher returns are materialized before program reduction.
    """
    if not isinstance(teachers, (list, tuple)) or not teachers:
        return None, dict(status='HOLD', complete=True,
                          failure='missing_or_invalid_teacher_sequence', teacher_validation=[])
    validation = []
    for i, pair in enumerate(teachers):
        is_pair = isinstance(pair, dict)
        input_valid = valid_grid(pair.get('input')) if is_pair else False
        output_valid = valid_grid(pair.get('output')) if is_pair else False
        validation.append(dict(teacher=i, input_valid=input_valid, output_valid=output_valid))
    if any(not x['input_valid'] or not x['output_valid'] for x in validation):
        return None, dict(status='HOLD', complete=True, failure='invalid_teacher_grid',
                          teacher_validation=validation)
    materialized = []
    for program in PROGRAMS:
        teacher_returns = []
        for i, pair in enumerate(teachers):
            output, record = render(pair['input'], program)
            teacher_returns.append(dict(teacher=i, output=output, record=record,
                                        exact=successful(output, record) and output == pair['output']))
        materialized.append(dict(program=list(program), teacher_returns=teacher_returns))
    retained = [x['program'] for x in materialized if all(y['exact'] for y in x['teacher_returns'])]
    state = dict(schema=STATE_SCHEMA, programs=retained) if retained else None
    record = dict(status='FIT' if state is not None else 'HOLD', complete=True,
                  teacher_validation=validation, teacher_count=len(teachers),
                  declared_program_count=len(PROGRAMS),
                  materialized_return_count=sum(len(x['teacher_returns']) for x in materialized),
                  all_program_returns=materialized, retained_programs=retained)
    if state is None:
        record['failure'] = 'no_complete_teacher_fitting_program'
    return state, record


def predict(grid, state):
    """Return (grid_or_None, complete_prediction_record) using only grid/state.

    State stores program names only. Every retained program is materialized;
    any failed return or any full-grid disagreement yields HOLD.
    """
    if not valid_grid(grid):
        return None, dict(status='HOLD', complete=True, failure='invalid_input_grid',
                          all_program_returns=[])
    if not isinstance(state, dict) or state.get('schema') != STATE_SCHEMA:
        return None, dict(status='HOLD', complete=True, failure='invalid_retained_state',
                          all_program_returns=[])
    raw_programs = state.get('programs')
    if not isinstance(raw_programs, (list, tuple)) or not raw_programs:
        return None, dict(status='HOLD', complete=True, failure='empty_retained_programs',
                          all_program_returns=[])
    programs = []
    for raw in raw_programs:
        if (not isinstance(raw, (list, tuple)) or len(raw) != 2
                or tuple(raw) not in PROGRAMS):
            return None, dict(status='HOLD', complete=True, failure='undeclared_retained_program',
                              all_program_returns=[])
        programs.append(tuple(raw))
    materialized = []
    for program in programs:
        output, record = render(grid, program)
        materialized.append(dict(program=list(program), output=output, record=record,
                                 successful=successful(output, record)))
    record = dict(complete=True, retained_program_count=len(programs),
                  materialized_return_count=len(materialized), all_program_returns=materialized)
    if any(not x['successful'] for x in materialized):
        return None, dict(record, status='HOLD', failure='retained_program_failed')
    if any(x['output'] != materialized[0]['output'] for x in materialized):
        return None, dict(record, status='HOLD', failure='retained_programs_disagree')
    return materialized[0]['output'], dict(record, status='OUTPUT')
