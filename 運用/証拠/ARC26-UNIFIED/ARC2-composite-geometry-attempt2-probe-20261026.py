"""Offline aggregate probe: fill duplicate v16 attempt pairs with a generic program."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate
from 接続.ARC2.単純変換候補 import valid_grid


CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
V16_RUN = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact(row: dict, target: Grid, input_grid: Grid) -> bool:
    return any(
        row.get(name) == target and row.get(name) != input_grid
        for name in ("attempt_1", "attempt_2")
    )


Grid = list[list[int]]


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    runtime_path = V16_RUN / "submission.json"
    audit_path = V16_RUN / "submission_audit.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))

    # Candidate generation receives only challenge train pairs and test inputs.
    candidates: dict[str, list[Grid | None]] = {}
    for task_id, task in challenge.items():
        model = CompositeGeometryCandidate(task["train"])
        candidates[task_id] = [
            model.候補(pair["input"], {})[0] for pair in task["test"]
        ]
    if set(candidates) != set(challenge):
        raise RuntimeError("candidate generation did not cover the challenge")

    # Public training outputs are loaded only after all candidate predictions exist.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    if not set(challenge).issubset(labels):
        raise RuntimeError("missing offline scorecard labels")

    before_tasks = before_examples = after_tasks = after_examples = 0
    candidate_predictions = candidate_exact = candidate_distinct = 0
    pairs_distinct_before = pairs_distinct_after = 0
    newly_correct = regressions = 0
    example_count = 0
    for task_id, task in challenge.items():
        targets = labels[task_id]
        rows = runtime[task_id]
        test_pairs = task["test"]
        if not (len(targets) == len(rows) == len(test_pairs) == len(candidates[task_id])):
            raise RuntimeError("test example count mismatch")
        before_correct = []
        after_correct = []
        for index, target in enumerate(targets):
            row = rows[index]
            input_grid = test_pairs[index]["input"]
            candidate = candidates[task_id][index]
            candidate_predictions += candidate is not None
            candidate_exact += candidate == target and candidate != input_grid
            current = {
                "attempt_1": row["attempt_1"],
                "attempt_2": row["attempt_2"],
            }
            before = exact(current, target, input_grid)
            before_correct.append(before)
            distinct_before = current["attempt_1"] != current["attempt_2"]
            pairs_distinct_before += distinct_before

            updated = dict(current)
            if (
                valid_grid(candidate)
                and candidate != updated["attempt_1"]
                and updated["attempt_2"] == updated["attempt_1"]
            ):
                updated["attempt_2"] = candidate
                candidate_distinct += 1
            after = exact(updated, target, input_grid)
            after_correct.append(after)
            pairs_distinct_after += updated["attempt_1"] != updated["attempt_2"]
            example_count += 1
            before_examples += before
            after_examples += after
        before_task = all(before_correct)
        after_task = all(after_correct)
        before_tasks += before_task
        after_tasks += after_task
        newly_correct += after_task and not before_task
        regressions += before_task and not after_task

    report = {
        "schema": "arc2-composite-geometry-attempt2-probe-v1",
        "tasks": len(challenge),
        "test_examples": example_count,
        "candidate_generation_completed_before_labels_loaded": True,
        "labels_source": "public ARC-AGI-2 training outputs; offline scoring only",
        "runtime_received_targets": False,
        "baseline_submission_sha256": sha(runtime_path),
        "baseline_audit_sha256": sha(audit_path),
        "challenge_sha256": sha(CHALLENGE),
        "candidate_module_sha256": sha(ROOT / "接続/ARC2/複合幾何変換候補.py"),
        "candidate_tasks_with_prediction": sum(bool(any(row is not None for row in rows)) for rows in candidates.values()),
        "candidate_predicted_examples": candidate_predictions,
        "candidate_exact_examples": candidate_exact,
        "new_distinct_attempt_2_rows": candidate_distinct,
        "distinct_attempt_pairs_before": pairs_distinct_before,
        "distinct_attempt_pairs_after": pairs_distinct_after,
        "baseline_correct_tasks": before_tasks,
        "baseline_correct_examples": before_examples,
        "candidate_correct_tasks": after_tasks,
        "candidate_correct_examples": after_examples,
        "delta_tasks": after_tasks - before_tasks,
        "delta_examples": after_examples - before_examples,
        "newly_correct_tasks": newly_correct,
        "regressed_tasks": regressions,
        "selection_policy": "Preserve both v16 attempts unless they are identical; in that case fill attempt_2 only with a valid distinct candidate",
        "official_competition_score": "UNKNOWN_NOT_SUBMITTED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "candidate_predicted_examples", "candidate_exact_examples", "new_distinct_attempt_2_rows",
        "distinct_attempt_pairs_before", "distinct_attempt_pairs_after", "baseline_correct_tasks",
        "candidate_correct_tasks", "delta_tasks", "delta_examples", "newly_correct_tasks", "regressed_tasks"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
