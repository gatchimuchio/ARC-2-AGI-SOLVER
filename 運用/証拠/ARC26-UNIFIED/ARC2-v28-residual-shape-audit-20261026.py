"""Run exact v28 on the public challenge and retain only aggregate residual-shape metrics."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BUILD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026"
BASELINE_REPORT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v28-full-runtime-evaluation-20261026.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shape(grid):
    if not isinstance(grid, list) or not grid:
        return None
    if not isinstance(grid[0], list) or not grid[0]:
        return None
    if any(not isinstance(row, list) or len(row) != len(grid[0]) for row in grid):
        return None
    return len(grid), len(grid[0])


def _relation(input_shape, target_shape):
    if input_shape is None or target_shape is None:
        return "invalid"
    if input_shape == target_shape:
        return "same"
    if input_shape == (target_shape[1], target_shape[0]):
        return "transpose"
    input_area = input_shape[0] * input_shape[1]
    target_area = target_shape[0] * target_shape[1]
    if target_area < input_area:
        return "shrink_area"
    if target_area > input_area:
        return "expand_area"
    return "same_area_reframe"


def _pixel_accuracy(prediction, target):
    if _shape(prediction) != _shape(target):
        return None
    total = sum(len(row) for row in target)
    matches = sum(
        left == right
        for left_row, right_row in zip(prediction, target, strict=True)
        for left, right in zip(left_row, right_row, strict=True)
    )
    return matches / total if total else None


def _pixel_bin(value):
    if value is None:
        return "shape_mismatch"
    if value == 1.0:
        return "1.0"
    if value < 0.25:
        return "0-0.25"
    if value < 0.50:
        return "0.25-0.50"
    if value < 0.75:
        return "0.50-0.75"
    return "0.75-1.0"


def _run_exact_bundle(tasks: dict):
    with tempfile.TemporaryDirectory(prefix="arc2-v28-residual-audit-") as temp_name:
        temp = Path(temp_name)
        challenge_path = temp / "challenges.json"
        output_dir = temp / "output"
        stdout_path = temp / "solver.stdout.log"
        stderr_path = temp / "solver.stderr.log"
        challenge_path.write_text(json.dumps(tasks, ensure_ascii=False), encoding="utf-8")
        environment = {
            **os.environ,
            "PYTHONUTF8": "1",
            "ARC2_PAYLOAD_ROOT": str(temp / "payload"),
        }
        started = time.perf_counter()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(BUILD / "solve.py"),
                    "--challenges",
                    str(challenge_path),
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                env=environment,
                stdout=stdout,
                stderr=stderr,
            )
            last_report = 0
            while process.poll() is None:
                elapsed = int(time.perf_counter() - started)
                if elapsed - last_report >= 60:
                    print(json.dumps({"exact_v28_runtime_seconds": elapsed}), flush=True)
                    last_report = elapsed
                time.sleep(5)
        runtime = time.perf_counter() - started
        if process.returncode:
            detail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
            raise RuntimeError(f"exact v28 bundle failed ({process.returncode}): {detail}")
        submission_path = output_dir / "submission.json"
        audit_path = output_dir / "submission_audit.json"
        predictions = json.loads(submission_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        submission_sha = _sha(submission_path)
        audit_sha = _sha(audit_path)
    return predictions, audit, runtime, submission_sha, audit_sha


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    runtime_tasks = {
        task_id: {
            "train": task["train"],
            "test": [{"input": pair["input"]} for pair in task["test"]],
        }
        for task_id, task in challenge.items()
    }
    print(json.dumps({"phase": "exact_v28_public_runtime_started", "tasks": len(runtime_tasks)}), flush=True)
    predictions, audit, runtime, submission_sha, audit_sha = _run_exact_bundle(runtime_tasks)

    # Open public targets only after all exact v28 predictions have completed.
    input_target_relation = Counter()
    train_example_count = Counter()
    exact_position = Counter()
    target_shape = Counter()
    attempt_shape_alignment = Counter()
    wrong_attempt_count = Counter()
    pixel_accuracy_bins = Counter()
    pixel_accuracy_sum = 0.0
    pixel_accuracy_count = 0
    errors_with_shape_match = 0
    errors_without_shape_match = 0
    examples = exact_examples = exact_tasks = 0
    per_task_correct = []
    for task_id, task in challenge.items():
        rows = predictions[task_id]
        targets = json.loads((TRAINING / f"{task_id}.json").read_text(encoding="utf-8"))["test"]
        task_correct = []
        for index, pair in enumerate(task["test"]):
            row = rows[index]
            target = targets[index]["output"]
            input_grid = pair["input"]
            input_dims = _shape(input_grid)
            target_dims = _shape(target)
            attempt1, attempt2 = row["attempt_1"], row["attempt_2"]
            correct1 = attempt1 == target
            correct2 = attempt2 == target
            correct = correct1 or correct2
            examples += 1
            exact_examples += correct
            task_correct.append(correct)
            exact_position["attempt_1_only"] += correct1 and not correct2
            exact_position["attempt_2_only"] += correct2 and not correct1
            exact_position["both"] += correct1 and correct2
            exact_position["neither"] += not correct
            train_count = len(task.get("train", []))
            train_bin = "1" if train_count == 1 else "2" if train_count == 2 else "3-4" if train_count <= 4 else "5+"
            train_example_count[train_bin] += 1
            input_target_relation[_relation(input_dims, target_dims)] += 1
            target_shape[f"{target_dims[0]}x{target_dims[1]}"] += 1
            shape1 = _shape(attempt1) == target_dims
            shape2 = _shape(attempt2) == target_dims
            alignment = "both" if shape1 and shape2 else "attempt_1_only" if shape1 else "attempt_2_only" if shape2 else "neither"
            attempt_shape_alignment[alignment] += 1
            if not correct:
                wrong_attempt_count["both_wrong"] += 1
                has_shape = shape1 or shape2
                errors_with_shape_match += has_shape
                errors_without_shape_match += not has_shape
                for prediction in (attempt1, attempt2):
                    accuracy = _pixel_accuracy(prediction, target)
                    pixel_accuracy_bins[_pixel_bin(accuracy)] += 1
                    if accuracy is not None:
                        pixel_accuracy_sum += accuracy
                        pixel_accuracy_count += 1
        per_task_correct.append(all(task_correct))
    exact_tasks = sum(per_task_correct)

    baseline_report = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    baseline = baseline_report["v28_full_runtime"]
    observed = {"exact_tasks": exact_tasks, "exact_examples": exact_examples}
    if observed != baseline:
        raise RuntimeError(f"exact v28 repeat differed: observed={observed}, stored={baseline}")
    report = {
        "schema": "arc2-v28-residual-shape-audit-v1",
        "public_challenge_tasks": len(challenge),
        "public_challenge_examples": examples,
        "exact_v28_score": observed,
        "v28_repeat_runtime_seconds": round(runtime, 3),
        "baseline_runtime_seconds": baseline_report.get("runtime_seconds"),
        "attempt_exact_position": dict(exact_position),
        "wrong_examples_with_any_attempt_shape_matching_target": errors_with_shape_match,
        "wrong_examples_with_no_attempt_shape_matching_target": errors_without_shape_match,
        "attempt_output_shape_alignment_all_examples": dict(attempt_shape_alignment),
        "input_to_target_shape_relation": dict(input_target_relation),
        "training_example_count_bins": dict(train_example_count),
        "wrong_attempt_pixel_accuracy_bins_when_shape_matches_target": dict(pixel_accuracy_bins),
        "mean_wrong_attempt_pixel_accuracy_on_shape_matched_outputs": round(pixel_accuracy_sum / pixel_accuracy_count, 6) if pixel_accuracy_count else None,
        "shape_matched_wrong_attempt_count": pixel_accuracy_count,
        "target_output_shape_counts": dict(target_shape),
        "fallback_count": audit.get("fallback_count"),
        "runtime_received_test_targets": False,
        "targets_read_after_exact_runtime_completion": True,
        "per_task_ids_grids_predictions_or_targets_written": False,
        "temporary_outputs_and_payload_removed": True,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "build_manifest": _sha(BUILD / "build-manifest.json"),
            "baseline_full_report": _sha(BASELINE_REPORT),
            "exact_submission_temporary_sha256": submission_sha,
            "exact_audit_temporary_sha256": audit_sha,
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
