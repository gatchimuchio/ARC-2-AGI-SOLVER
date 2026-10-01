from __future__ import annotations

from itertools import combinations
import json
from typing import Any, Iterable, Sequence

from .型 import 経験記録, 原理候補, 原理記録, 原理状態, 懐疑記録


def 値キー(値: Any) -> str:
    try:
        return json.dumps(値, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(値)


def 経験写像(経験: 経験記録) -> dict[tuple[str, ...], Any]:
    return {観測.経路: 観測.値 for 観測 in 経験.観測群 if 観測.推論対象}


class 共通推論器:
    """
    懐疑操作が要求した意味操作だけを実行する最小共通推論器。
    現行射影では、比較・共通性・条件関係、条件追加、代替条件探索を実装する。
    """

    def __init__(self, 最大条件数: int = 2) -> None:
        self.最大条件数 = 最大条件数

    @staticmethod
    def _作用情報(懐疑群: Sequence[懐疑記録]) -> tuple[set[str], set[tuple[str, ...]], tuple[str, ...]]:
        操作: set[str] = set()
        対象: set[tuple[str, ...]] = set()
        参照: list[str] = []
        for 懐疑 in 懐疑群:
            操作.update(懐疑.要求操作群)
            if any(x in 懐疑.要求操作群 for x in ("条件関係生成", "条件追加探索", "代替条件探索")):
                対象.update(懐疑.対象経路群)
                参照.append(懐疑.懐疑識別子)
        return 操作, 対象, tuple(参照)

    def 導出する(
        self,
        経験群: Sequence[経験記録],
        懐疑群: Sequence[懐疑記録],
        最小支持数: int,
        識別子生成,
        継続原理群: Sequence[原理記録] = (),
    ) -> tuple[原理候補, ...]:
        if not 懐疑群:
            raise RuntimeError("推論起点欠落: 懐疑操作なしでは推論を実行できません")
        操作, 懐疑対象, 懐疑参照 = self._作用情報(懐疑群)
        if "条件関係生成" not in 操作:
            return ()

        写像群 = [(経験, 経験写像(経験)) for 経験 in 経験群]
        観測経路 = {経路 for _, 写像 in 写像群 for 経路 in 写像}
        全経路 = sorted(観測経路 & 懐疑対象 if 懐疑対象 else 観測経路, key=repr)
        候補群: list[原理候補] = []

        for 原理 in 継続原理群:
            if (
                原理.状態 == 原理状態.適用範囲付き暫定原理
                and 原理.除外反証参照群
                and 原理.対象系境界 == (経験群[0].対象系境界 if 経験群 else 原理.対象系境界)
            ):
                継続候補 = self._継続原理候補(
                    写像群, 原理, 懐疑参照, 最小支持数, 識別子生成
                )
                if 継続候補 is not None:
                    候補群.append(継続候補)

        許容条件数 = 1
        if "条件追加探索" in 操作 or "代替条件探索" in 操作:
            許容条件数 = self.最大条件数

        for 結果経路 in 全経路:
            条件候補 = [p for p in 全経路 if p != 結果経路]
            for 条件数 in range(1, min(許容条件数, len(条件候補)) + 1):
                for 条件経路群 in combinations(条件候補, 条件数):
                    候補 = self._決定的対応候補(
                        写像群, 条件経路群, 結果経路, 懐疑参照, 最小支持数, 識別子生成
                    )
                    if 候補 is not None:
                        候補群.append(候補)
        return tuple(self._重複除去(候補群))

    def 不成立を確認する(
        self,
        経験群: Sequence[経験記録],
        懐疑群: Sequence[懐疑記録],
        最小支持数: int,
        有効原理群: Sequence[原理記録] = (),
    ) -> bool:
        if len(経験群) < 最小支持数 or not 懐疑群:
            return False
        対象系境界 = 経験群[0].対象系境界 if 経験群 else None
        最新写像 = 経験写像(経験群[-1]) if 経験群 else {}
        関連原理 = tuple(
            p for p in 有効原理群
            if (対象系境界 is None or p.対象系境界 == 対象系境界)
            and all(path in 最新写像 for path in p.条件経路群)
        )
        if 関連原理:
            return False
        判定経験群 = tuple(経験群)
        操作, 懐疑対象, _ = self._作用情報(懐疑群)
        if "条件関係生成" not in 操作:
            return False
        写像群 = [(e, 経験写像(e)) for e in 判定経験群]
        観測経路 = {p for _, m in 写像群 for p in m}
        全経路 = sorted(観測経路 & 懐疑対象 if 懐疑対象 else 観測経路, key=repr)
        十分観測組 = 0
        for 結果経路 in 全経路:
            for 条件経路 in (p for p in 全経路 if p != 結果経路):
                対応: dict[str, str] = {}
                完全数 = 0
                条件種類: set[str] = set()
                矛盾 = False
                for _, 写像 in 写像群:
                    if 条件経路 not in 写像 or 結果経路 not in 写像:
                        continue
                    完全数 += 1
                    c = 値キー(写像[条件経路])
                    r = 値キー(写像[結果経路])
                    条件種類.add(c)
                    if c in 対応 and 対応[c] != r:
                        矛盾 = True
                    else:
                        対応[c] = r
                if 完全数 >= 最小支持数 and len(条件種類) >= 2:
                    十分観測組 += 1
                    if not 矛盾:
                        return False
        return 十分観測組 > 0

    def _継続原理候補(
        self,
        写像群,
        原理: 原理記録,
        懐疑参照,
        最小支持数,
        識別子生成,
    ) -> 原理候補 | None:
        除外 = set(原理.除外反証参照群)
        対応: dict[tuple[str, ...], str] = {}
        対応値: dict[tuple[str, ...], Any] = {}
        根拠: list[str] = []
        条件種類: set[tuple[str, ...]] = set()

        for 経験, 写像 in 写像群:
            if 経験.経験識別子 in 除外:
                continue
            if 原理.結果経路 not in 写像 or any(p not in 写像 for p in 原理.条件経路群):
                continue
            条件値 = tuple(値キー(写像[p]) for p in 原理.条件経路群)
            結果値キー = 値キー(写像[原理.結果経路])
            条件種類.add(条件値)
            根拠.append(経験.経験識別子)

            if 原理.関係型 == "同値関係" and len(原理.条件経路群) == 1:
                if 写像[原理.条件経路群[0]] != 写像[原理.結果経路]:
                    return None
                対応[条件値] = 結果値キー
                対応値[条件値] = 写像[原理.結果経路]
                continue

            if 条件値 in 対応 and 対応[条件値] != 結果値キー:
                return None
            対応[条件値] = 結果値キー
            対応値[条件値] = 写像[原理.結果経路]

        if len(根拠) < 最小支持数 or len(条件種類) < 2:
            return None

        return 原理候補(
            候補識別子=識別子生成("原理候補"),
            対象系境界=原理.対象系境界,
            関係型=原理.関係型,
            条件経路群=原理.条件経路群,
            結果経路=原理.結果経路,
            対応表=tuple(sorted(対応.items(), key=repr)),
            対応値表=tuple(sorted(対応値.items(), key=repr)),
            根拠参照群=tuple(dict.fromkeys(根拠)),
            反証参照群=(),
            懐疑参照群=tuple(懐疑参照),
            適用範囲={
                **dict(原理.適用範囲),
                "再学習": "明示審査済み除外判断を当該系譜だけで継承",
                "条件種類数": len(条件種類),
            },
            生成条件={
                "作用": "懐疑→既存原理系譜の再開放・再学習",
                "因果断定": False,
                "継承元原理": 原理.原理識別子,
            },
            除外経験参照群=tuple(原理.除外反証参照群),
        )

    def _決定的対応候補(
        self,
        写像群,
        条件経路群,
        結果経路,
        懐疑参照,
        最小支持数,
        識別子生成,
    ) -> 原理候補 | None:
        対応: dict[tuple[str, ...], str] = {}
        対応値: dict[tuple[str, ...], Any] = {}
        根拠: list[str] = []
        反証: list[str] = []
        条件種類: set[tuple[str, ...]] = set()
        同値 = len(条件経路群) == 1

        for 経験, 写像 in 写像群:
            if 結果経路 not in 写像 or any(p not in 写像 for p in 条件経路群):
                continue
            条件値 = tuple(値キー(写像[p]) for p in 条件経路群)
            結果値キー = 値キー(写像[結果経路])
            条件種類.add(条件値)
            根拠.append(経験.経験識別子)
            if 条件値 in 対応 and 対応[条件値] != 結果値キー:
                反証.append(経験.経験識別子)
            else:
                対応[条件値] = 結果値キー
                対応値[条件値] = 写像[結果経路]
            if 同値 and 写像[条件経路群[0]] != 写像[結果経路]:
                同値 = False

        if len(根拠) < 最小支持数 or len(条件種類) < 2 or 反証:
            return None

        関係型 = "同値関係" if 同値 else "決定的対応関係"
        対象系境界 = 写像群[0][0].対象系境界 if 写像群 else "未指定"
        return 原理候補(
            候補識別子=識別子生成("原理候補"),
            対象系境界=対象系境界,
            関係型=関係型,
            条件経路群=tuple(条件経路群),
            結果経路=結果経路,
            対応表=tuple(sorted(対応.items(), key=repr)),
            対応値表=tuple(sorted(対応値.items(), key=repr)),
            根拠参照群=tuple(dict.fromkeys(根拠)),
            反証参照群=(),
            懐疑参照群=tuple(懐疑参照),
            適用範囲={
                "確認範囲": "同値関係は値一般へ転用候補、決定的対応関係は観測済み条件値",
                "条件数": len(条件経路群),
                "条件種類数": len(条件種類),
            },
            生成条件={
                "作用": "懐疑→比較・共通性・条件関係",
                "因果断定": False,
            },
        )

    @staticmethod
    def _重複除去(候補群: Iterable[原理候補]) -> Iterable[原理候補]:
        既出: set[tuple[Any, ...]] = set()
        for 候補 in 候補群:
            鍵 = (候補.関係型, 候補.条件経路群, 候補.結果経路, 候補.対応表)
            if 鍵 in 既出:
                continue
            既出.add(鍵)
            yield 候補
