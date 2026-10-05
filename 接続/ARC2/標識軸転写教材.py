"""Separate prospective chirality prior; complete teacher fit and unanimous prediction."""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from . import 標識軸転写候補 as core
FIELDS = ('body_color', 'marker_color', 'object_connectivity', 'unconstrained_axis_chirality')


def emit(observer, kind, **record):
    if observer is not None:
        observer(deepcopy({'kind': kind, **record}))


def validate_teachers(teachers):
    record = {'teacher_fit_minimum': 2, 'teacher_count': 0}
    if not isinstance(teachers, (list, tuple)):
        return False, dict(record, failure='invalid_teacher_container')
    record['teacher_count'] = len(teachers)
    if any(not isinstance(t, dict) or set(t) != {'input', 'output'}
           or not core.valid_grid(t['input']) or not core.valid_grid(t['output']) for t in teachers):
        return False, dict(record, failure='invalid_teacher_pair')
    if len(teachers) < 2:
        return False, dict(record, failure='too_few_distinct_teachers')
    if len({tuple(map(tuple, t['input'])) for t in teachers}) != len(teachers):
        return False, dict(record, failure='duplicate_teacher_inputs')
    return True, record


def freeze_model(index, program):
    return (index,) + tuple(program[k] for k in FIELDS)


def expand_model(model):
    return {'program_index': model[0], 'program': dict(zip(FIELDS, model[1:]))}


def fit(teachers, observer=None):
    valid, record = validate_teachers(teachers)
    emit(observer, 'teacher_validation', valid=valid, record=record)
    if not valid:
        return (), record
    all_programs = core.programs()
    assert len(all_programs) == 360
    retained, outcomes = [], Counter()
    completed, model_index, teacher_index = 0, None, None
    try:
        for model_index, program in enumerate(all_programs):
            exacts = []
            for teacher_index, pair in enumerate(teachers):
                out, detail = core.render(pair['input'], program)
                exact = out is not None and core.valid_grid(out) and out == pair['output']
                status = 'exact' if exact else 'candidate_failure' if out is None else 'grid_mismatch'
                result = dict(teacher_index=teacher_index, output=out, detail=detail, exact_teacher_match=exact)
                outcomes[status] += 1
                exacts.append(exact)
                completed += 1
                emit(observer, 'model_teacher_return', model_index=model_index, teacher_index=teacher_index,
                     program=program, result=result, status=status, completed_returns=completed)
            keep = all(exacts)
            emit(observer, 'model_completed', model_index=model_index, program=program,
                 teacher_exacts=exacts, retained=keep)
            if keep:
                retained.append(freeze_model(model_index, program))
    except BaseException as error:
        emit(observer, 'evaluation_exception', stage='model_teacher_return', model_index=model_index,
             teacher_index=teacher_index, exception=type(error).__name__, message=str(error),
             partial_inner_stage=getattr(error, 'partial_full_return', None),
             completed_returns=completed, planned_returns=len(all_programs)*len(teachers),
             unevaluated_returns=len(all_programs)*len(teachers)-completed, semantic_HOLD=False)
        raise
    record.update(program_count=len(all_programs), complete_program_teacher_evaluations=completed,
                  outcomes=dict(outcomes), retained_count=len(retained),
                  failure=None if retained else 'no_model_fits_all_teachers')
    return tuple(retained), record


def predict(grid, models, observer=None):
    trace = dict(program_returns=[], output=None)
    model_index = None
    try:
        for model_index, model in enumerate(models):
            program = expand_model(model)['program']
            output, detail = core.render(grid, program)
            row = dict(index=model_index, program=program, output=output, detail=detail)
            trace['program_returns'].append(row)
            emit(observer, 'retained_model_return', model_index=model_index,
                 program_index=model[0], record=row, completed_returns=len(trace['program_returns']))
        if not models:
            trace['failure'] = 'no_teacher_fit_program'
        elif any(x['output'] is None for x in trace['program_returns']):
            trace['failure'] = 'retained_program_failed'
        elif len({tuple(map(tuple, x['output'])) for x in trace['program_returns']}) != 1:
            trace['failure'] = 'retained_program_outputs_disagree'
        else:
            trace['output'] = trace['program_returns'][0]['output']
        emit(observer, 'retained_consensus', candidate=trace['output'], record=trace)
        return trace['output'], trace
    except BaseException as error:
        emit(observer, 'evaluation_exception', stage='retained_model_return', model_index=model_index,
             exception=type(error).__name__, message=str(error),
             partial_inner_stage=getattr(error, 'partial_full_return', None),
             completed_returns=len(trace['program_returns']), planned_returns=len(models),
             unevaluated_returns=len(models)-len(trace['program_returns']), semantic_HOLD=False)
        raise


@dataclass(frozen=True, init=False, slots=True)
class 標識軸転写教材:
    モデル群: tuple
    教師数: int
    教師fit最小数: int
    適合数: int
    不足理由: str | None

    def __init__(self, 教師群, 監査=None, 観測=None):
        models, record = fit(教師群, observer=観測)
        object.__setattr__(self, 'モデル群', models)
        object.__setattr__(self, '教師数', record['teacher_count'])
        object.__setattr__(self, '教師fit最小数', 2)
        object.__setattr__(self, '適合数', len(models))
        object.__setattr__(self, '不足理由', record.get('failure'))
        if 監査 is not None:
            監査.update(deepcopy(record))

    def 候補(self, 格子, _policy, *, 観測=None):
        return predict(格子, self.モデル群, observer=観測)

    def 展開モデル(self):
        return [expand_model(model) for model in self.モデル群]

    def 記録(self):
        return {'保持候補数': len(self.モデル群), '保持候補': self.展開モデル(),
                '教師数': self.教師数, '教師fit最小数': self.教師fit最小数,
                '不足理由': self.不足理由,
                '合意条件': '全保持モデル・全許可役割が成功し完全出力が一致する場合のみ返す',
                '固定prior': '片軸labelのみ共有chiralityを適用、両軸制約では全side整合D4を保持する新しい360文法。意味妥当性未確認'}
