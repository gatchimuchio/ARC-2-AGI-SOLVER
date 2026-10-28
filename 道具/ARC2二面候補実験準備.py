"""検証済みの凍結実行器へ二面候補を追加した実験stageを再現する。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from 道具.ARC2候補診断準備 import 作成 as 診断stage作成


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "接続/ARC2/二面真理値候補.py"
CANDIDATE_SHA = "819d9459ed6cb1a356532b98658e756038945b80d9996b6f7b51e881372a945f"


def 作成(destination: Path):
    source = CANDIDATE.read_bytes()
    if hashlib.sha256(source).hexdigest() != CANDIDATE_SHA:
        raise ValueError("評価済み候補のhashと一致しません")
    manifest = 診断stage作成(destination)
    adapter = destination / "Kaggle提出.py"
    text = adapter.read_text(encoding="utf-8")
    anchor = '        from 接続.ARC2.単純変換候補 import unique_candidate\n'
    if text.count(anchor) != 1:
        raise ValueError("候補import箇所が一意ではありません")
    text = text.replace(anchor, anchor + '        from two_panel import candidate as two_panel_candidate\n', 1)
    anchor = '            公開行群.append(\n'
    if text.count(anchor) != 1:
        raise ValueError("候補採用箇所が一意ではありません")
    insertion = (
        '            if 位置 < len(課題["test"]) and (not 格子か(第二候補) or 第二候補 == 第一候補):\n'
        '                二面候補 = two_panel_candidate(課題["train"], 課題["test"][位置]["input"])\n'
        '                if 格子か(二面候補) and 二面候補 != 第一候補:\n'
        '                    第二候補 = 二面候補\n'
    )
    text = text.replace(anchor, insertion + anchor, 1)
    compile(text, str(adapter), "exec")
    adapter.write_text(text, encoding="utf-8", newline="\n")
    with (destination / "two_panel.py").open("xb") as file:
        file.write(source)
    manifest["diagnostic_sha256"]["Kaggle提出.py"] = hashlib.sha256(adapter.read_bytes()).hexdigest()
    manifest["candidate_sha256"] = CANDIDATE_SHA
    manifest["integration"] = "Use only as a distinct second attempt when no valid distinct second candidate already exists; leave first attempt and HDS acceptance unchanged."
    (destination / "diagnostic-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(作成(args.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
