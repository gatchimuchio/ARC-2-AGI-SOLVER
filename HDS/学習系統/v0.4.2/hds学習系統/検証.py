from __future__ import annotations

from typing import Sequence

from .型 import 判定状態, 検証結果, 原理候補, 経験記録
from .推論 import 経験写像, 値キー


class 共通検証器:
    def __init__(self, 最小支持数: int = 3) -> None:
        self.最小支持数 = 最小支持数

    def 検証する(self, 候補: 原理候補, 経験群: Sequence[経験記録]) -> 検証結果:
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

        if 反証:
            return 検証結果(
                判定=判定状態.失敗,
                理由="適用範囲に反例がある",
                支持参照群=tuple(支持),
                反証参照群=tuple(反証),
                支持数=len(支持),
                条件種類数=len(条件種類),
            )
        if len(支持) < self.最小支持数 or len(条件種類) < 2:
            return 検証結果(
                判定=判定状態.断定保留,
                理由="支持数または条件種類が不足している",
                支持参照群=tuple(支持),
                支持数=len(支持),
                条件種類数=len(条件種類),
            )
        return 検証結果(
            判定=判定状態.適合,
            理由="現観測範囲で関係が再現し、反例がない",
            支持参照群=tuple(支持),
            支持数=len(支持),
            条件種類数=len(条件種類),
        )
