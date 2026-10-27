"""Strict teacher boundary, exhaustive fit, immutable models and whole-grid consensus."""
from copy import deepcopy
from dataclasses import dataclass
from . import 見本格子分類候補 as core


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
    record = {'teacher_count': 0, 'teacher_fit_minimum': 2, 'declared_models': len(core.MODELS)}
    if type(teachers) not in (list, tuple):
        return False, dict(record, failure='invalid_teacher_container')
    record['teacher_count'] = len(teachers)
    if any(type(pair) is not dict or set(pair) != {'input', 'output'}
           or not valid_grid(pair['input']) or not valid_grid(pair['output']) for pair in teachers):
        return False, dict(record, failure='invalid_teacher_pair')
    if len(teachers) < 2:
        return False, dict(record, failure='too_few_distinct_teachers')
    if len({tuple(map(tuple, pair['input'])) for pair in teachers}) != len(teachers):
        return False, dict(record, failure='duplicate_teacher_inputs')
    return True, record


class _Trace:
    def __init__(self, observer, stage):
        self.observer, self.stage = observer, stage
        self.completed_models, self.active = [], {}
        self.completed_returns = 0

    def __call__(self, event):
        kind = event['kind']
        if kind == 'model_start':
            self.active = {'model': event['model'], 'model_index': event['model_index'],
                           'parameter_returns': [], 'teacher_returns': [],
                           'allocation_prefix': [], 'allocation_search_prefix': []}
        elif kind == 'parameter_teacher_start':
            self.active.update(teacher_index=event['teacher_index'], allocation_prefix=[],
                               allocation_search_prefix=[])
        elif kind == 'render_start':
            self.active.pop('proof_domain', None)
            self.active.update(allocation_prefix=[], allocation_search_prefix=[], proof_witness_prefix=[])
        elif kind == 'allocation_proof_start':
            self.active.update(proof_domain=deepcopy(event['domain']), proof_witness_prefix=[])
        elif kind == 'allocation_witness_return':
            self.active.setdefault('proof_witness_prefix', []).append(deepcopy(event))
        elif kind == 'allocation_search_start':
            self.active['allocation_search_prefix'] = [deepcopy(event)]
        elif kind == 'allocation_search_step':
            self.active['allocation_search_prefix'].append(deepcopy(event))
        elif kind in ('allocation_return', 'parameter_allocation_return'):
            self.active.setdefault('allocation_prefix', []).append(deepcopy(event))
        elif kind == 'parameter_teacher_return':
            self.active['parameter_returns'].append(deepcopy(event))
        elif kind == 'model_teacher_return':
            self.active['teacher_returns'].append(deepcopy(event))
            self.active.update(allocation_prefix=[], allocation_search_prefix=[])
            self.completed_returns += 1
        elif kind == 'model_completed':
            self.completed_models.append(deepcopy(event['record']))
            self.active = {}
        elif kind == 'retained_model_return':
            self.completed_returns += 1
        emit(self.observer, kind, **{k:v for k,v in event.items() if k != 'kind'})

    def exception(self, error):
        emit(self.observer, 'evaluation_exception', stage=self.stage,
             exception=type(error).__name__, message=str(error), semantic_HOLD=False,
             completed_model_prefix=self.completed_models, completed_returns=self.completed_returns,
             partial_current_model=self.active)


def fit(teachers, observer=None):
    valid, record = validate_teachers(teachers)
    emit(observer, 'teacher_validation', valid=valid, record=record)
    if not valid:
        return (), record
    mismatches = [{'teacher_index': i, 'input_shape': (len(p['input']), len(p['input'][0])),
                   'output_shape': (len(p['output']), len(p['output'][0]))}
                  for i,p in enumerate(teachers)
                  if (len(p['input']),len(p['input'][0])) != (len(p['output']),len(p['output'][0]))]
    if mismatches:
        record.update(failure='shape_preservation_refutes_whole_grammar', evaluated_models=0,
                      evaluated_teacher_returns=0, symbolically_impossible_models=len(core.MODELS),
                      shape_witnesses=mismatches, retained_count=0)
        emit(observer, 'whole_grammar_impossibility', record=record)
        return (), record
    trace = _Trace(observer, 'teacher_fit')
    try:
        retained, records = core.fit(teachers, observer=trace)
    except BaseException as error:
        trace.exception(error)
        raise
    models = tuple((tuple(m['model']), tuple(m['colors'])) for m in retained)
    record.update(evaluated_models=len(records), evaluated_teacher_returns=len(records)*len(teachers),
                  symbolically_impossible_models=0, retained_count=len(models),
                  failure=None if models else 'no_model_fits_all_teachers')
    emit(observer, 'teacher_fit_completed', models=models, record=record)
    return models, record


def predict(grid, models, observer=None):
    if not valid_grid(grid):
        record = {'failure': 'invalid_grid', 'returns': []}
        emit(observer, 'retained_consensus', output=None, record=record)
        return None, record
    trace = _Trace(observer, 'prediction'); returns = []
    try:
        for index, (model, colors) in enumerate(models):
            trace({'kind':'model_start', 'model_index':index, 'model':model})
            output, detail = core.render(grid, model, colors, observer=trace)
            row = {'model':model, 'colors':colors, 'output':output, 'record':detail}
            returns.append(row)
            trace({'kind':'model_completed', 'record':row})
            trace({'kind':'retained_model_return', 'model_index':index, 'result':row})
        record = {'returns': returns}
        if not returns:
            record['failure'] = 'no_models'
        elif any(r['output'] is None for r in returns):
            record['failure'] = 'retained_model_unresolved'
        elif any(r['output'] != returns[0]['output'] for r in returns):
            record['failure'] = 'retained_model_disagreement'
        else:
            record.update(agreed_models=len(returns), foreground_preserved=True)
        output = None if 'failure' in record else returns[0]['output']
        emit(observer, 'retained_consensus', output=output, record=record)
        return output, record
    except BaseException as error:
        trace.exception(error)
        raise


@dataclass(frozen=True, init=False, slots=True)
class 見本格子分類教材:
    モデル群: tuple
    教師数: int
    適合数: int
    不足理由: str | None

    def __init__(self, 教師群, 監査=None, 観測=None):
        models, record = fit(教師群, observer=観測)
        object.__setattr__(self, 'モデル群', models)
        object.__setattr__(self, '教師数', record['teacher_count'])
        object.__setattr__(self, '適合数', len(models))
        object.__setattr__(self, '不足理由', record.get('failure'))
        if 監査 is not None:
            監査.update(deepcopy(record))

    def 候補(self, 格子, policy, 観測=None):
        return predict(格子, self.モデル群, observer=観測)

    def 展開モデル(self):
        return [{'model':model, 'colors':colors} for model,colors in self.モデル群]

    def 記録(self):
        return {'保持候補':self.展開モデル(), '保持候補数':self.適合数,
                '教師数':self.教師数, '教師fit最小数':2, '不足理由':self.不足理由,
                '合意条件':'全保持モデルと全割当が成功し全盤面一致する場合のみ返す。資源例外は伝播。',
                '固定prior':'唯一最頻背景・四方向の唯一役割・同色二分割線・正偶数間隔の規則格子・全前景所有・有限576仮説・背景のみ塗色'}
