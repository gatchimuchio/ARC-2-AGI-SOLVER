from __future__ import annotations

from typing import Any, Sequence

from .型 import (
    原理候補,
    原理記録,
    原理状態,
    採用状態,
    経験記録,
    予測記録,
    競合記録,
    追加観測要求,
    識別不能記録,
)
from .推論 import 経験写像, 値キー


def 系譜鍵(対象系境界: str, 関係型: str, 条件経路群, 結果経路) -> str:
    return repr((対象系境界, 関係型, tuple(条件経路群), tuple(結果経路)))


def 原理証拠を評価する(原理: 原理記録, 経験群: Sequence[経験記録]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """関係型の意味に従って支持・反証を再計算する。未観測はどちらにも数えない。"""
    from .数量関係 import 数量関係型, 数量証拠
    if 原理.関係型 == 数量関係型:
        support, counters, _ = 数量証拠(原理, 経験群)
        return support, counters
    from .構造関係 import 構造関係型, 構造証拠を評価する
    if 原理.関係型 in 構造関係型:
        return 構造証拠を評価する(原理, 経験群)
    対応 = dict(原理.対応表)
    除外 = set(原理.除外反証参照群)
    支持: list[str] = []
    反証: list[str] = []
    for 経験 in 経験群:
        if 経験.対象系境界 != 原理.対象系境界 or 経験.経験識別子 in 除外:
            continue
        from .構造関係 import 定値文脈が適合
        if 原理.関係型 == "定値関係" and not 定値文脈が適合(原理, 経験.原入力):
            continue
        写像 = 経験写像(経験)
        if 原理.結果経路 not in 写像 or any(p not in 写像 for p in 原理.条件経路群):
            continue

        if 原理.関係型 == "同値関係" and len(原理.条件経路群) == 1:
            if 写像[原理.条件経路群[0]] == 写像[原理.結果経路]:
                支持.append(経験.経験識別子)
            else:
                反証.append(経験.経験識別子)
            continue

        条件値 = tuple(値キー(写像[p]) for p in 原理.条件経路群)
        if 条件値 not in 対応:
            continue
        if 対応[条件値] == 値キー(写像[原理.結果経路]):
            支持.append(経験.経験識別子)
        else:
            反証.append(経験.経験識別子)
    return tuple(支持), tuple(反証)


class 共通適応器:
    def __init__(self):
        self.数量関係有効 = True

    def 原理化する(
        self,
        候補: 原理候補,
        旧原理: 原理記録 | None,
        識別子生成,
        *,
        時点: str,
        親原理参照: str | None = None,
        改訂理由: str | None = None,
    ) -> 原理記録:
        版 = 1 if 旧原理 is None else 旧原理.版 + 1
        系譜 = 系譜鍵(候補.対象系境界, 候補.関係型, 候補.条件経路群, 候補.結果経路)
        return 原理記録(
            原理識別子=識別子生成("原理"),
            対象系境界=候補.対象系境界,
            系譜識別子=系譜,
            版=版,
            状態=原理状態.適用範囲付き暫定原理,
            関係型=候補.関係型,
            条件経路群=候補.条件経路群,
            結果経路=候補.結果経路,
            対応表=候補.対応表,
            対応値表=候補.対応値表,
            根拠参照群=候補.根拠参照群,
            反証参照群=(),
            適用範囲=候補.適用範囲,
            再開放条件=("関係意味に反する新経験", "より強い条件関係の成立", "識別不能性を解く新観測"),
            時点=時点,
            親原理参照=親原理参照,
            改訂理由=改訂理由,
            除外反証参照群=tuple(dict.fromkeys(
                (() if 旧原理 is None else 旧原理.除外反証参照群) + 候補.除外経験参照群
            )),
            採用状態=採用状態.有効,
        )

    def 反証を検出する(self, 原理: 原理記録, 新経験: 経験記録) -> bool:
        if 原理.対象系境界 != 新経験.対象系境界 or 新経験.経験識別子 in set(原理.除外反証参照群):
            return False
        from .数量関係 import 数量関係型, 数量証拠
        if 原理.関係型 == 数量関係型:
            return bool(数量証拠(原理, (新経験,))[1])
        from .構造関係 import 構造関係型, 構造証拠を評価する
        if 原理.関係型 in 構造関係型:
            return bool(構造証拠を評価する(原理, (新経験,))[1])
        from .構造関係 import 定値文脈が適合
        if 原理.関係型 == "定値関係" and not 定値文脈が適合(原理, 新経験.原入力):
            return False
        写像 = 経験写像(新経験)
        if 原理.結果経路 not in 写像 or any(p not in 写像 for p in 原理.条件経路群):
            return False
        if 原理.関係型 == "同値関係" and len(原理.条件経路群) == 1:
            return 写像[原理.条件経路群[0]] != 写像[原理.結果経路]
        条件値 = tuple(値キー(写像[p]) for p in 原理.条件経路群)
        対応 = dict(原理.対応表)
        if 条件値 not in 対応:
            return False
        return 対応[条件値] != 値キー(写像[原理.結果経路])

    def 予測する(
        self,
        原理群: Sequence[原理記録],
        新経験: 経験記録,
    ) -> tuple[tuple[予測記録, ...], tuple[競合記録, ...], tuple[追加観測要求, ...]]:
        写像 = 経験写像(新経験)
        予測群: list[予測記録] = []
        観測要求候補: list[追加観測要求] = []

        for 原理 in 原理群:
            if 原理.対象系境界 != 新経験.対象系境界:
                continue
            if 原理.状態 != 原理状態.適用範囲付き暫定原理 or 原理.採用状態 != 採用状態.有効:
                continue
            from .構造関係 import 構造関係型, 容器群, 構造を予測する, 定値文脈が適合
            from .数量関係 import 数量関係型, 数量写像, 数量を計算する
            if 原理.関係型 == 数量関係型:
                if not self.数量関係有効:
                    continue
                quantities = 数量写像(新経験)
                if 原理.結果経路 in 写像:
                    continue
                try:
                    source = quantities[原理.条件経路群[0]]
                    value = 数量を計算する(原理, source)
                except (KeyError, ValueError):
                    観測要求候補.append(追加観測要求(原理.結果経路, 原理.条件経路群, (原理.原理識別子,), '数量型・外挿範囲・整数閉包が未成立'))
                    continue
                予測群.append(予測記録(原理.原理識別子, 原理.結果経路, value, (source,)))
                continue
            if 原理.関係型 == "定値関係" and not 定値文脈が適合(原理, 新経験.原入力):
                観測要求候補.append(追加観測要求(原理.結果経路, (), (原理.原理識別子,), "定値仮説の入力構造文脈が確認範囲外"))
                continue
            if 原理.関係型 in 構造関係型:
                containers = 容器群(新経験.原入力)
                if 原理.結果経路 in containers:
                    continue
                source = containers.get(原理.条件経路群[0])
                if source is None:
                    観測要求候補.append(追加観測要求(原理.結果経路, 原理.条件経路群, (原理.原理識別子,), '構造関係の入力容器が未観測'))
                    continue
                try:
                    predicted = 構造を予測する(原理, source)
                except (KeyError, ValueError):
                    観測要求候補.append(追加観測要求(原理.結果経路, (), (原理.原理識別子,), '構造関係の値または型が確認範囲外'))
                    continue
                予測群.append(予測記録(原理.原理識別子, 原理.結果経路, predicted, (source,)))
                continue
            if 原理.結果経路 in 写像:
                continue

            不足 = tuple(p for p in 原理.条件経路群 if p not in 写像)
            if 不足:
                観測要求候補.append(追加観測要求(
                    結果経路=原理.結果経路,
                    不足経路群=不足,
                    原理参照群=(原理.原理識別子,),
                    理由="暫定原理を評価する条件経路が未観測",
                ))
                continue

            条件値生 = tuple(写像[p] for p in 原理.条件経路群)
            条件値 = tuple(値キー(v) for v in 条件値生)
            対応値 = dict(原理.対応値表)
            if 原理.関係型 == "同値関係" and len(条件値生) == 1:
                予測値 = 条件値生[0]
            elif 条件値 in 対応値:
                予測値 = 対応値[条件値]
            else:
                観測要求候補.append(追加観測要求(
                    結果経路=原理.結果経路,
                    不足経路群=(),
                    原理参照群=(原理.原理識別子,),
                    理由="条件経路は観測済みだが、この条件値は暫定原理の確認範囲外。結果観測が必要",
                    未知条件値群=条件値生,
                ))
                continue
            予測群.append(予測記録(
                原理参照=原理.原理識別子,
                結果経路=原理.結果経路,
                予測値=予測値,
                条件値群=条件値生,
            ))

        競合群: list[競合記録] = []
        経路別: dict[tuple[str, ...], list[予測記録]] = {}
        for 予測 in 予測群:
            経路別.setdefault(予測.結果経路, []).append(予測)
        for 経路, 同経路予測 in 経路別.items():
            値集合: list[Any] = []
            値キー集合: set[str] = set()
            for p in 同経路予測:
                from .構造関係 import 容器署名
                k = 容器署名(p.予測値) if isinstance(p.予測値, (dict, list, tuple)) else 値キー(p.予測値)
                if k not in 値キー集合:
                    値キー集合.add(k)
                    値集合.append(p.予測値)
            if len(値集合) > 1:
                競合群.append(競合記録(
                    結果経路=経路,
                    候補値群=tuple(値集合),
                    原理参照群=tuple(p.原理参照 for p in 同経路予測),
                ))
        from .構造関係 import 予測重複を監査する
        構造競合, 除外位置 = 予測重複を監査する(予測群)
        競合群.extend(構造競合)
        競合経路 = {x.結果経路 for x in 競合群}
        確定予測 = tuple(p for i, p in enumerate(予測群) if p.結果経路 not in 競合経路 and i not in 除外位置)

        統合: dict[tuple[Any, ...], 追加観測要求] = {}
        for r in 観測要求候補:
            鍵 = (r.結果経路, r.不足経路群, tuple(値キー(v) for v in r.未知条件値群), r.理由)
            if 鍵 not in 統合:
                統合[鍵] = r
            else:
                既 = 統合[鍵]
                統合[鍵] = 追加観測要求(
                    結果経路=既.結果経路,
                    不足経路群=既.不足経路群,
                    原理参照群=tuple(dict.fromkeys(既.原理参照群 + r.原理参照群)),
                    理由=既.理由,
                    未知条件値群=既.未知条件値群,
                )
        return 確定予測, tuple(競合群), tuple(統合.values())

    def 識別不能を検出する(
        self,
        原理群: Sequence[原理記録],
        経験群: Sequence[経験記録],
    ) -> tuple[識別不能記録, ...]:
        群: dict[tuple[Any, ...], list[原理記録]] = {}
        for 原理 in 原理群:
            if 原理.状態 != 原理状態.適用範囲付き暫定原理 or 原理.採用状態 != 採用状態.有効:
                continue
            支持, 反証 = 原理証拠を評価する(原理, 経験群)
            鍵 = (原理.対象系境界, 原理.結果経路, tuple(sorted(支持)), tuple(sorted(反証)))
            群.setdefault(鍵, []).append(原理)

        結果: list[識別不能記録] = []
        for (_, 結果経路, 支持, 反証), 原理一覧 in 群.items():
            条件集合 = {tuple(x.条件経路群) for x in 原理一覧}
            if len(条件集合) < 2:
                continue
            非包含組あり = False
            for i, a in enumerate(原理一覧):
                sa = set(a.条件経路群)
                for b in 原理一覧[i + 1:]:
                    sb = set(b.条件経路群)
                    if not (sa <= sb or sb <= sa):
                        非包含組あり = True
                        break
                if 非包含組あり:
                    break
            if not 非包含組あり:
                continue
            結果.append(識別不能記録(
                結果経路=結果経路,
                原理参照群=tuple(x.原理識別子 for x in 原理一覧),
                条件経路群=tuple(tuple(x.条件経路群) for x in 原理一覧),
                支持参照群=tuple(支持),
                反証参照群=tuple(反証),
            ))
        return tuple(結果)
