"""教師と学習機械の値境界。問題ID・正解は予測要求に存在しない。"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

格子 = tuple[tuple[int, ...], ...]

def 格子化(value: Any) -> 格子:
    if not isinstance(value, (tuple, list)) or not 1 <= len(value) <= 30:
        raise ValueError('格子の行数は1..30')
    if not all(isinstance(row, (tuple, list)) for row in value):
        raise ValueError('各行は列')
    width = len(value[0])
    if not 1 <= width <= 30 or any(len(row) != width for row in value):
        raise ValueError('格子は1..30列の矩形')
    if any(type(cell) is not int or not 0 <= cell <= 9 for row in value for cell in row):
        raise ValueError('色は整数0..9')
    return tuple(tuple(row) for row in value)

@dataclass(frozen=True, slots=True)
class 予測要求:
    入力: 格子
    def __post_init__(self):
        object.__setattr__(self, '入力', 格子化(self.入力))

@dataclass(frozen=True, slots=True)
class 予測:
    状態: str
    出力: 格子 | None
    理由: tuple[str, ...]
    使用原理: tuple[str, ...] = ()
    推定済み項目数: int = 0

@dataclass(frozen=True, slots=True)
class 結果通知:
    """採点結果のみ。評価用正解の格子は持たない。"""
    正解: bool
    予測状態: str
