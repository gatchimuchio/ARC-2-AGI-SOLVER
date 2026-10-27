"""Run only v18 bundle tasks whose composite program can change attempt 2."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate  # noqa: E402
from 接続.ARC2.単純変換候補 import valid_grid  # noqa: E402


CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v18-composite-second-guess-20261026"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_correct(row: dict, target: list[list[int]]) -> bool:
    return any(row.get(name) == target for name in ("attempt_1", "attempt_2"))


def row_nonidentity_correct(row: dict, target: list[list[int]], input_grid: list[list[int]]) -> bool:
    return target != input_grid and row_correct(row, target)


def run_versioned_worker(task: dict, launcher: Path) -> tuple[dict | None, float]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(launcher), "--worker"],
        input=json.dumps(task, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=300,
        env=env,
        check=False,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode or not lines:
        return None, time.monotonic() - started
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError:
        return None, time.monotonic() - started
    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != len(task["test"]):
        return None, time.monotonic() - started
    return payload, time.monotonic() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    base_path = BASELINE / "submission.json"
    baseline = json.loads(base_path.read_text(encoding="utf-8"))
    launcher = BUILD / "solve.py"
    manifest_path = BUILD / "build-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    affected = []
    candidate_predictions = candidate_distinct = 0
    for task_id, task in challenge.items():
        model = CompositeGeometryCandidate(task["train"])
        affected_examples = []
        for index, pair in enumerate(task["test"]):
            candidate, _ = model.候補(pair["input"], {})
            candidate_predictions += candidate is not None
            if (
                valid_grid(candidate)
                and candidate != baseline[task_id][index]["attempt_1"]
            ):
                candidate_distinct += 1
                affected_examples.append(index)
        if affected_examples:
            affected.append((task_id, task, affected_examples))

    # All candidate detection above uses training examples and test inputs only.
    # Run the exact versioned bundle worker for every task the new family can change.
    updated = json.loads(json.dumps(baseline))
    worker_errors = 0
    worker_seconds = 0.0
    changed_attempt_1 = changed_attempt_2 = 0
    for task_id, task, _affected_examples in affected:
        payload, elapsed = run_versioned_worker(task, launcher)
        worker_seconds += elapsed
        if payload is None:
            worker_errors += 1
            continue
        rows = payload["results"]
        for index, pair in enumerate(task["test"]):
            row = rows[index] if isinstance(rows[index], dict) else {}
            first = row.get("answer")
            if not valid_grid(first):
                first = pair["input"]
            second = row.get("second_answer")
            if not valid_grid(second) or second == first:
                second = first
            changed_attempt_1 += baseline[task_id][index]["attempt_1"] != first
            changed_attempt_2 += baseline[task_id][index]["attempt_2"] != second
            updated[task_id][index] = {"attempt_1": first, "attempt_2": second}

    # Load public held-out targets only after all versioned worker predictions exist.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    base_grid_tasks = base_grid_examples = current_grid_tasks = current_grid_examples = 0
    base_nonidentity_tasks = base_nonidentity_examples = 0
    current_nonidentity_tasks = current_nonidentity_examples = 0
    distinct_before = distinct_after = new_tasks = regressed_tasks = 0
    new_examples = regressed_examples = 0
    for task_id, task in challenge.items():
        base_rows, current_rows = [], []
        for index, pair in enumerate(task["test"]):
            target, input_grid = labels[task_id][index], pair["input"]
            before = row_correct(baseline[task_id][index], target)
            after = row_correct(updated[task_id][index], target)
            before_nonidentity = row_nonidentity_correct(baseline[task_id][index], target, input_grid)
            after_nonidentity = row_nonidentity_correct(updated[task_id][index], target, input_grid)
            base_rows.append(before)
            current_rows.append(after)
            base_grid_examples += before
            current_grid_examples += after
            base_nonidentity_examples += before_nonidentity
            current_nonidentity_examples += after_nonidentity
            distinct_before += baseline[task_id][index]["attempt_1"] != baseline[task_id][index]["attempt_2"]
            distinct_after += updated[task_id][index]["attempt_1"] != updated[task_id][index]["attempt_2"]
            new_examples += after and not before
            regressed_examples += before and not after
        base_task, current_task = all(base_rows), all(current_rows)
        base_grid_tasks += base_task
        current_grid_tasks += current_task
        base_nonidentity_tasks += all(
            row_nonidentity_correct(baseline[task_id][index], labels[task_id][index], pair["input"])
            for index, pair in enumerate(task["test"])
        )
        current_nonidentity_tasks += all(
            row_nonidentity_correct(updated[task_id][index], labels[task_id][index], pair["input"])
            for index, pair in enumerate(task["test"])
        )
        new_tasks += current_task and not base_task
        regressed_tasks += base_task and not current_task

    file_manifest = {row["path"]: row for row in manifest["files"]}
    composite_row = file_manifest.get("接続/ARC2/複合幾何変換候補.py", {})
    adapter_row = file_manifest.get("接続/ARC2/Kaggle提出.py", {})
    hds_row = file_manifest.get("接続/ARC2/HDS接続.py", {})
    payload_sha = manifest.get("payload_sha256")
    report = {
        "schema": "arc2-v18-composite-attempt2-impact-scorecard-v1",
        "tasks": len(challenge),
        "test_examples": sum(len(task["test"]) for task in challenge.values()),
        "versioned_worker_calls": len(affected),
        "versioned_worker_errors": worker_errors,
        "versioned_worker_elapsed_seconds": round(worker_seconds, 3),
        "candidate_predictions": candidate_predictions,
        "candidate_distinct_from_existing_primary": candidate_distinct,
        "labels_source": "public ARC-AGI-2 training outputs; offline scoring only",
        "runtime_received_targets": False,
        "targets_read_only_after_all_versioned_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "baseline_submission_sha256": sha(base_path),
        "candidate_composition_sha256": hashlib.sha256(
            json.dumps(updated, ensure_ascii=False, indent=2).encode("utf-8")
        ).hexdigest(),
        "challenge_sha256": sha(CHALLENGE),
        "v18_payload_sha256": payload_sha,
        "v18_adapter_sha256": adapter_row.get("sha256"),
        "v18_composite_module_sha256": composite_row.get("sha256"),
        "v18_hds_connector_sha256": hds_row.get("sha256"),
        "baseline_exact_grid_tasks": base_grid_tasks,
        "baseline_exact_grid_examples": base_grid_examples,
        "candidate_exact_grid_tasks": current_grid_tasks,
        "candidate_exact_grid_examples": current_grid_examples,
        "delta_exact_grid_tasks": current_grid_tasks - base_grid_tasks,
        "delta_exact_grid_examples": current_grid_examples - base_grid_examples,
        "newly_correct_grid_tasks": new_tasks,
        "regressed_grid_tasks": regressed_tasks,
        "newly_correct_grid_examples": new_examples,
        "regressed_grid_examples": regressed_examples,
        "changed_attempt_1_examples": changed_attempt_1,
        "changed_attempt_2_examples": changed_attempt_2,
        "distinct_attempt_pairs_before": distinct_before,
        "distinct_attempt_pairs_after": distinct_after,
        "baseline_nonidentity_correct_tasks": base_nonidentity_tasks,
        "candidate_nonidentity_correct_tasks": current_nonidentity_tasks,
        "baseline_nonidentity_correct_examples": base_nonidentity_examples,
        "candidate_nonidentity_correct_examples": current_nonidentity_examples,
        "official_competition_score": "UNKNOWN_NOT_SUBMITTED",
        "interpretation": "Matched composition of the complete v16 runtime output and the v18 versioned worker for every task where this family can change the second attempt; not a full v18 240-task runtime.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "versioned_worker_calls", "versioned_worker_errors", "candidate_predictions",
        "candidate_distinct_from_existing_primary", "baseline_exact_grid_tasks",
        "candidate_exact_grid_tasks", "delta_exact_grid_tasks", "delta_exact_grid_examples",
        "newly_correct_grid_tasks", "regressed_grid_tasks", "changed_attempt_1_examples",
        "changed_attempt_2_examples", "distinct_attempt_pairs_before", "distinct_attempt_pairs_after"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
