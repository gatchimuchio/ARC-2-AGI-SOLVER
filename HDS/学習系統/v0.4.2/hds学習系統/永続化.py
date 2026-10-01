from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from . import 型 as 型定義


def _型表() -> dict[str, type]:
    表: dict[str, type] = {}
    for 名 in dir(型定義):
        対象 = getattr(型定義, 名)
        if isinstance(対象, type) and (is_dataclass(対象) or issubclass_safe(対象, Enum)):
            表[名] = 対象
    return 表


def issubclass_safe(対象: Any, 親: type) -> bool:
    try:
        return issubclass(対象, 親)
    except TypeError:
        return False


def _符号化(x: Any) -> Any:
    if isinstance(x, Enum):
        return {"__列挙__": type(x).__name__, "値": x.value}
    if is_dataclass(x):
        return {
            "__データ型__": type(x).__name__,
            "値": {f.name: _符号化(getattr(x, f.name)) for f in fields(x)},
        }
    if isinstance(x, tuple):
        return {"__組__": [_符号化(v) for v in x]}
    if isinstance(x, list):
        return [_符号化(v) for v in x]
    if isinstance(x, dict):
        return {"__辞書__": [[_符号化(k), _符号化(v)] for k, v in x.items()]}
    return x


def _復号(x: Any, 型表=None) -> Any:
    # 一回の復号で型登録を固定。別の読込では必ず新しく構築する。
    if 型表 is None:
        型表 = _型表()
    if isinstance(x, list):
        return [_復号(v, 型表) for v in x]
    if not isinstance(x, dict):
        return x
    if "__列挙__" in x:
        cls = 型表[x["__列挙__"]]
        return cls(x["値"])
    if "__データ型__" in x:
        cls = 型表[x["__データ型__"]]
        値 = {k: _復号(v, 型表) for k, v in x["値"].items()}
        return cls(**値)
    if "__組__" in x:
        return tuple(_復号(v, 型表) for v in x["__組__"])
    if "__辞書__" in x:
        return {_復号(k, 型表): _復号(v, 型表) for k, v in x["__辞書__"]}
    return {k: _復号(v, 型表) for k, v in x.items()}


def 書き出す(実行系: Any, 経路: Path) -> None:
    内容 = {
        "形式版": 8,
        "最小支持数": 実行系.最小支持数,
        "最大条件数": 実行系.最大条件数,
        "数量関係有効": 実行系.数量関係有効,
        "添字関係有効": 実行系.添字関係有効,
        "関係合成有効": 実行系.関係合成有効,
        "最大合成段数": 実行系.最大合成段数,
        "最大合成候補数": 実行系.最大合成候補数,
        "識別子状態": 実行系.識別子.状態を書き出す(),
        "台帳": 実行系.台帳.全取得(),
        "状態履歴": 実行系.状態.履歴(),
        "原理履歴": 実行系._原理履歴,
    }
    # 内容・形式はそのまま。全JSON文字列の同時保持を避け、完成fileだけ公開する。
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=経路.parent,
                                         prefix="." + 経路.name + ".", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(_符号化(内容), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, 経路)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def 読み込む(経路: Path, 実行系型: type) -> Any:
    内容 = _復号(json.loads(経路.read_text(encoding="utf-8")))
    if 内容.get("形式版") not in (1, 2, 3, 4, 5, 6, 7, 8):
        raise ValueError("未対応の永続化形式版です")
    実行系 = 実行系型(最小支持数=int(内容["最小支持数"]), 最大条件数=int(内容["最大条件数"]),
                      数量関係有効=内容.get("数量関係有効", True), 添字関係有効=内容.get("添字関係有効", True), 関係合成有効=内容.get("関係合成有効", False),
                      最大合成段数=内容.get("最大合成段数", 4), 最大合成候補数=内容.get("最大合成候補数", 4096))
    実行系.識別子.状態を復元する(dict(内容["識別子状態"]))
    実行系.台帳.状態を復元する({k: list(v) for k, v in 内容["台帳"].items()})
    実行系.状態.状態を復元する([dict(x) for x in 内容["状態履歴"]])
    実行系._原理履歴 = {str(k): list(v) for k, v in 内容["原理履歴"].items()}
    return 実行系
