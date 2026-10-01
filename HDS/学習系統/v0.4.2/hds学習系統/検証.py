from __future__ import annotations

from typing import Sequence

from .型 import 判定状態, 検証結果, 原理候補, 経験記録
from .推論 import 経験写像, 値キー


class 共通検証器:
    def __init__(self, 最小支持数: int = 3) -> None:
        self.最小支持数 = 最小支持数

    def 検証する(self, 候補: 原理候補, 経験群: Sequence[経験記録]) -> 検証結果:
        from .構造関係 import 構造関係型, 構造証拠を評価する, 構造支持条件
        if 候補.関係型 in 構造関係型:
            支持, 反証 = 構造証拠を評価する(候補, 経験群)
            distinct = {値キー(sorted(経験写像(e).items(), key=repr)) for e in 経験群 if e.経験識別子 in 支持}
            判定 = 判定状態.失敗 if 反証 else (判定状態.適合 if len(distinct) >= self.最小支持数 and 構造支持条件(候補, 経験群, 支持, self.最小支持数) else 判定状態.断定保留)
            return 検証結果(判定, '同型構造の全要素を既存観測と照合', 支持, 反証, len(distinct), len(候補.対応表))
        対応 = dict(候補.対応表)
        支持: list[str] = []
        反証: list[str] = []
        条件種類: set[tuple[str, ...]] = set()

        除外 = set(候補.除外経験参照群)
        for 経験 in 経験群:
            if 経験.対象系境界 != 候補.対象系境界 or 経験.経験識別子 in 除外:
                continue
            写像 = 経験写像(経験)
            if 候補.結果経路 not in 写像 or any(p not in 写像 for p in 候補.条件経路群):
                continue
            条件値 = tuple(値キー(写像[p]) for p in 候補.条件経路群)
            条件種類.add(条件値)

            if 候補.関係型 == "同値関係" and len(候補.条件経路群) == 1:
                if 写像[候補.条件経路群[0]] == 写像[候補.結果経路]:
                    支持.append(経験.経験識別子)
                else:
                    反証.append(経験.経験識別子)
                continue

            if 条件値 not in 対応:
                continue
            if 対応[条件値] == 値キー(写像[候補.結果経路]):
                支持.append(経験.経験識別子)
            else:
                反証.append(経験.経験識別子)

        支持集合 = set(支持)
        異なる支持観測 = {値キー(sorted(経験写像(e).items(), key=repr))
                          for e in 経験群 if e.経験識別子 in 支持集合}
        if 反証:
            return 検証結果(
                判定=判定状態.失敗,
                理由="適用範囲に反例がある",
                支持参照群=tuple(支持),
                反証参照群=tuple(反証),
                支持数=len(異なる支持観測),
                条件種類数=len(条件種類),
            )
        if 候補.関係型 == "定値関係":
            支持集合 = set(支持)
            独立観測 = {値キー(sorted(経験写像(e).items(), key=repr))
                        for e in 経験群 if e.経験識別子 in 支持集合}
            条件不足 = bool(候補.条件経路群) or len(独立観測) < self.最小支持数
        elif 候補.関係型 == "決定的対応関係":
            # 一条件値一観測の表は任意の偶然対応にも適合するため、採用しない。
            条件別観測: dict[tuple[str, ...], set[str]] = {}
            支持集合 = set(支持)
            for 経験 in 経験群:
                if 経験.経験識別子 not in 支持集合:
                    continue
                写像 = 経験写像(経験)
                条件 = tuple(値キー(写像[p]) for p in 候補.条件経路群)
                条件別観測.setdefault(条件, set()).add(値キー(sorted(写像.items(), key=repr)))
            条件不足 = len(条件種類) < 2 or any(len(rows) < 2 for rows in 条件別観測.values())
        else:
            条件不足 = len(条件種類) < 2
        if len(異なる支持観測) < self.最小支持数 or 条件不足:
            return 検証結果(
                判定=判定状態.断定保留,
                理由="支持数・条件種類・条件別独立観測が不足している",
                支持参照群=tuple(支持),
                支持数=len(異なる支持観測),
                条件種類数=len(条件種類),
            )
        return 検証結果(
            判定=判定状態.適合,
            理由="現観測範囲で関係が再現し、反例がない",
            支持参照群=tuple(支持),
            支持数=len(異なる支持観測),
            条件種類数=len(条件種類),
        )
