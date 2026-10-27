"""全240候補の教師fitと全保持候補合意。支持閾値はnative HDSだけが判断する。"""
from dataclasses import dataclass
from . import 枠端積層候補 as core

FIELDS = ('fast_color', 'connectivity', 'fast_sign', 'slow_sign', 'center')


def emit(observer, kind, **value):
    if observer is not None:
        observer({'kind': kind, **value})


def validate_teachers(teachers):
    record = {'teacher_fit_minimum': 2, 'teacher_count': 0}
    if not isinstance(teachers, (list, tuple)):
        return False, dict(record, failure='invalid_teacher_container')
    record['teacher_count'] = len(teachers)
    if any(not isinstance(t, dict) or set(t) != {'input', 'output'}
           or not core.base.valid_grid(t['input']) or not core.base.valid_grid(t['output'])
           for t in teachers):
        return False, dict(record, failure='invalid_teacher_pair')
    if len(teachers) < 2:
        return False, dict(record, failure='too_few_distinct_teachers')
    if len({core.base.grid_key(t['input']) for t in teachers}) != len(teachers):
        return False, dict(record, failure='duplicate_teacher_inputs')
    return True, record


def expand_model(model):
    return dict(zip(FIELDS, model))


def fit(teachers, observer=None):
    """全返値を逐次observerへ渡す。例外をHOLDへ変換しない。"""
    valid, record = validate_teachers(teachers)
    emit(observer, 'teacher_validation', valid=valid, record=record)
    if not valid:
        return (), record
    programs = core.all_programs()
    views, evaluators, retained, records = [], [], [], []
    stage, model_index, teacher_index, completed = 'input_view', None, None, 0
    try:
        for teacher_index, pair in enumerate(teachers):
            view = core.base.prepare_input(pair['input'])
            views.append(view); evaluators.append(core.Evaluator(view))
            emit(observer, 'teacher_input_view', teacher_index=teacher_index, view=view)
        stage = 'model_teacher_return'
        for model_index, program in enumerate(programs):
            results, exacts = [], []
            for teacher_index, (evaluator, pair) in enumerate(zip(evaluators, teachers)):
                result = evaluator.evaluate(program)
                exact = result['failure'] is None and result['output'] == pair['output']
                results.append(result); exacts.append(exact)
                completed += 1
                emit(observer, stage, model_index=model_index, teacher_index=teacher_index,
                     program=program.record(), result=result, exact=exact, completed_returns=completed)
            row = {'program_number': model_index, 'program': program.record(),
                   'teacher_returns': results, 'teacher_exacts': exacts, 'retained': all(exacts)}
            records.append(row)
            emit(observer, 'model_completed', record=row)
            if all(exacts):
                retained.append(tuple(getattr(program, field) for field in FIELDS))
    except BaseException as error:
        emit(observer, 'evaluation_exception', stage=stage, model_index=model_index,
             teacher_index=teacher_index, exception=type(error).__name__, message=str(error),
             completed_returns=completed, planned_returns=len(programs)*len(teachers),
             unevaluated_returns=len(programs)*len(teachers)-completed,
             semantic_HOLD=False)
        raise
    record.update(all_program_teacher_returns=records, teacher_input_views=views,
                  enumerated_model_count=len(programs), eligible_model_count=len(retained),
                  eligible_models=[expand_model(model) for model in retained],
                  failure=None if retained else 'no_model_fits_all_teachers')
    return tuple(retained), record


def predict(grid, models, observer=None):
    """全保持モデルの完成格子が一致した場合だけ返す。成功した一部へ絞らない。"""
    returns = []
    stage, model_index = 'input_view', None
    try:
        view = core.base.prepare_input(grid)
        emit(observer, 'input_view', view=view)
        evaluator = core.Evaluator(view)
        stage = 'retained_model_return'
        for model_index, model in enumerate(models):
            program = core.Program(**expand_model(model))
            row = {'program': program.record(), 'result': evaluator.evaluate(program)}
            returns.append(row)
            emit(observer, stage, model_index=model_index, record=row, completed_returns=len(returns))
    except BaseException as error:
        emit(observer, 'evaluation_exception', stage=stage, model_index=model_index,
             exception=type(error).__name__, message=str(error), completed_returns=len(returns),
             planned_returns=len(models), unevaluated_returns=len(models)-len(returns), semantic_HOLD=False)
        raise
    failures = [i for i, row in enumerate(returns) if row['result']['failure']]
    success = [row['result']['output'] for row in returns if row['result']['failure'] is None]
    unique = {core.base.grid_key(output) for output in success}
    if not models:
        status, code = 'HOLD', 'no_teacher_consistent_program'
    elif failures:
        status, code = 'HOLD', 'retained_program_failure'
    elif len(unique) != 1:
        status, code = 'HOLD', 'retained_program_disagreement'
    else:
        status, code = 'OUTPUT', None
    record = {'status': status, 'code': code, 'output': success[0] if status == 'OUTPUT' else None,
              'failure_program_indices': failures, 'distinct_success_outputs': len(unique),
              'input_view': view, 'returns': returns}
    emit(observer, 'retained_consensus', record=record)
    return record['output'], record


@dataclass(frozen=True, init=False, slots=True)
class 枠端積層教材:
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
            監査.update(record)

    def 候補(self, 格子, _policy, *, 観測=None):
        return predict(格子, self.モデル群, observer=観測)

    def 展開モデル(self):
        return [expand_model(model) for model in self.モデル群]

    def 記録(self):
        return {'保持候補数': len(self.モデル群), '保持候補': self.展開モデル(),
                '教師数': self.教師数, '教師fit最小数': self.教師fit最小数,
                '不足理由': self.不足理由,
                '合意条件': '全保持モデル・全役割・全順序が成功し完全出力が一致する場合のみ返す',
                '固定prior': 'cue有向辺を右へ送る同じproper C4回転を全payloadへ適用'}
