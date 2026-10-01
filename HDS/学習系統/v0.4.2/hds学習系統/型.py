from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class 学習成立状態(str, Enum):
    成立確認 = "成立確認"
    接続途上 = "接続途上"
    不成立確認 = "不成立確認"
    未確認 = "未確認"
    適用外 = "適用外"
    # v0.3互換エイリアス。意味の正本は「不成立確認」。
    未成立 = "不成立確認"


class 判定状態(str, Enum):
    適合 = "適合"
    断定保留 = "断定保留"
    失敗 = "失敗"


class 原理状態(str, Enum):
    原理候補 = "原理候補"
    適用範囲付き暫定原理 = "適用範囲付き暫定原理"
    # 旧保存形式互換用。v0.4.2以降の新規記録では使用しない。
    係争中 = "係争中"
    再開放済み = "再開放済み"
    反証済み = "反証済み"
    隔離済み = "隔離済み"


class 採用状態(str, Enum):
    提案済み = "提案済み"
    試行採用 = "試行採用"
    有効 = "有効"
    既定無効 = "既定無効"
    隔離 = "隔離"
    棄却済み = "棄却済み"
    新版移行済み = "新版移行済み"
    履歴保管済み = "履歴保管済み"


@dataclass(frozen=True)
class 外部入力:
    内容: Any
    対象系境界: str
    主体: str | None = None
    対象: str | None = None
    目的: str | None = None
    文脈: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class 観測事実:
    経路: tuple[str, ...]
    値: Any
    値型: str
    推論対象: bool = True


@dataclass(frozen=True)
class 学習入力:
    原入力: Any
    対象系境界: str
    観測群: tuple[観測事実, ...]
    主体: str | None = None
    対象: str | None = None
    目的: str | None = None
    文脈: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class 経験記録:
    経験識別子: str
    対象系境界: str
    原入力: Any
    観測群: tuple[観測事実, ...]
    主体: str | None
    対象: str | None
    目的: str | None
    時点: str


@dataclass(frozen=True)
class 懐疑記録:
    懐疑識別子: str
    経験参照: str
    焦点: str
    作用内容: str
    参照経験群: tuple[str, ...]
    時点: str
    対象経路群: tuple[tuple[str, ...], ...] = ()
    要求操作群: tuple[str, ...] = ()
    発火根拠: str = ""


@dataclass(frozen=True)
class 原理候補:
    候補識別子: str
    対象系境界: str
    関係型: str
    条件経路群: tuple[tuple[str, ...], ...]
    結果経路: tuple[str, ...]
    対応表: tuple[tuple[tuple[str, ...], str], ...]
    対応値表: tuple[tuple[tuple[str, ...], Any], ...]
    根拠参照群: tuple[str, ...]
    反証参照群: tuple[str, ...]
    懐疑参照群: tuple[str, ...]
    適用範囲: Mapping[str, Any]
    生成条件: Mapping[str, Any]
    # 観測自体は削除せず、特定原理系譜の明示審査で反証から除外された経験参照だけを
    # 同系譜の再学習・検証で尊重する。
    除外経験参照群: tuple[str, ...] = ()


@dataclass(frozen=True)
class 検証結果:
    判定: 判定状態
    理由: str
    支持参照群: tuple[str, ...] = ()
    反証参照群: tuple[str, ...] = ()
    支持数: int = 0
    条件種類数: int = 0


@dataclass(frozen=True)
class 原理記録:
    原理識別子: str
    対象系境界: str
    系譜識別子: str
    版: int
    状態: 原理状態
    関係型: str
    条件経路群: tuple[tuple[str, ...], ...]
    結果経路: tuple[str, ...]
    対応表: tuple[tuple[tuple[str, ...], str], ...]
    対応値表: tuple[tuple[tuple[str, ...], Any], ...]
    根拠参照群: tuple[str, ...]
    反証参照群: tuple[str, ...]
    適用範囲: Mapping[str, Any]
    再開放条件: tuple[str, ...]
    時点: str
    親原理参照: str | None = None
    改訂理由: str | None = None
    除外反証参照群: tuple[str, ...] = ()
    解決理由: str | None = None
    解決主体: str | None = None
    採用状態: 採用状態 = 採用状態.有効


@dataclass(frozen=True)
class 予測記録:
    原理参照: str
    結果経路: tuple[str, ...]
    予測値: Any
    条件値群: tuple[Any, ...]


@dataclass(frozen=True)
class 競合記録:
    結果経路: tuple[str, ...]
    候補値群: tuple[Any, ...]
    原理参照群: tuple[str, ...]


@dataclass(frozen=True)
class 追加観測要求:
    結果経路: tuple[str, ...]
    不足経路群: tuple[tuple[str, ...], ...]
    原理参照群: tuple[str, ...]
    理由: str = "関連する暫定原理を評価するための観測が不足している"
    未知条件値群: tuple[Any, ...] = ()


@dataclass(frozen=True)
class 識別不能記録:
    結果経路: tuple[str, ...]
    原理参照群: tuple[str, ...]
    条件経路群: tuple[tuple[tuple[str, ...], ...], ...]
    支持参照群: tuple[str, ...]
    反証参照群: tuple[str, ...]
    理由: str = "現観測では複数の関係候補を識別できない"


@dataclass(frozen=True)
class 学習過程記録:
    学習識別子: str
    学習前状態版: int
    学習後状態版: int
    経験参照: str
    懐疑参照群: tuple[str, ...]
    推論候補参照群: tuple[str, ...]
    採用原理参照群: tuple[str, ...]
    再開放原理参照群: tuple[str, ...]
    学習成立状態: 学習成立状態
    時点: str
    係争化原理参照群: tuple[str, ...] = ()
    状態変化理由群: tuple[str, ...] = ()
    対象系境界: str = ""
    主体参照: str | None = None
    対象期間: tuple[str, str] = ()
    学習前状態スナップショット: Mapping[str, str] = field(default_factory=dict)
    保持記憶参照群: tuple[str, ...] = ()
    更新記録参照群: tuple[str, ...] = ()
    観測限界: tuple[str, ...] = ()
    観測限界参照群: tuple[str, ...] = ()


@dataclass(frozen=True)
class 実行結果:
    学習過程: 学習過程記録
    現在状態版: int
    有効原理群: tuple[原理記録, ...]
    予測群: tuple[予測記録, ...]
    競合群: tuple[競合記録, ...]
    断定保留理由群: tuple[str, ...]
    追跡情報: Mapping[str, Any]
    係争中原理群: tuple[原理記録, ...] = ()
    追加観測要求群: tuple[追加観測要求, ...] = ()
    識別不能群: tuple[識別不能記録, ...] = ()


@dataclass(frozen=True)
class 外部出力:
    状態: str
    内容: Mapping[str, Any]
    追跡情報: Mapping[str, Any]
