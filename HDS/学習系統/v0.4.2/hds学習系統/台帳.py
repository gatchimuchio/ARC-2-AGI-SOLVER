from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from typing import Any


class 識別子生成器:
    def __init__(self) -> None:
        self._番号: dict[str, int] = {}

    def 次(self, 種別: str) -> str:
        値 = self._番号.get(種別, 0) + 1
        self._番号[種別] = 値
        return f"{種別}-{値:06d}"

    def 状態を書き出す(self) -> dict[str, int]:
        return deepcopy(self._番号)

    def 状態を復元する(self, 状態: dict[str, int]) -> None:
        self._番号 = {str(k): int(v) for k, v in 状態.items()}


class 追記専用台帳:
    def __init__(self) -> None:
        self._台帳: dict[str, list[Any]] = {}

    def 追記(self, 台帳名: str, 記録: Any) -> None:
        self._台帳.setdefault(台帳名, []).append(deepcopy(記録))

    def 取得(self, 台帳名: str) -> tuple[Any, ...]:
        return tuple(deepcopy(self._台帳.get(台帳名, ())))

    def 件数(self, 台帳名: str) -> int:
        return len(self._台帳.get(台帳名, ()))

    def 全取得(self) -> dict[str, tuple[Any, ...]]:
        return {名: tuple(deepcopy(値)) for 名, 値 in self._台帳.items()}

    def 状態を復元する(self, 状態: dict[str, list[Any]]) -> None:
        self._台帳 = {str(名): [deepcopy(x) for x in 値] for 名, 値 in 状態.items()}

    def JSON相当(self) -> dict[str, list[Any]]:
        def 変換(x: Any) -> Any:
            if is_dataclass(x):
                return {k: 変換(v) for k, v in asdict(x).items()}
            if isinstance(x, dict):
                return {str(k): 変換(v) for k, v in x.items()}
            if isinstance(x, (list, tuple)):
                return [変換(v) for v in x]
            if hasattr(x, "value"):
                return 変換(x.value)
            return x
        return {名: [変換(v) for v in 値] for 名, 値 in self._台帳.items()}


class 状態管理器:
    """現行原理の集合を版付きで保持する。旧版は削除しない。"""

    def __init__(self) -> None:
        self._履歴: list[dict[str, str]] = [{}]

    @property
    def 現在版(self) -> int:
        return len(self._履歴) - 1

    @property
    def 現在状態(self) -> dict[str, str]:
        return deepcopy(self._履歴[-1])

    def 更新(self, 新状態: dict[str, str]) -> tuple[int, int]:
        前 = self.現在版
        if 新状態 == self._履歴[-1]:
            return 前, 前
        self._履歴.append(deepcopy(新状態))
        return 前, self.現在版

    def 履歴(self) -> tuple[dict[str, str], ...]:
        return tuple(deepcopy(self._履歴))

    def 状態を復元する(self, 履歴: list[dict[str, str]]) -> None:
        self._履歴 = [deepcopy(x) for x in 履歴] or [{}]
