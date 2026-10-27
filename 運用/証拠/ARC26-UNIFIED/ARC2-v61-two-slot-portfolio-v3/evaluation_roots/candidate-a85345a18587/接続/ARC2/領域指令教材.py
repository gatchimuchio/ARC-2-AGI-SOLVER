"""Teacher-only region-command composition with ordinary HDS support, empty prior.

Every renderer preserves input colors and canvas up to a quarter turn:
marker/cue erasure uses an observed host color; transfer uses an observed
payload; transform_grid_by_name only permutes cells. Thus an output with new
colors or dimensions neither equal nor reversed cannot fit any model.
No exception conversion, fallback, support inflation, or runtime data access.
"""
from copy import deepcopy
from dataclasses import asdict
from . import 領域指令核 as api


def fit(teachers):
    if (not isinstance(teachers, list) or len(teachers) < 2
            or any(not isinstance(p, dict) or not api.valid(p.get('input'))
                   or not api.valid(p.get('output')) for p in teachers)):
        return api.fit_teachers(teachers)
    witnesses = []
    for i, pair in enumerate(teachers):
        shape = (len(pair['input']), len(pair['input'][0]))
        target_shape = (len(pair['output']), len(pair['output'][0]))
        novel = set(v for row in pair['output'] for v in row) - set(v for row in pair['input'] for v in row)
        if target_shape not in (shape, shape[::-1]) or novel:
            witnesses.append(dict(teacher=i, input_shape=shape, output_shape=target_shape,
                                  novel_colors=sorted(novel)))
    if witnesses:
        return None, dict(complete=True, reason='teacher_rotation_shape_or_palette_impossible',
                          retained_models=[], necessity_guard=dict(
                              proof='every_model_preserves_canvas_up_to_quarter_turn_and_input_palette',
                              all_models_impossible=True, witnesses=witnesses, parse_calls=0))
    return api.fit_teachers(teachers)


class 領域指令教材:
    __slots__ = ('fitted', 'teacher_count', 'complete', 'failure', 'necessity')

    def __init__(self, teachers, audit=None):
        fitted, record = fit(teachers)
        self.fitted = fitted
        self.teacher_count = len(teachers) if isinstance(teachers, list) else 0
        self.complete = record.get('complete', False)
        self.failure = record.get('reason')
        self.necessity = record.get('necessity_guard', {}).get('proof')
        if audit is not None:
            audit.update(deepcopy(record))

    def 候補(self, grid, _policy):
        return api.predict(grid, self.fitted)

    def 記録(self):
        models = [asdict(m) for m in self.fitted.models] if self.fitted is not None else []
        return {'保持候補': models, '保持候補数': len(models), '教師数': self.teacher_count,
                'fit完了': self.complete, '不足理由': self.failure,
                '必要条件証明': self.necessity, '事前支持数': 0,
                '合意条件': '全保持モデル・全適格解釈の成功と役割および完全格子一致',
                '新規境界': '標識所有と同時領域転写および任意隅cue旋回'}
