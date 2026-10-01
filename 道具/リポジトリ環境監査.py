#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ルート = Path(__file__).resolve().parents[1]
必須 = (
    "README.md","AGENTS.md","制御/現在状態.json","運用/権限順序.md",
    "HDS/学習系統/v0.4.2/README.md","入力/公式サンプル/マニフェスト.json",
    "戦略/README.md","検証/README.md",
)
禁止 = ("ミニドラ","設計/AGI三主体構成.md","設計/共通知能基盤")

def 失敗(msg):
    raise SystemExit("リポジトリ環境監査失敗: " + msg)

def main():
    for p in 必須:
        if not (ルート/p).is_file(): 失敗("必須ファイル欠落: "+p)
    for p in 禁止:
        if (ルート/p).exists(): 失敗("除去済み構成が再出現: "+p)
    状態=json.loads((ルート/"制御/現在状態.json").read_text(encoding="utf-8"))
    if 状態.get("基底言語")!="日本語": 失敗("基底言語不一致")
    if 状態.get("戦略") is not None: 失敗("戦略未選択契約に反する")
    if 状態.get("自動遷移") is not False: 失敗("自動遷移は禁止")
    if 状態.get("学習機械正本")!="HDS/学習系統/v0.4.2": 失敗("学習機械正本不一致")
    print(json.dumps({"状態":"合格","対象":"ARC2","学習機械":"HDS/学習系統/v0.4.2"},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
