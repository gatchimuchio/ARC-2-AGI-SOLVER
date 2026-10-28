"""安全版二面候補stageから、診断書込みなしのprivate Kaggle Notebookを生成する。"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROZEN_BUILDER = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2_v61_deadline_review_bundle_build_20261027.py"
BUDGET_SECONDS = 37800


def 構築(stage: Path, output: Path):
    if output.exists():
        raise FileExistsError("既存のNotebook出力は上書きしません")
    stage = stage.resolve()
    manifest = json.loads((stage / "diagnostic-manifest.json").read_text(encoding="utf-8"))
    security = manifest.get("security", {})
    if security.get("teacher_test_removed") is not True or security.get("cache_member_revalidation") is not True:
        raise ValueError("安全化済みstageではありません")
    names = ("Kaggle提出.py", "deadline_control.py", "outer_watchdog.py", "solve.py")
    hashes = manifest["diagnostic_sha256"]
    members = {name: hashes[name] for name in names}
    members["two_panel.py"] = manifest["candidate_sha256"]
    spec = importlib.util.spec_from_file_location("arc2_frozen_deadline_builder", FROZEN_BUILDER)
    if spec is None or spec.loader is None:
        raise RuntimeError("固定Notebook builderを読み込めません")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    builder.SOURCE_ROOT = stage
    builder.BUILD_ROOT = output.resolve()
    builder.MEMBERS = members
    builder.KERNEL_ID = "tecchannn/arc2-v7-two-panel-hardened"
    builder.KERNEL_TITLE = "ARC2 v7 two panel hardened"
    original_source = builder.notebook_source

    def source_with_budget(bundle_b64, bundle_sha256):
        source = original_source(bundle_b64, bundle_sha256)
        old = '"--output-dir", "/kaggle/working"])'
        new = f'"--output-dir", "/kaggle/working", "--run-budget-seconds", "{BUDGET_SECONDS}"])'
        if source.count(old) != 1 or "--aggregate-diagnostics" in source:
            raise ValueError("Notebookの予算または診断条件が不正です")
        return source.replace(old, new)

    builder.notebook_source = source_with_budget
    with contextlib.redirect_stdout(io.StringIO()):
        builder.main()
    path = output / "build-manifest.json"
    built = json.loads(path.read_text(encoding="utf-8"))
    built.update({"instruction_version": "ARC2-v7.0", "run_budget_seconds": BUDGET_SECONDS,
                  "aggregate_diagnostics": False, "payload_security": security,
                  "acceptance": "LOCAL_AND_PRIVATE_RUNTIME_VERIFICATION_REQUIRED"})
    path.write_text(json.dumps(built, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return built


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(構築(args.stage, args.output), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
