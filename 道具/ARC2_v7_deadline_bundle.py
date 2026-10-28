"""v61の固定済み実行資産から、v7の時間予算を指定したNotebookを生成する。"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2_v61_deadline_review_bundle_build_20261027.py"
BUDGET_SECONDS = 37800


def main() -> None:
    spec = importlib.util.spec_from_file_location("arc2_frozen_deadline_builder", BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("固定済みbuilderを読み込めません")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.BUILD_ROOT = ROOT / "出力/Kaggle/arc2-v7-deadline-105h-20261028-build"
    # Kaggleは初回作成時にtitle由来のスラッグを採用する。
    builder.KERNEL_ID = "tecchannn/arc2-v7-deadline-10h30m"
    builder.KERNEL_TITLE = "ARC2 v7 deadline 10h30m"
    original_source = builder.notebook_source

    def source_with_budget(bundle_b64: str, bundle_sha256: str) -> str:
        source = original_source(bundle_b64, bundle_sha256)
        old = '"--output-dir", "/kaggle/working"])'
        new = f'"--output-dir", "/kaggle/working", "--run-budget-seconds", "{BUDGET_SECONDS}"])'
        if source.count(old) != 1:
            raise ValueError("Notebookの予算指定箇所が一意ではありません")
        return source.replace(old, new)

    builder.notebook_source = source_with_budget
    with contextlib.redirect_stdout(io.StringIO()):
        builder.main()
    manifest_path = builder.BUILD_ROOT / "build-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_budget_seconds"] = BUDGET_SECONDS
    manifest["instruction_version"] = "ARC2-v7.0"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
