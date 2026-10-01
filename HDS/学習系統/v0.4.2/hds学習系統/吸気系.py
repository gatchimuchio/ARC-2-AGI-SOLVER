from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .型 import 外部入力, 学習入力, 観測事実


内部予約接頭辞 = "@HDS:"


def _安定表現(値: Any) -> str:
    try:
        return json.dumps(値, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(値)


def _辞書キー経路要素(キー: Any) -> str:
    """型を失わず、HDS内部予約名前空間とも衝突しない経路表現。"""
    if isinstance(キー, str):
        if キー.startswith(内部予約接頭辞):
            return f'{内部予約接頭辞}利用者文字列:{_安定表現(キー)}'
        return キー
    return f'{内部予約接頭辞}キー:{type(キー).__name__}:{_安定表現(キー)}'


class 最小吸気系:
    """
    外部入力を意味解釈せず、原入力を保持したまま構造化観測へ変換する。
    内部メタ情報は保持するが推論主演算へは入れない。
    """

    def 取り込む(self, 入力: 外部入力) -> 学習入力:
        観測群: list[観測事実] = []
        self._平坦化(入力.内容, (), 観測群)
        return 学習入力(
            原入力=deepcopy(入力.内容),
            対象系境界=入力.対象系境界,
            観測群=tuple(観測群),
            主体=入力.主体,
            対象=入力.対象,
            目的=入力.目的,
            文脈=deepcopy(dict(入力.文脈)),
        )

    def _平坦化(self, 値: Any, 経路: tuple[str, ...], 出力: list[観測事実]) -> None:
        if isinstance(値, dict):
            出力.append(観測事実(経路 + (f"{内部予約接頭辞}構造",), "辞書", "構造", False))
            出力.append(観測事実(経路 + (f"{内部予約接頭辞}要素数",), len(値), "整数", False))
            項目群 = [(_辞書キー経路要素(k), k) for k in 値.keys()]
            for 経路要素, 元キー in sorted(項目群, key=lambda x: x[0]):
                self._平坦化(値[元キー], 経路 + (経路要素,), 出力)
            return
        if isinstance(値, (list, tuple)):
            出力.append(観測事実(経路 + (f"{内部予約接頭辞}構造",), "列", "構造", False))
            出力.append(観測事実(経路 + (f"{内部予約接頭辞}要素数",), len(値), "整数", False))
            for i, 要素 in enumerate(値):
                self._平坦化(要素, 経路 + (f"{内部予約接頭辞}索引:{i}",), 出力)
            return
        出力.append(観測事実(経路, deepcopy(値), self._型名(値), True))

    @staticmethod
    def _型名(値: Any) -> str:
        if 値 is None:
            return "無"
        if isinstance(値, bool):
            return "真偽"
        if isinstance(値, int):
            return "整数"
        if isinstance(値, float):
            return "実数"
        if isinstance(値, str):
            return "文字列"
        return type(値).__name__
