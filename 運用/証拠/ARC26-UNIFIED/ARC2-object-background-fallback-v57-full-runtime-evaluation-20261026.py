"""Run the local v57 object-background fallback candidate on the full public ARC2 challenge and score offline."""
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
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v57-object-background-training-fallback-20261026"
PAIRED = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-object-background-fallback-v57-exact-paired-20261026.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score(predictions, targets):
    exact_examples = exact_tasks = 0
    for task_id, rows in predictions.items():
        correctness = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(rows, targets[task_id], strict=True)
        ]
        exact_examples += sum(correctness)
        exact_tasks += all(correctness)
    return {"exact_tasks": exact_tasks, "exact_examples": exact_examples}


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge_data = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="arc2-v57-full-") as temp_name:
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
            errors="replace",
            timeout=3600,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                "v57 object-background fallback full runtime failed with "
                f"exit {process.returncode}; stdout_tail={process.stdout[-2400:]!r}; "
                f"stderr_tail={process.stderr[-2400:]!r}"
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
    current_score = _score(predictions, targets)
    baseline_score = _score(baseline, targets)
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

    manifest = json.loads((BUILD / "build-manifest.json").read_text(encoding="utf-8"))
    paired = json.loads(PAIRED.read_text(encoding="utf-8"))
    parent_score = paired["challenge_candidate_tasks_exact_v28_bundle_paired"]
    parent_aggregate = {"exact_tasks": 14, "exact_examples": 15}
    report = {
        "schema": "arc2-object-background-fallback-v57-full-runtime-evaluation-v1",
        "challenge_tasks": len(challenge_data),
        "challenge_examples": sum(len(task["test"]) for task in challenge_data.values()),
        "runtime_task_count": audit.get("tasks"),
        "runtime_example_count": audit.get("test_examples"),
        "runtime_seconds": audit.get("seconds"),
        "fallback_count": audit.get("fallback_count"),
        "fallback_reason_counts": audit.get("solver_hold_reason_counts", {}),
        "v19_baseline": baseline_score,
        "v57_full_challenge_score": current_score,
        "delta_vs_v19": {
            "newly_correct_tasks": current_score["exact_tasks"] - baseline_score["exact_tasks"],
            "newly_correct_examples": gained_examples,
            "regressed_tasks": regressed_tasks,
            "regressed_examples": regressed_examples,
            "changed_attempt1_examples": changed_first,
            "changed_attempt2_examples": changed_second,
        },
        "delta_vs_v51_aggregate": {
            "exact_tasks": current_score["exact_tasks"] - parent_aggregate["exact_tasks"],
            "exact_examples": current_score["exact_examples"] - parent_aggregate["exact_examples"],
            "parent_v51_score": parent_aggregate,
            "parent_v51_output_sha256": "8c4a3d09d80e9cef5cf9f3873afa523d2700a52882a5b65ad041d39380327194",
            "paired_candidate_region_evidence": {
                "baseline_exact_examples": parent_score["baseline_exact_examples"],
                "combined_exact_examples": parent_score["combined_exact_examples"],
                "newly_correct_examples": parent_score["newly_correct_examples"],
                "regressed_examples": parent_score["regressed_examples"],
                "baseline_exact_tasks": parent_score["baseline_exact_tasks"],
                "combined_exact_tasks": parent_score["combined_exact_tasks"],
                "newly_correct_tasks": parent_score["newly_correct_tasks"],
                "regressed_tasks": parent_score["regressed_tasks"],
            },
        },
        "v57_submission_sha256": output_sha256,
        "temporary_audit_sha256": audit_sha256,
        "bundle_payload_sha256": manifest["payload_sha256"],
        "bundle_notebook_sha256": manifest["notebook_sha256"],
        "runtime_received_test_targets": False,
        "targets_read_after_full_runtime_completion": True,
        "temporary_predictions_targets_and_payload_removed": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "parent_v51_public_score": parent_aggregate,
        "parent_v28_output_sha256": "54f6a303c4143f15279e2084d5ad798455e565b4d51cd6a2b226e4d4735af46a",
        "parent_v51_payload_sha256": "bea77a938152d80e39beb0f43be219e649c31e01dfb7fe3f7dc6ed5e44b4bb23",
        "runtime_used_generic_prior_memory": True,
        "runtime_includes_v51_largest_component_primary": True,
        "runtime_includes_training_guided_fallback": True,
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE),
            "build_manifest": _sha(BUILD / "build-manifest.json"),
            "paired_v51_scorecard": _sha(PAIRED),
            "bundle_prior_memory": next(row["sha256"] for row in manifest["files"] if row["path"].endswith("/事前記憶訓練例.json")),
            "bundle_adapter": next(row["sha256"] for row in manifest["files"] if row["path"].endswith("/Kaggle提出.py")),
            "bundle_hds_bridge": next(row["sha256"] for row in manifest["files"] if row["path"].endswith("/HDS接続.py")),
            "bundle_object_extraction": next(row["sha256"] for row in manifest["files"] if row["path"] == "接続/ARC2/物体抽出候補.py"),
            "bundle_feature_neighbor": next(row["sha256"] for row in manifest["files"] if "近傍" in row["path"] and row["path"].endswith("変換選択.py")),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
