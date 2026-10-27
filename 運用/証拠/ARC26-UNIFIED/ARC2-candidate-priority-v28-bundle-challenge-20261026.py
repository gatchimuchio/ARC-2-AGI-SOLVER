"""Compare exact v25/v28 bundles only on public tasks with competing object candidates."""
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
V21_FULL_REPORT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v21.1-full-runtime-evaluation-20261026.json"
V25_CHALLENGE_REPORT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-object-composite-palette-v25-bundle-challenge-20261026.json"
V25_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v25-composite-palette-second-20261026"
V28_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_bundle(build: Path, tasks: dict, prefix: str):
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        challenge_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        process = subprocess.run(
            [
                sys.executable,
                str(build / "solve.py"),
                "--challenges",
                str(challenge_path),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONUTF8": "1", "ARC2_PAYLOAD_ROOT": str(temp / "payload")},
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            check=False,
        )
        if process.returncode:
            raise RuntimeError(f"{build.name} failed: {process.returncode}")
        predictions = json.loads((output_dir / "submission.json").read_text(encoding="utf-8"))
        audit = json.loads((output_dir / "submission_audit.json").read_text(encoding="utf-8"))
    return predictions, audit


def _score(predictions: dict, targets: dict) -> dict[str, int]:
    exact_examples = exact_tasks = 0
    for task_id, rows in predictions.items():
        correct = [
            row["attempt_1"] == target or row["attempt_2"] == target
            for row, target in zip(rows, targets[task_id], strict=True)
        ]
        exact_examples += sum(correct)
        exact_tasks += all(correct)
    return {"exact_tasks": exact_tasks, "exact_examples": exact_examples}


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    selected: dict[str, dict] = {}
    competing_examples = 0
    for task_id, task in sorted(challenge.items()):
        model = ObjectExtractionCandidate(task["train"])
        relevant = False
        for pair in task["test"]:
            test_input = pair["input"]
            candidates = [
                model.candidate(test_input)[0],
                model.outlier_candidate(test_input)[0],
                model.palette_candidate(test_input)[0],
            ]
            distinct = {
                tuple(tuple(row) for row in candidate)
                for candidate in candidates
                if isinstance(candidate, list) and candidate
            }
            if len(distinct) > 1:
                competing_examples += 1
                relevant = True
        if relevant:
            selected[task_id] = {
                "train": task["train"],
                "test": [{"input": pair["input"]} for pair in task["test"]],
            }

    if selected:
        v25, v25_audit = _run_bundle(V25_BUILD, selected, "arc2-v25-v28-challenge-")
        v28, v28_audit = _run_bundle(V28_BUILD, selected, "arc2-v28-challenge-")
    else:
        v25 = v28 = {}
        v25_audit = v28_audit = {"fallback_count": 0}

    # Read public targets only after both exact bundle outputs are materialized.
    targets = {
        path.stem: [
            pair["output"]
            for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])
        ]
        for path in SOURCE_ROOT.glob("*.json")
    }
    v25_targets = {task_id: targets[task_id] for task_id in v25}
    v28_targets = {task_id: targets[task_id] for task_id in v28}
    v25_score = _score(v25, v25_targets)
    v28_score = _score(v28, v28_targets)
    changed_examples = changed_attempt2 = 0
    for task_id, rows in v28.items():
        for index, row in enumerate(rows):
            before = v25[task_id][index]
            changed_examples += row != before
            changed_attempt2 += row["attempt_2"] != before["attempt_2"]

    projected_v25 = json.loads(V25_CHALLENGE_REPORT.read_text(encoding="utf-8"))[
        "projected_full_challenge_v25"
    ]
    delta = {
        "exact_tasks": v28_score["exact_tasks"] - v25_score["exact_tasks"],
        "exact_examples": v28_score["exact_examples"] - v25_score["exact_examples"],
    }
    report = {
        "schema": "arc2-candidate-priority-v28-bundle-challenge-v1",
        "public_challenge_tasks": len(challenge),
        "public_challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "examples_with_multiple_distinct_object_candidates": competing_examples,
        "tasks_run_from_both_exact_bundles": len(selected),
        "examples_run_from_both_exact_bundles": sum(
            len(task["test"]) for task in selected.values()
        ),
        "v25_subset_score": v25_score,
        "v28_subset_score": v28_score,
        "changed_examples": changed_examples,
        "changed_attempt2_examples": changed_attempt2,
        "v25_bundle_fallbacks": v25_audit.get("fallback_count"),
        "v28_bundle_fallbacks": v28_audit.get("fallback_count"),
        "projected_full_challenge_v25": projected_v25,
        "projected_full_challenge_v28": {
            "exact_tasks": projected_v25["exact_tasks"] + delta["exact_tasks"],
            "exact_examples": projected_v25["exact_examples"] + delta["exact_examples"],
        },
        "projected_delta": delta,
        "runtime_received_test_targets": False,
        "targets_read_after_both_exact_bundle_outputs": True,
        "temporary_subset_outputs_and_payloads_removed": True,
        "task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "v21.1_full_report": _sha(V21_FULL_REPORT),
            "v25_challenge_report": _sha(V25_CHALLENGE_REPORT),
            "v25_build_manifest": _sha(V25_BUILD / "build-manifest.json"),
            "v28_build_manifest": _sha(V28_BUILD / "build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
