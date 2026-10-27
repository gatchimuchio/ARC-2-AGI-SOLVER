"""Compare v21 and v20 bundles on the public challenge's affected tasks."""
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
BASELINE_V19 = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
V20_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v20-object-extraction-second-20261026"
V21_BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v21-object-outlier-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _select_affected(challenge, baseline):
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate

    v20_tasks = {}
    v21_tasks = {}
    old_candidates = old_selected = new_candidates = new_selected = 0
    for task_id, task in sorted(challenge.items()):
        model = ObjectExtractionCandidate(task["train"])
        should_run_v20 = should_run_v21 = False
        rows = baseline[task_id]
        for index, pair in enumerate(task["test"]):
            first = rows[index]["attempt_1"]
            second = rows[index]["attempt_2"]
            old_candidate, _ = model.candidate(pair["input"])
            if old_candidate is not None and old_candidate != first:
                old_candidates += 1
                if second == first:
                    second = old_candidate
                    old_selected += 1
                    should_run_v20 = True
                    should_run_v21 = True
            if second == first:
                new_candidate, _ = model.outlier_candidate(pair["input"])
                if new_candidate is not None and new_candidate != first:
                    new_candidates += 1
                    new_selected += 1
                    should_run_v21 = True
        input_only = {
            "train": task["train"],
            "test": [{"input": pair["input"]} for pair in task["test"]],
        }
        if should_run_v20:
            v20_tasks[task_id] = input_only
        if should_run_v21:
            v21_tasks[task_id] = input_only
    return v20_tasks, v21_tasks, {
        "v20_distinct_candidates": old_candidates,
        "v20_duplicate_slots_selected": old_selected,
        "v21_distinct_candidates_after_v20": new_candidates,
        "v21_duplicate_slots_selected": new_selected,
    }


def _run_bundle(build: Path, tasks: dict, prefix: str):
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_name:
        temp = Path(temp_name)
        subset_path = temp / "challenges.json"
        output_dir = temp / "output"
        payload_root = temp / "payload"
        subset_path.write_text(
            json.dumps(tasks, ensure_ascii=False), encoding="utf-8"
        )
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(payload_root),
        }
        process = subprocess.run(
            [
                sys.executable,
                str(build / "solve.py"),
                "--challenges",
                str(subset_path),
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(
                f"{build.name} failed with exit {process.returncode}"
            )
        predictions = json.loads(
            (output_dir / "submission.json").read_text(encoding="utf-8")
        )
        audit = json.loads(
            (output_dir / "submission_audit.json").read_text(encoding="utf-8")
        )
        return predictions, audit


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
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline_v19 = json.loads(BASELINE_V19.read_text(encoding="utf-8"))
    v20_tasks, v21_tasks, selection = _select_affected(challenge, baseline_v19)
    v20_subset, v20_audit = _run_bundle(V20_BUILD, v20_tasks, "arc2-v20-matched-")
    v21_subset, v21_audit = _run_bundle(V21_BUILD, v21_tasks, "arc2-v21-matched-")

    # Public targets are loaded only after both bundle runs have finished.
    targets = {
        path.stem: [
            pair["output"]
            for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])
        ]
        for path in SOURCE_ROOT.glob("*.json")
    }
    current_v20 = {task_id: rows for task_id, rows in baseline_v19.items()}
    current_v21 = {task_id: rows for task_id, rows in baseline_v19.items()}
    current_v20.update(v20_subset)
    current_v21.update(v21_subset)
    v20_score = _score(current_v20, targets)
    v21_score = _score(current_v21, targets)

    gains = regressions = changed_attempt2 = 0
    for task_id, rows in current_v21.items():
        for index, row in enumerate(rows):
            old = current_v20[task_id][index]
            target = targets[task_id][index]
            before = old["attempt_1"] == target or old["attempt_2"] == target
            after = row["attempt_1"] == target or row["attempt_2"] == target
            gains += after and not before
            regressions += before and not after
            changed_attempt2 += row["attempt_2"] != old["attempt_2"]

    v20_manifest = json.loads(
        (V20_BUILD / "build-manifest.json").read_text(encoding="utf-8")
    )
    v21_manifest = json.loads(
        (V21_BUILD / "build-manifest.json").read_text(encoding="utf-8")
    )
    report = {
        "schema": "arc2-object-outlier-v21-bundle-matched-challenge-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "v20_tasks_run_from_bundle": len(v20_tasks),
        "v21_union_tasks_run_from_bundle": len(v21_tasks),
        "candidate_selection": selection,
        "v20_bundle_fallbacks": v20_audit.get("fallback_count"),
        "v21_bundle_fallbacks": v21_audit.get("fallback_count"),
        "v20_bundle_matched_composition": v20_score,
        "v21_bundle_matched_composition": v21_score,
        "delta_v21_vs_v20": {
            "newly_correct_tasks": v21_score["exact_tasks"] - v20_score["exact_tasks"],
            "newly_correct_examples": gains,
            "regressed_examples": regressions,
            "changed_attempt2_examples": changed_attempt2,
        },
        "v20_payload_sha256": v20_manifest["payload_sha256"],
        "v21_payload_sha256": v21_manifest["payload_sha256"],
        "v21_notebook_sha256": v21_manifest["notebook_sha256"],
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_both_bundle_outputs": True,
        "temporary_subset_inputs_outputs_and_payloads_removed": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE_V19),
            "v20_build_manifest": _sha(V20_BUILD / "build-manifest.json"),
            "v21_build_manifest": _sha(V21_BUILD / "build-manifest.json"),
            "adapter": _sha(ROOT / "接続/ARC2/Kaggle提出.py"),
            "object_extraction_module": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        },
    }
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
