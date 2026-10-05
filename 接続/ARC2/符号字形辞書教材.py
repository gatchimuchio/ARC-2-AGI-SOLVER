"""Strict teacher boundary and complete-return observation for the frozen grammar."""
from dataclasses import dataclass
from . import 符号字形辞書候補 as core


def emit(observer, kind, **value):
    if observer is not None:
        observer({'kind': kind, **value})


def validate_teachers(teachers):
    record = {'teacher_count': len(teachers) if isinstance(teachers, list) else 0,
              'teacher_fit_minimum': 2}
    if not isinstance(teachers, list):
        return False, dict(record, failure='invalid_teacher_container')
    if any(not isinstance(pair, dict) or set(pair) != {'input', 'output'}
           or not core.valid_grid(pair['input']) or not core.valid_grid(pair['output'])
           for pair in teachers):
        return False, dict(record, failure='invalid_teacher_pair')
    if len(teachers) < 2:
        return False, dict(record, failure='too_few_distinct_teachers')
    if len({tuple(map(tuple, pair['input'])) for pair in teachers}) != len(teachers):
        return False, dict(record, failure='duplicate_teacher_inputs')
    return True, record


class _ObservedGrammar(core.Grammar):
    """Only wrap completed calls; inherited Grammar method bodies stay untouched."""
    def __init__(self, observer, stage):
        super().__init__(core.valid_grid, core.color_components)
        self.observer, self.stage = observer, stage
        self.completed_hypotheses = self.completed_parse = self.completed_render = 0
        self.partial, self.retained, self.render_returns = [], [], []
        self.in_render = False
        self._modes, self._component_records = {}, {}
        self.components = self._cached_components

    def mode(self, grid):
        key = tuple(map(tuple, grid))
        if key not in self._modes:
            self._modes[key] = super().mode(grid)
        return self._modes[key]

    def _cached_components(self, grid, color, include_diagonal=False):
        key = (tuple(map(tuple, grid)), color, include_diagonal)
        if key not in self._component_records:
            found = core.color_components(grid, color, include_diagonal=include_diagonal)
            self._component_records[key] = tuple(
                (part["color"], frozenset(part["cells"]), part["bbox"], part["size"])
                for part in found)
        # Every caller receives independent mutable records, as the original helper provides.
        return [{"color": color, "cells": set(cells), "bbox": bbox, "size": size}
                for color, cells, bbox, size in self._component_records[key]]

    def returned(self, kind, **value):
        row = {'kind': kind, 'hypothesis_index': self.completed_hypotheses,
               'stage': self.stage, **value}
        self.partial.append(row)
        if self.observer is not None:
            self.observer(row)

    def parse(self, grid, bg, keys, shape, anchor, corner):
        result = super().parse(grid, bg, keys, shape, anchor, corner)
        self.completed_parse += 1
        self.returned('parse_return', nested_in_render=self.in_render,
                      parse_index=self.completed_parse-1,
                      parameters=(bg, shape, anchor, corner, tuple(keys)),
                      parsed=result[0], record=result[1])
        return result

    def glyph_valid(self, tile, bg, keys):
        result = super().glyph_valid(tile, bg, keys)
        self.returned('glyph_return', tile=tile, background=bg, keys=tuple(keys), valid=result)
        return result

    def render(self, grid, model):
        self.in_render = True
        try:
            result = super().render(grid, model)
        finally:
            self.in_render = False
        self.completed_render += 1
        self.render_returns.append(result)
        self.returned('render_return', model_index=self.completed_render-1,
                      model=model, output=result[0], record=result[1])
        return result

    def hypothesis(self, record):
        if record['accepted']:
            self.retained.append(record['model'])
        emit(self.observer, 'hypothesis_completed', hypothesis_index=self.completed_hypotheses,
             record=record)
        self.completed_hypotheses += 1
        self.partial = []
        self.render_returns = []

    def exception(self, error):
        emit(self.observer, 'evaluation_exception', stage=self.stage,
             exception=type(error).__name__, message=str(error), semantic_HOLD=False,
             completed_hypotheses=self.completed_hypotheses,
             completed_parse_returns=self.completed_parse,
             completed_render_returns=self.completed_render,
             partial_current_hypothesis=self.partial,
             retained_models=tuple(self.retained),
             completed_render_prefix=self.render_returns)


