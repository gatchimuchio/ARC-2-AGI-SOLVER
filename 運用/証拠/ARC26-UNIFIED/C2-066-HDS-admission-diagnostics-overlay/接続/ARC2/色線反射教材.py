"""Strict immutable teacher adapter; exhaustive eight-program fit and whole consensus."""
from copy import deepcopy
from dataclasses import dataclass
from . import 色線反射候補 as core


def valid_grid(grid):
    return (type(grid) is list and 1 <= len(grid) <= 30
            and type(grid[0]) is list and 1 <= len(grid[0]) <= 30
            and all(type(row) is list and len(row) == len(grid[0])
                    and all(type(v) is int and 0 <= v <= 9 for v in row)
                    for row in grid))


def emit(observer, kind, **value):
    if observer is not None:
        observer(deepcopy({'kind': kind, **value}))


def validate_teachers(teachers):
    record = {'teacher_count': 0, 'teacher_fit_minimum': 2,
              'declared_models': len(core.PROGRAMS)}
    if type(teachers) not in (list, tuple):
        return False, dict(record, failure='invalid_teacher_container')
    record['teacher_count'] = len(teachers)
    if any(type(pair) is not dict or set(pair) != {'input', 'output'}
           or not valid_grid(pair['input']) or not valid_grid(pair['output'])
           for pair in teachers):
        return False, dict(record, failure='invalid_teacher_pair')
    if len(teachers) < 2:
        return False, dict(record, failure='too_few_distinct_teachers')
    if len({tuple(map(tuple, pair['input'])) for pair in teachers}) != len(teachers):
        return False, dict(record, failure='duplicate_teacher_inputs')
    return True, record


class _Trace:
    """Complete returned prefix plus the active call; never converts exceptions to HOLD."""
    def __init__(self, observer, stage):
        self.observer, self.stage = observer, stage
        self.completed_models, self.current_returns, self.active = [], [], None
        self.partial = None

    def begin_model(self, model_index, model):
        self.current_returns = []
        emit(self.observer, 'model_start', model_index=model_index, model=model)

    def render(self, grid, model, teacher_index=None):
        self.active = {'model': model, 'teacher_index': teacher_index, 'input': grid}
        self.partial = None
        emit(self.observer, 'render_start', **self.active)
        def observe_prefix(event):
            if event['kind'] == 'role_completed':
                if self.partial is None:
                    self.partial = {'kind':'role_prefix', 'glyphs':[], 'failed_roles':[]}
                self.partial['glyphs'].append(deepcopy(event['glyph']))
                self.partial['failed_roles'].extend(deepcopy(event['failed_roles']))
            else:
                self.partial = deepcopy(event)
            emit(self.observer, event['kind'], **{k:v for k,v in event.items() if k != 'kind'})
        output, detail = core.render(grid, model, observer=observe_prefix if self.observer is not None else None)
        row = {'model': model, 'teacher_index': teacher_index,
               'input': grid, 'output': output, 'record': detail}
        self.current_returns.append(deepcopy(row))
        self.active = None
        emit(self.observer, 'render_return', **row)
        return output, detail

    def complete_model(self, row):
        self.completed_models.append(deepcopy(row))
        self.current_returns = []
        emit(self.observer, 'model_completed', record=row)

    def exception(self, error):
        emit(self.observer, 'evaluation_exception', stage=self.stage,
             exception=type(error).__name__, message=str(error), semantic_HOLD=False,
             completed_model_prefix=self.completed_models,
             current_model_return_prefix=self.current_returns, active_call=self.active,
             partial_current_render=self.partial)


def fit(teachers, observer=None):
    valid, record = validate_teachers(teachers)
    emit(observer, 'teacher_validation', valid=valid, record=record)
    if not valid:
        return (), record
    trace = _Trace(observer, 'teacher_fit'); models = []; records = []
    try:
        for model_index, model in enumerate(core.PROGRAMS):
            trace.begin_model(model_index, model); trials = []
            for teacher_index, pair in enumerate(teachers):
                output, detail = trace.render(pair['input'], model, teacher_index)
                same_shape = (output is not None and len(output) == len(pair['output'])
                              and all(len(a) == len(b) for a,b in zip(output,pair['output'])))
                mismatches = (None if output is None else
                              [[r,c,output[r][c],v] for r,row in enumerate(pair['output'])
                               for c,v in enumerate(row) if output[r][c] != v]
                              if same_shape else {'failure': 'output_shape_mismatch',
                                                 'actual_shape': [len(output),len(output[0])],
                                                 'expected_shape': [len(pair['output']),len(pair['output'][0])]})
                trials.append({'teacher':teacher_index, 'output':output, 'record':detail,
                               'equal':output == pair['output'], 'mismatches':mismatches})
            row = {'program':list(model), 'teachers':[{'teacher':t['teacher'], 'output':t['output'], 'record':t['record'], 'exact':t['equal']} for t in trials], 'all_exact':all(t['equal'] for t in trials)}
            records.append(row); trace.complete_model(row)
            if all(t['equal'] for t in trials):
                models.append(tuple(model))
        record.update(evaluated_models=len(records), evaluated_teacher_returns=len(records)*len(teachers),
                      retained_count=len(models), failure=None if models else 'no_model_fits_all_teachers')
        emit(observer, 'teacher_fit_completed', models=models, record=record)
        return tuple(models), record
    except BaseException as error:
        trace.exception(error)
        raise


def predict(grid, models, observer=None):
    if not valid_grid(grid):
        record = {'failure':'invalid_grid', 'returns':[]}
        emit(observer, 'retained_consensus', output=None, record=record)
        return None, record
    trace = _Trace(observer, 'prediction'); returns = []
    try:
        for model_index, model in enumerate(models):
            trace.begin_model(model_index, model)
            output, detail = trace.render(grid, model)
            row = {'output':output, 'record':detail}
            returns.append(row); trace.complete_model(row)
        record = {'models':[list(m) for m in models], 'returns':returns}
        if not returns:
            record['failure'] = 'no_fitted_models'
        elif any(r['output'] is None for r in returns):
            record['failure'] = 'model_failure'
        elif any(r['output'] != returns[0]['output'] for r in returns):
            record['failure'] = 'model_disagreement'
        output = None if 'failure' in record else returns[0]['output']
        emit(observer, 'retained_consensus', output=output, record=record)
        return output, record
    except BaseException as error:
        trace.exception(error)
        raise


@dataclass(frozen=True, init=False, slots=True)
class 色線反射教材:
    モデル群: tuple
    教師数: int
    適合数: int
    不足理由: str | None

    def __init__(self, 教師群, 監査=None, 観測=None):
        models, record = fit(教師群, 観測)
        object.__setattr__(self, 'モデル群', models)
        object.__setattr__(self, '教師数', record['teacher_count'])
        object.__setattr__(self, '適合数', len(models))
        object.__setattr__(self, '不足理由', record.get('failure'))
        if 監査 is not None:
            監査.update(deepcopy(record))

    def 候補(self, 格子, policy, 観測=None):
        return predict(格子, self.モデル群, 観測)

    def 記録(self):
        return {'保持候補':[list(m) for m in self.モデル群], '保持候補数':self.適合数,
                '教師数':self.教師数, '教師fit最小数':2, '不足理由':self.不足理由,
                '合意条件':'全保持モデル・全入力役割が成功し全盤面一致。資源例外は伝播。',
                '固定prior':'唯一最頻背景・whole C4 L3/棒3/点・全L発射・法線隣接port・8共有program・全有限状態閉包・等色分岐は未観測prior・engine注入cycleのL入力到達性は未証明'}
