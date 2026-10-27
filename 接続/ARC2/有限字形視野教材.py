"""Exact strict012 fitting with the frozen bounded background-padding input view.

The old trial is rejected history, not accepted-main reuse. Labels participate in
the conservative envelope and can make a formerly valid near-30 input HOLD.
This inherits strict teacher fitting and the old fresh-background renderer.
"""
from copy import deepcopy
from dataclasses import dataclass
from . import 符号字形辞書教材 as strict
from . import 有限字形視野候補 as view
from .既存重畳組立 import crop_grid

MAX_FIT_HYPOTHESES = 20_000


def emit(observer, event):
    if observer is not None:
        observer(deepcopy(event))


def _declared_fit_hypotheses(teachers):
    if not isinstance(teachers, list) or not teachers:
        return None
    try:
        inputs = [pair['input'] for pair in teachers]
        max_h = min(len(grid) for grid in inputs)
        max_w = min(len(grid[0]) for grid in inputs)
    except (KeyError, TypeError, IndexError):
        return None
    return 4 * (max_h * (max_h + 1) // 2) * (max_w * (max_w + 1) // 2)


def fit(teachers, observer=None):
    strict_observer = None if observer is None else lambda event: emit(observer, event)
    declared = _declared_fit_hypotheses(teachers)
    if declared is None or declared <= MAX_FIT_HYPOTHESES:
        return strict.fit(teachers, strict_observer)

    valid, record = strict.validate_teachers(teachers)
    strict.emit(strict_observer, 'teacher_validation', valid=valid, record=record)
    if not valid:
        return (), record

    # Keep the existing exact impossibility certificate available even when
    # the remaining exhaustive domain would exceed the runtime budget.
    grammar = strict._ObservedGrammar(strict_observer, 'teacher_fit')
    proof = strict.impossible_shared_shape(teachers, grammar)
    if proof is not None:
        record.update(failure=proof['proof'], domain_resolved=True,
                      exhausted=False, hypotheses=0, models=0, proof=proof)
        strict.emit(strict_observer, 'grammar_domain_proof', record=proof)
        strict.emit(strict_observer, 'teacher_fit_completed', retained_models=(), record=record)
        return (), record

    record.update(failure='hypothesis_budget_exceeded', domain_resolved=False,
                  exhausted=False, search_truncated=True, hypotheses=0, models=0,
                  declared_hypotheses=declared, max_hypotheses=MAX_FIT_HYPOTHESES)
    strict.emit(strict_observer, 'grammar_domain_budget', record=record)
    strict.emit(strict_observer, 'teacher_fit_completed', retained_models=(), record=record)
    return (), record


def predict(grid, models, observer=None):
    completed = []
    safe_observer = None if observer is None else lambda event: emit(observer, event)
    grammar = strict._ObservedGrammar(safe_observer, 'bounded_view_prediction')
    try:
        for index, model in enumerate(models):
            result = view.render_window(grid, model, grammar, crop_grid)
            completed.append(result)
            emit(observer, {'kind': 'view_model_return', 'model_index': index,
                            'model': model, 'output': result[0], 'record': result[1]})
    except BaseException as error:
        grammar.exception(error)
        emit(observer, {'kind': 'view_evaluation_exception', 'stage': 'bounded_view_prediction',
                        'exception': type(error).__name__, 'message': str(error),
                        'resource_failure': isinstance(error, (MemoryError, RecursionError, TimeoutError)),
                        'semantic_HOLD': False, 'active_model_index': len(completed),
                        'completed_view_prefix': completed})
        raise
    # Same frozen consensus semantics; the explicit loop only adds observation.
    record = {'returns': deepcopy(completed), 'all_retained_models_evaluated': len(completed)}
    if not completed or any(output is None for output, _ in completed):
        output, record = None, {**record, 'failure': 'one_or_more_retained_models_failed'}
    elif any(output != completed[0][0] for output, _ in completed[1:]):
        output, record = None, {**record, 'failure': 'retained_models_disagree'}
    else:
        output = completed[0][0]
    emit(observer, {'kind': 'retained_view_consensus', 'output': output, 'record': record})
    return output, record


@dataclass(frozen=True, init=False, slots=True)
class 有限字形視野教材:
    モデル群: tuple
    教師数: int
    適合数: int

    def __init__(self, 教師群, 監査=None, 観測=None):
        models, record = fit(教師群, 観測)
        object.__setattr__(self, 'モデル群', models)
        object.__setattr__(self, '教師数', record['teacher_count'])
        object.__setattr__(self, '適合数', len(models))
        if 監査 is not None:
            監査.update(deepcopy(record))

    def 候補(self, 格子, _policy, 観測=None):
        return predict(格子, self.モデル群, 観測)

    def 記録(self):
        return {'保持候補': list(self.モデル群), '保持候補数': self.適合数,
                '教師数': self.教師数, '教師fit最小数': 2,
                '合意条件': '全保持モデル成功かつ元入力窓crop一致。失敗・不一致・ゼロ保持はHOLD。資源例外は伝播。',
                '固定prior': '旧012strict教師fit。元入力strict ARC/一意背景をpadding前検査。全key envelopeはlabelを含む。30超HOLD。背景padding→旧renderer→元窓crop。',
                '制約': f'教師fit仮説数が{MAX_FIT_HYPOTHESES}超なら部分候補を破棄してHOLD。clipped教師の新辞書学習なし。旧012fresh背景出力、元前景保存の主張なし。label過剰paddingで旧有効入力もHOLDし得る。'}
