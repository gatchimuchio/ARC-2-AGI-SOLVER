"""Probe teacher-consistent alternate whole-grid D4 outputs as attempt 2."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from 接続.ARC2.格子D4教材 import 格子D4教材, _変換群  # noqa: E402
from 接続.ARC2.単純変換候補 import valid_grid  # noqa: E402


CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
RUNTIME = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidates(model, grid):
    if not model.変換候補 and not model.色写像候補:
        return []
    transformed = _変換群(grid)
    predictions = []
    for name in model.変換候補:
        prediction = transformed[name]
        if prediction not in predictions:
            predictions.append(prediction)
    for name, pairs in model.色写像候補:
        source = transformed[name]
        mapping = dict(pairs)
        colors = {color for row in source for color in row}
        if not colors.issubset(mapping):
            continue
        prediction = [[mapping[color] for color in row] for row in source]
        if prediction not in predictions:
            predictions.append(prediction)
    return [prediction for prediction in predictions if valid_grid(prediction)]


def exact(row, target, source):
    return any(row.get(name) == target and row.get(name) != source for name in ("attempt_1", "attempt_2"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    submission_path = RUNTIME / "submission.json"
    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    alternatives = {}
    fit_examples = multi_output_examples = 0
    for task_id, task in challenge.items():
        model = 格子D4教材(task["train"])
        task_candidates = []
        for pair in task["test"]:
            options = candidates(model, pair["input"])
            fit_examples += bool(options)
            multi_output_examples += len(options) > 1
            task_candidates.append(options)
        alternatives[task_id] = task_candidates

    # Public targets are read only after all D4 candidate sets are generated.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    before_tasks = before_examples = after_tasks = after_examples = 0
    alternative_exact = selected = distinct_before = distinct_after = 0
    newly_correct = regressions = 0
    for task_id, task in challenge.items():
        before_rows, after_rows = [], []
        for index, pair in enumerate(task["test"]):
            target, source = labels[task_id][index], pair["input"]
            row = submission[task_id][index]
            first, second = row["attempt_1"], row["attempt_2"]
            options = alternatives[task_id][index]
            before = exact(row, target, source)
            updated_second = second
            option = next((value for value in options if value != first), None)
            if option is not None:
                alternative_exact += option == target and option != source
                if second == first:
                    updated_second = option
                    selected += 1
            after = target in (first, updated_second) and target != source
            before_rows.append(before)
            after_rows.append(after)
            before_examples += before
            after_examples += after
            distinct_before += first != second
            distinct_after += first != updated_second
        before_task, after_task = all(before_rows), all(after_rows)
        before_tasks += before_task
        after_tasks += after_task
        newly_correct += after_task and not before_task
        regressions += before_task and not after_task

    report = {
        "schema": "arc2-d4-alternative-attempt2-probe-v1",
        "tasks": len(challenge),
        "test_examples": sum(len(task["test"]) for task in challenge.values()),
        "candidate_generation_completed_before_labels_loaded": True,
        "runtime_received_targets": False,
        "labels_source": "public ARC-AGI-2 training outputs; offline scoring only",
        "baseline_submission_sha256": sha(submission_path),
        "challenge_sha256": sha(CHALLENGE),
        "d4_module_sha256": sha(ROOT / "接続/ARC2/格子D4教材.py"),
        "examples_with_d4_fit": fit_examples,
        "examples_with_multiple_distinct_d4_predictions": multi_output_examples,
        "selected_distinct_alternatives": selected,
        "selected_alternative_exact_examples": alternative_exact,
        "distinct_attempt_pairs_before": distinct_before,
        "distinct_attempt_pairs_after": distinct_after,
        "baseline_correct_tasks": before_tasks,
        "baseline_correct_examples": before_examples,
        "candidate_correct_tasks": after_tasks,
        "candidate_correct_examples": after_examples,
        "delta_tasks": after_tasks - before_tasks,
        "delta_examples": after_examples - before_examples,
        "newly_correct_tasks": newly_correct,
        "regressed_tasks": regressions,
        "selection_policy": "Preserve v16 attempt_1; choose the first distinct output among D4 programs that reproduce every training pair, only filling a duplicate attempt pair",
        "official_competition_score": "UNKNOWN_NOT_SUBMITTED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "examples_with_d4_fit", "examples_with_multiple_distinct_d4_predictions",
        "selected_distinct_alternatives", "selected_alternative_exact_examples",
        "distinct_attempt_pairs_before", "distinct_attempt_pairs_after", "baseline_correct_tasks",
        "candidate_correct_tasks", "delta_tasks", "delta_examples", "newly_correct_tasks", "regressed_tasks"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
