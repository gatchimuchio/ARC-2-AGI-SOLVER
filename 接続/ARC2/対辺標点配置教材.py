"""Explicit paired-key catalog placement boundary; unchanged HDS gates.

Retain every frozen126 teacher-fitting program and use the frozen129 consensus
without rescuing failed roles or programs. The bridge supplies an empty prior.
"""
from copy import deepcopy
from dataclasses import dataclass
from . import 対辺標点配置候補 as core


@dataclass(frozen=True, init=False, slots=True)
class 対辺標点配置教材:
    モデル群: tuple
    教師数: int
    適合数: int
    完了: bool
    不足理由: str | None

    def __init__(self, 教師群, 監査=None):
        programs, record = core.fit(教師群)
        object.__setattr__(self, 'モデル群', programs)
        object.__setattr__(self, '教師数', len(教師群))
        object.__setattr__(self, '適合数', len(programs))
        object.__setattr__(self, '完了', record.get('complete', False))
        object.__setattr__(self, '不足理由', record.get('failure'))
        if 監査 is not None:
            監査.update(deepcopy(record))

    def 候補(self, 格子, _policy):
        return core.consensus(格子, self.モデル群)

    def 記録(self):
        return {'保持候補': self.モデル群, '保持候補数': self.適合数,
                '教師数': self.教師数, '教師fit最小数': 2, 'fit完了': self.完了,
                '不足理由': self.不足理由,
                '合意条件': '全保持programと全構造役割の成功および完全格子一致',
                '新規境界': '完全source-mask鍵の対辺標点積と静的な非対応周囲装飾'}