def impossible_shared_shape(teachers, grammar):
    """An exact empty-domain certificate, never a heuristic candidate filter.

    Grammar.parse requires every payload component bbox to equal the one shared
    (gh, gw). Two unequal required shapes therefore contradict every declared
    shape, every anchor in that shape, and all four label corners. This proof
    executes no per-hypothesis parse; it returns None whenever not established.
    """
    if any((len(p['input']), len(p['input'][0])) !=
           (len(p['output']), len(p['output'][0])) for p in teachers):
        return None
    backgrounds = {grammar.mode(p['input']) for p in teachers}
    if None in backgrounds or len(backgrounds) != 1:
        return None
    bg = next(iter(backgrounds))
    input_colors = {v for p in teachers for row in p['input'] for v in row}
    output_colors = {v for p in teachers for row in p['output'] for v in row}
    keys = tuple(sorted(input_colors - output_colors - {bg}))
    if not keys:
        return None
    first = None
    for ti, pair in enumerate(teachers):
        grid = pair['input']
        for color in sorted({v for row in grid for v in row} - {bg} - set(keys)):
            for component in grammar.components(grid, color, include_diagonal=True):
                top, left, bottom, right = component['bbox']
                witness = {'teacher_index': ti, 'color': color,
                           'bbox': component['bbox'], 'size': component['size'],
                           'required_shape': (bottom-top+1, right-left+1)}
                if first is None:
                    first = witness
                elif first['required_shape'] != witness['required_shape']:
                    h = min(len(p['input']) for p in teachers)
                    w = min(len(p['input'][0]) for p in teachers)
                    declared = h*(h+1)*w*(w+1)
                    return {'proof': 'incompatible_payload_component_shapes',
                            'background': bg, 'keys': keys,
                            'witnesses': (first, witness),
                            'domain': {'height': (1, h), 'width': (1, w),
                                       'anchors': 'every cell of each shape',
                                       'label_corners': ((-1,-1),(-1,1),(1,-1),(1,1))},
                            'declared_hypotheses': declared,
                            'enumerated_hypotheses': 0,
                            'proven_rejected_hypotheses': declared,
                            'all_declared_models_rejected': True}
    return None


def fit(teachers, observer=None):
    valid, record = validate_teachers(teachers)
    emit(observer, 'teacher_validation', valid=valid, record=record)
    if not valid:
        return (), record
    grammar = _ObservedGrammar(observer, 'teacher_fit')
    try:
        proof = impossible_shared_shape(teachers, grammar)
        if proof is not None:
            record.update(failure=proof['proof'], domain_resolved=True,
                          exhausted=False, hypotheses=0, models=0, proof=proof)
            emit(observer, 'grammar_domain_proof', record=proof)
            emit(observer, 'teacher_fit_completed', retained_models=(), record=record)
            return (), record
        models, detail = grammar.fit(teachers, grammar.hypothesis)
    except BaseException as error:
        grammar.exception(error)
        raise
    record.update(detail)
    emit(observer, 'teacher_fit_completed', retained_models=models, record=record)
    return models, record


def predict(grid, models, observer=None):
    grammar = _ObservedGrammar(observer, 'prediction')
    try:
        output, record = grammar.consensus(grid, models)
    except BaseException as error:
        grammar.exception(error)
        raise
    emit(observer, 'retained_consensus', output=output, record=record)
    return output, record


@dataclass(frozen=True, init=False, slots=True)
class 符号字形辞書教材:
    モデル群: tuple
    教師数: int
    適合数: int

    def __init__(self, 教師群, 監査=None, 観測=None):
        models, record = fit(教師群, 観測)
        object.__setattr__(self, 'モデル群', models)
        object.__setattr__(self, '教師数', record['teacher_count'])
        object.__setattr__(self, '適合数', len(models))
        if 監査 is not None:
            監査.update(record)

    def 候補(self, 格子, _policy, *, 観測=None):
        return predict(格子, self.モデル群, 観測)

    def 展開モデル(self):
        return list(self.モデル群)

    def 記録(self):
        return {'保持候補': self.展開モデル(), '保持候補数': self.適合数,
                '教師数': self.教師数, '教師fit最小数': 2,
                '合意条件': '全保持モデル成功かつ全盤面一致。失敗・不一致・ゼロ保持はHOLD。資源例外は伝播。',
                '固定prior': '共有唯一最頻背景・同サイズcanvas・key/payload非兼用・単色非singleton tight8連結glyph・共有矩形/内部原点/4外側対角label・無回転無拡縮・全tile矩形in-bounds非重複。'}
