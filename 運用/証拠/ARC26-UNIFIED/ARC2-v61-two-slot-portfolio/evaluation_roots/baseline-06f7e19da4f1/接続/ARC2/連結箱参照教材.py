"""Explicit linked-box lookup boundary; standard HDS support and empty prior.

Only completed full-grid teacher consensus contributes one observation per
teacher. No individual box, wire endpoint, program or lookup supplies support.
The frozen candidate has no fallback or exception conversion.
"""
from copy import deepcopy
from dataclasses import dataclass
from . import 連結箱参照候補 as api


def fit(teachers):
    """Use only inherent canvas/input-palette impossibility certificates."""
    if not isinstance(teachers, (list, tuple)) or not teachers:
        return api.fit(teachers)
    validation = []
    for i, pair in enumerate(teachers):
        is_pair = isinstance(pair, dict)
        validation.append(dict(teacher=i,
                               input_valid=api.valid_grid(pair.get('input')) if is_pair else False,
                               output_valid=api.valid_grid(pair.get('output')) if is_pair else False))
    if any(not x['input_valid'] or not x['output_valid'] for x in validation):
        return api.fit(teachers)
    shape_witnesses, palette_witnesses = [], []
    for i, pair in enumerate(teachers):
        input_shape = (len(pair['input']), len(pair['input'][0]))
        output_shape = (len(pair['output']), len(pair['output'][0]))
        if input_shape != output_shape:
            shape_witnesses.append(dict(teacher=i, input_shape=input_shape, output_shape=output_shape))
        input_colors = {v for row in pair['input'] for v in row}
        output_colors = {v for row in pair['output'] for v in row}
        novel_colors = output_colors - input_colors
        if novel_colors:
            palette_witnesses.append(dict(teacher=i, input_colors=sorted(input_colors),
                                          output_colors=sorted(output_colors), novel_colors=sorted(novel_colors)))
    if shape_witnesses or palette_witnesses:
        return None, dict(status='HOLD', complete=True,
                          failure='teacher_shape_not_preserved' if shape_witnesses else 'teacher_output_color_not_in_input',
                          teacher_validation=validation, teacher_count=len(teachers),
                          declared_program_count=len(api.PROGRAMS), materialized_return_count=0,
                          all_program_returns=[], retained_programs=[],
                          necessity_guard=dict(proof='every_program_preserves_canvas_and_input_palette',
                                               all_programs_impossible=True,
                                               shape_witnesses=shape_witnesses,
                                               palette_witnesses=palette_witnesses,
                                               render_calls=0))
    return api.fit(teachers)


@dataclass(frozen=True, init=False, slots=True)
class 連結箱参照教材:
    モデル群: tuple
    教師数: int
    完了: bool
    不足理由: str | None
    必要条件証明: str | None

    def __init__(self, 教師群, 監査=None):
        state, record = fit(教師群)
        models = tuple(tuple(p) for p in state['programs']) if state is not None else ()
        object.__setattr__(self, 'モデル群', models)
        object.__setattr__(self, '教師数', record.get('teacher_count', len(教師群) if isinstance(教師群, (list, tuple)) else 0))
        object.__setattr__(self, '完了', record.get('complete', False))
        object.__setattr__(self, '不足理由', record.get('failure'))
        object.__setattr__(self, '必要条件証明', record.get('necessity_guard', {}).get('proof'))
        if 監査 is not None:
            監査.update(deepcopy(record))

    def 候補(self, 格子, _policy):
        state = dict(schema=api.STATE_SCHEMA, programs=[list(p) for p in self.モデル群]) if self.モデル群 else None
        return api.predict(格子, state)

    def 記録(self):
        return {'保持候補': self.モデル群, '保持候補数': len(self.モデル群),
                '教師数': self.教師数, 'fit完了': self.完了, '不足理由': self.不足理由,
                '必要条件証明': self.必要条件証明, '事前支持数': 0,
                '合意条件': '全保持programと全所有・端点・lookupの成功および完全格子一致',
                '新規境界': '線端の箱を外色keyと元中心valueで一回同時参照'}
