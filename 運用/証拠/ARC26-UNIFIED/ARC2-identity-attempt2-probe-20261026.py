"""Measure unchanged-input as a distinct second guess on duplicate pairs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
RUNTIME = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v17-composite-geometry-20261026/full-runtime-output-20261026"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    submission_path = RUNTIME / "submission.json"
    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    # Generate all second-guess selections before opening public targets.
    updated = {}
    for task_id, task in challenge.items():
        updated[task_id] = []
        for index, pair in enumerate(task["test"]):
            row = submission[task_id][index]
            first, second = row["attempt_1"], row["attempt_2"]
            use_identity = first != pair["input"] and second == first
            updated[task_id].append(
                pair["input"] if use_identity else second
            )

    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    before_grid_tasks = before_grid_examples = after_grid_tasks = after_grid_examples = 0
    before_nonidentity_tasks = before_nonidentity_examples = 0
    after_nonidentity_tasks = after_nonidentity_examples = 0
    distinct_before = distinct_after = identity_attempts = identity_exact = 0
    new_grid_tasks = regressed_grid_tasks = 0
    new_grid_examples = regressed_grid_examples = 0
    for task_id, task in challenge.items():
        before_exact, after_exact, before_strict, after_strict = [], [], [], []
        for index, pair in enumerate(task["test"]):
            target, source = labels[task_id][index], pair["input"]
            row = submission[task_id][index]
            first, second = row["attempt_1"], row["attempt_2"]
            updated_second = updated[task_id][index]
            base = target in (first, second)
            candidate = target in (first, updated_second)
            strict_base = base and target != source
            strict_candidate = candidate and target != source
            before_exact.append(base)
            after_exact.append(candidate)
            before_strict.append(strict_base)
            after_strict.append(strict_candidate)
            before_grid_examples += base
            after_grid_examples += candidate
            before_nonidentity_examples += strict_base
            after_nonidentity_examples += strict_candidate
            distinct_before += first != second
            distinct_after += first != updated_second
            identity_attempts += updated_second == source and first != source
            identity_exact += updated_second == target and target == source and first != target
            new_grid_examples += candidate and not base
            regressed_grid_examples += base and not candidate
        base_task, candidate_task = all(before_exact), all(after_exact)
        before_grid_tasks += base_task
        after_grid_tasks += candidate_task
        before_nonidentity_tasks += all(before_strict)
        after_nonidentity_tasks += all(after_strict)
        new_grid_tasks += candidate_task and not base_task
        regressed_grid_tasks += base_task and not candidate_task

    report = {
        "schema": "arc2-identity-attempt2-probe-v1",
        "tasks": len(challenge),
        "test_examples": sum(len(task["test"]) for task in challenge.values()),
        "candidate_generation_completed_before_labels_loaded": True,
        "runtime_received_targets": False,
        "labels_source": "public ARC-AGI-2 training outputs; offline scoring only",
        "v17_submission_sha256": sha(submission_path),
        "challenge_sha256": sha(CHALLENGE),
        "duplicate_pairs_filled_with_identity": identity_attempts,
        "identity_alternatives_exact_examples": identity_exact,
        "distinct_attempt_pairs_before": distinct_before,
        "distinct_attempt_pairs_after": distinct_after,
        "baseline_exact_grid_tasks": before_grid_tasks,
        "candidate_exact_grid_tasks": after_grid_tasks,
        "delta_exact_grid_tasks": after_grid_tasks - before_grid_tasks,
        "baseline_exact_grid_examples": before_grid_examples,
        "candidate_exact_grid_examples": after_grid_examples,
        "delta_exact_grid_examples": after_grid_examples - before_grid_examples,
        "newly_correct_grid_tasks": new_grid_tasks,
        "regressed_grid_tasks": regressed_grid_tasks,
        "newly_correct_grid_examples": new_grid_examples,
        "regressed_grid_examples": regressed_grid_examples,
        "baseline_nonidentity_correct_tasks": before_nonidentity_tasks,
        "candidate_nonidentity_correct_tasks": after_nonidentity_tasks,
        "baseline_nonidentity_correct_examples": before_nonidentity_examples,
        "candidate_nonidentity_correct_examples": after_nonidentity_examples,
        "selection_policy": "Preserve attempt_1 and any distinct existing attempt_2; where attempts duplicate and attempt_1 differs from test input, use unchanged test input as attempt_2",
        "official_competition_score": "UNKNOWN_NOT_SUBMITTED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "duplicate_pairs_filled_with_identity", "identity_alternatives_exact_examples",
        "distinct_attempt_pairs_before", "distinct_attempt_pairs_after", "baseline_exact_grid_tasks",
        "candidate_exact_grid_tasks", "delta_exact_grid_tasks", "baseline_exact_grid_examples",
        "candidate_exact_grid_examples", "delta_exact_grid_examples", "newly_correct_grid_tasks",
        "regressed_grid_tasks", "baseline_nonidentity_correct_tasks", "candidate_nonidentity_correct_tasks"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
