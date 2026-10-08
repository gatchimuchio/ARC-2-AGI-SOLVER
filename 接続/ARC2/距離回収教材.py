"""全教師適合した全有限距離回収モデルを保持し、全モデル合意だけを候補とする。"""
from __future__ import annotations
from .二軸補完教材 import valid_grid
from . import 距離回収候補 as core
from . import 門経路再構成候補 as gate_path


def 距離回収をfit(教師群):
    if not isinstance(教師群, list) or len(教師群) < 2:
        return [], {'failure': 'too_few_teachers'}
    if any(not isinstance(対, dict) or not valid_grid(対.get('input'))
           or not valid_grid(対.get('output')) for 対 in 教師群):
        return [], {'failure': 'invalid_teachers'}
    入力群 = [tuple(map(tuple, 対['input'])) for 対 in 教師群]
    if len(set(入力群)) != len(入力群):
        return [], {'failure': 'duplicate_teacher_inputs'}
    if any((len(対['input']),len(対['input'][0])) !=
           (len(対['output']),len(対['output'][0])) for 対 in 教師群):
        return [], {'failure': 'teacher_shape_not_preserved'}
    return core.fit(教師群)


def 全距離モデルを照会(格子, モデル群):
    if not モデル群:
        return None, {'failure': 'no_teacher_fit_model', 'retained_results': []}
    結果 = [core.render(格子, m['roles'], m['parameters'], m['shape']) for m in モデル群]
    全記録 = [{'model_index': i, 'candidate': out, 'detail': rec}
             for i, (out, rec) in enumerate(結果)]
    失敗群 = [rec for out, rec in 結果 if out is None]
    格子群 = {tuple(map(tuple, out)) for out, rec in 結果 if out is not None}
    if 失敗群:
        return None, {'failure': 'fitted_model_hold', 'models': len(モデル群),
                      'failures': 失敗群, 'retained_results': 全記録}
    if len(格子群) != 1:
        return None, {'failure': 'fitted_models_disagree', 'output_count': len(格子群),
                      'retained_results': 全記録}
    return [list(row) for row in next(iter(格子群))], {
        'models': len(モデル群), 'records': [rec for out, rec in 結果], 'retained_results': 全記録}


class 距離回収教材:
    def __init__(self, 教師群):
        モデル, 診断 = 距離回収をfit(教師群)
        self.モデル群 = tuple((tuple(m['roles'][k] for k in core.ROLE_NAMES),
                          tuple(m['shape']), tuple(m['parameters'][k] for k in core.AXES))
                         for m in モデル)
        self.門経路モデル群 = ()
        if not モデル and 診断 == {'failure': 'union_not_five_role_colors'}:
            経路モデル, _ = gate_path.fit(教師群)
            self.門経路モデル群 = gate_path.freeze(経路モデル)

    def 展開モデル(self):
        return [{'roles': dict(zip(core.ROLE_NAMES, 役割)), 'shape': list(形),
                 'parameters': dict(zip(core.AXES, 条件))}
                for 役割, 形, 条件 in self.モデル群]

    def 候補(self, 格子, _policy):
        if self.門経路モデル群:
            return gate_path.consensus(格子, gate_path.thaw(self.門経路モデル群))
        return 全距離モデルを照会(格子, self.展開モデル())

    def 記録(self):
        if self.門経路モデル群:
            return {'保持候補数': len(self.門経路モデル群),
                    '保持候補': gate_path.thaw(self.門経路モデル群),
                    '新規再構成': '教師適合した全D4門・完全C4経路モデルの完全格子合意'}
        return {'保持候補数': len(self.モデル群), '保持候補': self.展開モデル(),
                '合意条件': '全教師適合モデル全ての成功と完全格子一致。失敗モデルを除外しない'}
