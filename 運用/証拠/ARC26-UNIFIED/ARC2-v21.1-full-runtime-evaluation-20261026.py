"""Run the complete v21.1 bundle on the public ARC2 challenge and score offline."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v21.1-object-outlier-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score(predictions, targets):
    exact_examples = exact_tasks = 0
    correctness_by_task = {}
    for task_id, rows in predictions.items():
        correctness = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(rows, targets[task_id], strict=True)
        ]
        exact_examples += sum(correctness)
        exact_tasks += all(correctness)
        correctness_by_task[task_id] = correctness
    return (
        {"exact_tasks": exact_tasks, "exact_examples": exact_examples},
        correctness_by_task,
    )


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge_data = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="arc2-v21.1-full-") as temp_name:
        temp = Path(temp_name)
        output_dir = temp / "output"
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(temp / "payload"),
        }
        process = subprocess.run(
            [
                sys.executable,
                str(BUILD / "solve.py"),
                "--challenges",
                str(CHALLENGE),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=3600,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"v21.1 full runtime failed with exit {process.returncode}"
            )
        output_path = output_dir / "submission.json"
        audit_path = output_dir / "submission_audit.json"
        predictions = json.loads(output_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        output_sha256 = _sha(output_path)
        audit_sha256 = _sha(audit_path)

    # Read held-out public labels only after the exact full-bundle output exists.
    targets = {
        path.stem: [
            pair["output"]
            for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])
        ]
        for path in SOURCE_ROOT.glob("*.json")
    }
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    current_score, current_correct = _score(predictions, targets)
    baseline_score, baseline_correct = _score(baseline, targets)

    gained_examples = regressed_examples = changed_first = changed_second = 0
    gained_tasks = regressed_tasks = 0
    for task_id, rows in predictions.items():
        gained_task = regressed_task = False
        for index, row in enumerate(rows):
            old = baseline[task_id][index]
            target = targets[task_id][index]
            before = old["attempt_1"] == target or old["attempt_2"] == target
            after = row["attempt_1"] == target or row["attempt_2"] == target
            gained_examples += after and not before
            regressed_examples += before and not after
            gained_task |= after and not before
            regressed_task |= before and not after
            changed_first += row["attempt_1"] != old["attempt_1"]
            changed_second += row["attempt_2"] != old["attempt_2"]
        gained_tasks += gained_task
        regressed_tasks += regressed_task

    manifest = json.loads(
        (BUILD / "build-manifest.json").read_text(encoding="utf-8")
    )
    report = {
        "schema": "arc2-v21.1-full-runtime-evaluation-v1",
        "challenge_tasks": len(challenge_data),
        "challenge_examples": sum(len(task["test"]) for task in challenge_data.values()),
        "runtime_task_count": audit.get("tasks"),
        "runtime_example_count": audit.get("test_examples"),
        "runtime_seconds": audit.get("seconds"),
        "fallback_count": audit.get("fallback_count"),
        "fallback_reason_counts": audit.get("solver_hold_reason_counts", {}),
        "v19_baseline": baseline_score,
        "v21.1_full_runtime": current_score,
        "delta": {
            "newly_correct_tasks": current_score["exact_tasks"] - baseline_score["exact_tasks"],
            "newly_correct_examples": gained_examples,
            "regressed_tasks": regressed_tasks,
            "regressed_examples": regressed_examples,
            "changed_attempt1_examples": changed_first,
            "changed_attempt2_examples": changed_second,
        },
        "v21.1_submission_sha256": output_sha256,
        "temporary_audit_sha256": audit_sha256,
        "bundle_payload_sha256": manifest["payload_sha256"],
        "bundle_notebook_sha256": manifest["notebook_sha256"],
        "runtime_received_test_targets": False,
        "targets_read_after_full_runtime_completion": True,
        "temporary_predictions_targets_and_payload_removed": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE),
            "build_manifest": _sha(BUILD / "build-manifest.json"),
            "adapter": _sha(ROOT / "接続/ARC2/Kaggle提出.py"),
            "object_candidate": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
