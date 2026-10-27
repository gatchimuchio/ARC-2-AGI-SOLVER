"""Run only impacted public challenge tasks from the exact v20 Kaggle bundle."""
from __future__ import annotations

import hashlib
import importlib.util
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
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v20-object-extraction-second-20261026"
OUTPUT = Path(__file__).with_suffix(".json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_affected(challenge, baseline):
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.物体抽出候補 import ObjectExtractionCandidate

    selected = {}
    candidate_examples = selected_examples = 0
    for task_id, task in sorted(challenge.items()):
        model = ObjectExtractionCandidate(task["train"])
        base_rows = baseline[task_id]
        should_run = False
        for index, pair in enumerate(task["test"]):
            candidate, _record = model.candidate(pair["input"])
            base = base_rows[index]
            if candidate is None or candidate == base["attempt_1"]:
                continue
            candidate_examples += 1
            if candidate == base["attempt_2"]:
                continue
            if base["attempt_1"] == base["attempt_2"]:
                selected_examples += 1
                should_run = True
        if should_run:
            selected[task_id] = {
                "train": task["train"],
                "test": [{"input": pair["input"]} for pair in task["test"]],
            }
    return selected, candidate_examples, selected_examples


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    selected, candidate_examples, selected_examples = select_affected(challenge, baseline)

    with tempfile.TemporaryDirectory(prefix="arc2-v20-matched-") as temp_name:
        temp = Path(temp_name)
        subset_path = temp / "challenges.json"
        output_dir = temp / "output"
        subset_path.write_text(json.dumps(selected, ensure_ascii=False), encoding="utf-8")
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(BUILD / "runtime-payload"),
        }
        process = subprocess.run(
            [
                sys.executable,
                str(BUILD / "solve.py"),
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
            raise RuntimeError(f"v20 bundle worker failed: exit={process.returncode}")
        result_path = output_dir / "submission.json"
        current_subset = json.loads(result_path.read_text(encoding="utf-8"))

    # Official public labels are read only after exact bundle outputs are complete.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    current = {task_id: rows for task_id, rows in baseline.items()}
    for task_id, rows in current_subset.items():
        current[task_id] = rows

    def score(predictions):
        exact_examples = exact_tasks = 0
        for task_id, rows in predictions.items():
            correctness = [
                row["attempt_1"] == target or row["attempt_2"] == target
                for row, target in zip(rows, targets[task_id], strict=True)
            ]
            exact_examples += sum(correctness)
            exact_tasks += all(correctness)
        return {"exact_tasks": exact_tasks, "exact_examples": exact_examples}

    base_score = score(baseline)
    current_score = score(current)
    gains = regressions = changed_second = 0
    for task_id, rows in current.items():
        for index, row in enumerate(rows):
            old = baseline[task_id][index]
            target = targets[task_id][index]
            before = old["attempt_1"] == target or old["attempt_2"] == target
            after = row["attempt_1"] == target or row["attempt_2"] == target
            gains += after and not before
            regressions += before and not after
            changed_second += row["attempt_2"] != old["attempt_2"]
    build = json.loads((BUILD / "build-manifest.json").read_text(encoding="utf-8"))
    report = {
        "schema": "arc2-object-extraction-v20-bundle-matched-challenge-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task["test"]) for task in challenge.values()),
        "selected_tasks_run_from_bundle": len(selected),
        "candidate_examples_distinct_from_attempt1": candidate_examples,
        "selected_duplicate_second_slots": selected_examples,
        "worker_errors": 0,
        "baseline_v19": base_score,
        "v20_bundle_matched_composition": current_score,
        "delta": {
            "newly_correct_tasks": current_score["exact_tasks"] - base_score["exact_tasks"],
            "newly_correct_examples": gains,
            "regressed_examples": regressions,
            "changed_attempt2_examples": changed_second,
        },
        "bundle_payload_sha256": build["payload_sha256"],
        "bundle_notebook_sha256": build["notebook_sha256"],
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_bundle_outputs": True,
        "temporary_subset_inputs_and_outputs_removed": True,
        "per_task_predictions_or_targets_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "challenge": sha(CHALLENGE),
            "baseline_v19": sha(BASELINE),
            "build_manifest": sha(BUILD / "build-manifest.json"),
            "adapter": sha(ROOT / "接続/ARC2/Kaggle提出.py"),
            "object_extraction_module": sha(ROOT / "接続/ARC2/物体抽出候補.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
