"""Kaggleの公開入力・実行環境・出力回収を確認する。大会解答は生成しない。"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path


配布ファイル = (
    "arc-agi_training_challenges.json",
    "arc-agi_training_solutions.json",
    "arc-agi_evaluation_challenges.json",
    "arc-agi_evaluation_solutions.json",
    "arc-agi_test_challenges.json",
    "sample_submission.json",
)


def main() -> None:
    引数器 = argparse.ArgumentParser(description=__doc__)
    引数器.add_argument("--input-dir", type=Path)
    引数器.add_argument("--output-dir", type=Path, default=Path("/kaggle/working"))
    引数 = 引数器.parse_args()
    入力先 = 引数.input_dir
    if 入力先 is None:
        # Kaggleの新旧mount構成を外部境界で解決し、複数候補なら曖昧な採用をしない。
        候補 = list(Path("/kaggle/input").rglob("arc-agi_test_challenges.json"))
        if len(候補) != 1:
            raise RuntimeError(f"大会入力を一意に特定できない: 候補数={len(候補)}")
        入力先 = 候補[0].parent

    ファイル検査 = {}
    for 名前 in 配布ファイル:
        内容 = (入力先 / 名前).read_bytes()
        データ = json.loads(内容)
        if not isinstance(データ, dict) or not データ:
            raise ValueError(f"空または不正な大会JSON: {名前}")
        ファイル検査[名前] = {
            "record数": len(データ),
            "サイズbyte": len(内容),
            "SHA256": hashlib.sha256(内容).hexdigest(),
        }

    依存版 = {}
    for 名前 in ("numpy", "torch", "pandas", "transformers"):
        try:
            依存版[名前] = importlib.metadata.version(名前)
        except importlib.metadata.PackageNotFoundError:
            依存版[名前] = "未導入"
    報告 = {
        "確認形式": "arc2-connection-check-v2",
        "状態": "合格",
        "対象": "Kaggle接続・公開配布データ・出力回収",
        "Python": platform.python_version(),
        "OS": platform.system(),
        "依存版": 依存版,
        "ファイル検査": ファイル検査,
        "大会提出": "未実施。submission.jsonは生成しない",
    }
    引数.output_dir.mkdir(parents=True, exist_ok=True)
    (引数.output_dir / "接続確認.json").write_text(
        json.dumps(報告, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(報告, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
