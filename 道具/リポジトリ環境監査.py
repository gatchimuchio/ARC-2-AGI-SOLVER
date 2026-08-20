#!/usr/bin/env python3
"""日本語基底ARC2 repositoryの最小環境契約を検証する。"""

from __future__ import annotations

import json
from pathlib import Path


ルート = Path(__file__).resolve().parents[1]

必須ファイル = (
    "README.md",
    "AGENTS.md",
    "制御/現在状態.json",
    "運用/権限順序.md",
    "運用/日本語基底方針.md",
    "運用/リポジトリ運用モデル.md",
    "設計/AGI三主体構成.md",
    "HDS/README.md",
    "ミニドラ/README.md",
    "記憶/README.md",
    "入力/README.md",
    "入力/公式サンプル/README.md",
    "入力/公式サンプル/マニフェスト.json",
    "接続/README.md",
    "戦略/README.md",
    "検証/README.md",
)

旧正本禁止path = (
    "control/CURRENT_SELECTOR.json",
    "AUTHORITY_ORDER.md",
    "docs/operations/REPOSITORY_OPERATING_MODEL.md",
    "scripts/check_repository_environment.py",
    "scripts/sync_official_sample.py",
    "data/official_sample/MANIFEST.json",
)


def 失敗(理由: str) -> None:
    raise SystemExit(f"リポジトリ環境監査失敗: {理由}")


def main() -> None:
    for 相対path in 必須ファイル:
        if not (ルート / 相対path).is_file():
            失敗(f"必須ファイル欠落: {相対path}")

    for 相対path in 旧正本禁止path:
        if (ルート / 相対path).exists():
            失敗(f"旧英語基底pathが現行木へ残存: {相対path}")

    状態path = ルート / "制御/現在状態.json"
    try:
        状態 = json.loads(状態path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as 例外:
        失敗(f"現在状態を読めない: {例外}")

    if 状態.get("基底言語") != "日本語":
        失敗("基底言語が日本語ではない")
    if 状態.get("状態") != "再設計中":
        失敗("現在状態が再設計中ではない")
    if 状態.get("戦略") is not None:
        失敗("戦略未選択契約に反する")
    if 状態.get("自動遷移") is not False:
        失敗("自動遷移は禁止")

    期待構成 = {
        "入力判断主体": "HDS",
        "LLM主体": "ミニドラ",
        "記憶主体": "記憶",
        "HDSコンパイラ管轄": "HDS",
    }
    if 状態.get("AGI構成") != 期待構成:
        失敗("AGI三主体構成が固定契約と不一致")

    manifest = json.loads(
        (ルート / "入力/公式サンプル/マニフェスト.json").read_text(encoding="utf-8")
    )
    if manifest.get("アップロードZIP", {}).get("ファイル数") != 6:
        失敗("ARC2公式サンプルmanifestのファイル数が不正")
    if manifest.get("公式ソース", {}).get("commit") != "f3283f727488ad98fe575ea6a5ac981e4a188e49":
        失敗("ARC2公式source固定commitが不一致")

    print(
        json.dumps(
            {
                "状態": "合格",
                "対象": "ARC2",
                "基底言語": "日本語",
                "戦略": None,
                "AGI構成": "HDS + ミニドラ + 記憶",
                "公式サンプル": "固定済み",
                "必須ファイル数": len(必須ファイル),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
