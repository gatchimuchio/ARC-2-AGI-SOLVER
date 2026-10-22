#!/usr/bin/env python3
"""ファイルと現在状態の構造契約を検査する。解答性能の検証は行わない。"""

from __future__ import annotations

import json
from pathlib import Path

ルート = Path(__file__).resolve().parents[1]
必須 = (
    "README.md",
    "AGENTS.md",
    "制御/現在状態.json",
    "運用/権限順序.md",
    "入力/公式サンプル/マニフェスト.json",
    "戦略/README.md",
    "検証/README.md",
)
禁止 = ("ミニドラ", "設計/AGI三主体構成.md", "設計/共通知能基盤")


def 失敗(理由: str) -> None:
    raise SystemExit("リポジトリ環境監査失敗: " + 理由)


def 現在状態確認(状態: object) -> None:
    if not isinstance(状態, dict):
        失敗("現在状態はobjectでなければならない")
    if 状態.get("スキーマ版") != "arc2-current-state-ja-v2":
        失敗("現在状態のスキーマ版が未対応")
    if 状態.get("基底言語") != "日本語":
        失敗("基底言語不一致")
    for 項目 in ("状態", "現在作業", "学習機械正本"):
        値 = 状態.get(項目)
        if not isinstance(値, str) or not 値.strip():
            失敗(f"{項目}は空でない文字列が必要")
    if "戦略" not in 状態:
        失敗("戦略の選択状態が欠落")
    戦略 = 状態["戦略"]
    if 戦略 is not None and (not isinstance(戦略, str) or not 戦略.strip()):
        失敗("戦略はnullまたは空でない文字列が必要")
    if 状態.get("自動遷移") is not False:
        失敗("自動遷移は禁止")

    正本 = Path(状態["学習機械正本"])
    正本path = (ルート / 正本).resolve()
    if 正本.is_absolute() or 正本path == ルート or not 正本path.is_relative_to(ルート):
        失敗("学習機械正本はrepository内の相対pathが必要")
    if not 正本path.is_dir() or not (正本path / "README.md").is_file():
        失敗("選択された学習機械正本またはREADME.mdが存在しない")


def main():
    for p in 必須:
        if not (ルート / p).is_file():
            失敗("必須ファイル欠落: " + p)
    for p in 禁止:
        対象 = ルート / p
        # checkout後に残る空directoryには旧構成の実体がない。
        if 対象.is_file() or (対象.is_dir() and any(x.is_file() for x in 対象.rglob("*"))):
            失敗("除去済み構成が再出現: " + p)
    try:
        状態 = json.loads((ルート / "制御/現在状態.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as 例外:
        失敗(f"現在状態を読めない: {type(例外).__name__}")
    現在状態確認(状態)
    print(
        json.dumps(
            {
                "状態": "合格",
                "対象": "ARC2",
                "検証範囲": "repositoryの構造契約のみ。解答性能は未評価",
                "学習機械": 状態["学習機械正本"],
                "戦略": "未選択" if 状態["戦略"] is None else "選択済み",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
