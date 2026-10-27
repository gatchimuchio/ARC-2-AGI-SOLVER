"""Offline scorecard for v17 against the saved full v16 runtime output."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
DEFAULT_BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_correct(row: dict, target: list[list[int]], source: list[list[int]]) -> bool:
    return any(
        row.get(key) == target and row.get(key) != source
        for key in ("attempt_1", "attempt_2")
    )


def score(submission: dict, challenge: dict, labels: dict[str, list]) -> tuple[int, int, int]:
    tasks = examples = distinct_pairs = 0
    for task_id, task in challenge.items():
        rows = submission[task_id]
        correct = [
            row_correct(rows[index], labels[task_id][index], test_pair["input"])
            for index, test_pair in enumerate(task["test"])
        ]
        tasks += bool(correct) and all(correct)
        examples += sum(correct)
        distinct_pairs += sum(
            row.get("attempt_1") != row.get("attempt_2")
            for row in rows
        )
    return tasks, examples, distinct_pairs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline_path = args.baseline_dir / "submission.json"
    candidate_path = args.candidate_dir / "submission.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))

    # Load public targets only after both runtime prediction artifacts exist.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    if not set(challenge).issubset(labels):
        raise RuntimeError("missing public scorecard labels")

    before = score(baseline, challenge, labels)
    after = score(candidate, challenge, labels)
    changed_first = changed_second = 0
    newly_correct = regressed = 0
    for task_id, task in challenge.items():
        base_rows, candidate_rows = baseline[task_id], candidate[task_id]
        base_correct = [
            row_correct(base_rows[index], labels[task_id][index], test_pair["input"])
            for index, test_pair in enumerate(task["test"])
        ]
        candidate_correct = [
            row_correct(candidate_rows[index], labels[task_id][index], test_pair["input"])
            for index, test_pair in enumerate(task["test"])
        ]
        changed_first += sum(
            left.get("attempt_1") != right.get("attempt_1")
            for left, right in zip(base_rows, candidate_rows, strict=True)
        )
        changed_second += sum(
            left.get("attempt_2") != right.get("attempt_2")
            for left, right in zip(base_rows, candidate_rows, strict=True)
        )
        newly_correct += all(candidate_correct) and not all(base_correct)
        regressed += all(base_correct) and not all(candidate_correct)

    runtime_path = args.candidate_dir / "submission_audit.json"
    audit = json.loads(runtime_path.read_text(encoding="utf-8"))
    diagnostics = audit.get("aggregate_diagnostics", {})
    report = {
        "schema": "arc2-v17-composite-geometry-scorecard-v1",
        "tasks": len(challenge),
        "test_examples": sum(len(task["test"]) for task in challenge.values()),
        "labels_source": "public ARC-AGI-2 training outputs; offline scoring only",
        "candidate_predictions_completed_before_labels_loaded": True,
        "runtime_received_targets": False,
        "baseline_submission_sha256": sha(baseline_path),
        "candidate_submission_sha256": sha(candidate_path),
        "candidate_audit_sha256": sha(runtime_path),
        "challenge_sha256": sha(CHALLENGE),
        "candidate_runtime_seconds": audit.get("seconds"),
        "baseline_correct_tasks": before[0],
        "baseline_correct_examples": before[1],
        "baseline_distinct_attempt_pairs": before[2],
        "candidate_correct_tasks": after[0],
        "candidate_correct_examples": after[1],
        "candidate_distinct_attempt_pairs": after[2],
        "delta_tasks": after[0] - before[0],
        "delta_examples": after[1] - before[1],
        "newly_correct_tasks": newly_correct,
        "regressed_tasks": regressed,
        "changed_attempt_1_examples": changed_first,
        "changed_attempt_2_examples": changed_second,
        "candidate_family_counts": diagnostics.get("candidate_family_counts", {}),
        "official_competition_score": "UNKNOWN_NOT_SUBMITTED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "baseline_correct_tasks", "baseline_correct_examples", "baseline_distinct_attempt_pairs",
        "candidate_correct_tasks", "candidate_correct_examples", "candidate_distinct_attempt_pairs",
        "delta_tasks", "delta_examples", "newly_correct_tasks", "regressed_tasks",
        "changed_attempt_1_examples", "changed_attempt_2_examples", "candidate_family_counts"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
