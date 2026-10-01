from __future__ import annotations

from pathlib import Path

from .型 import 外部入力, 外部出力, 原理記録
from .吸気系 import 最小吸気系
from .実行系 import HDS学習実行系
from .排気系 import 最小排気系


class HDS学習系統:
    """外界 → 吸気 → HDS学習実行系 → 排気 → 外界 を閉じる最小系統。"""

    def __init__(self, 最小支持数: int = 3, 最大条件数: int = 2, 数量関係有効: bool = True, 添字関係有効: bool = True) -> None:
        self.吸気系 = 最小吸気系()
        self.エンジン = HDS学習実行系(最小支持数=最小支持数, 最大条件数=最大条件数, 数量関係有効=数量関係有効, 添字関係有効=添字関係有効)
        self.排気系 = 最小排気系()

    def 処理する(self, 入力: 外部入力) -> 外部出力:
        学習入力 = self.吸気系.取り込む(入力)
        実行結果 = self.エンジン.実行(学習入力)
        return self.排気系.排出する(実行結果)

    def 照会する(self, 入力: 外部入力) -> 外部出力:
        学習入力 = self.吸気系.取り込む(入力)
        実行結果 = self.エンジン.照会(学習入力)
        return self.排気系.排出する(実行結果)

    def 係争を解決する(
        self,
        原理識別子: str,
        処置: str,
        理由: str,
        承認主体: str,
        審査対象反証参照群: tuple[str, ...] | None = None,
    ) -> 原理記録:
        return self.エンジン.係争を解決する(
            原理識別子, 処置, 理由, 承認主体, 審査対象反証参照群
        )

    def 保存する(self, 経路: str | Path) -> None:
        self.エンジン.保存する(経路)

    @classmethod
    def 読み込む(cls, 経路: str | Path) -> "HDS学習系統":
        エンジン = HDS学習実行系.読み込む(経路)
        系 = cls(最小支持数=エンジン.最小支持数, 最大条件数=エンジン.最大条件数)
        系.エンジン = エンジン
        return 系
