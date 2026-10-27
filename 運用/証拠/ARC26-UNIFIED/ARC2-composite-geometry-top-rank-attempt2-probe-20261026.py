"""Probe two highest-support predictions at the simplest fitted rank."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate, _geometry, _key, _prepare  # noqa: E402
from 接続.ARC2.単純変換候補 import valid_grid  # noqa: E402

CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
RUNTIME = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v17-composite-geometry-20261026/full-runtime-output-20261026"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def top_two_at_best_rank(model, query):
    best_rank = min((rank for _, _, rank in model.programs), default=None)
    if best_rank is None:
        return []
    counts = Counter()
    for program, color_map, rank in model.programs:
        if rank != best_rank:
            continue
        orientation, crop, operation, rows, columns = program
        source = _prepare(query, orientation, crop)
        if source is None:
            continue
        transformed = _geometry(source, operation, rows, columns)
        if transformed is None:
            continue
        candidate = [[color_map.get(color, color) for color in row] for row in transformed]
        if valid_grid(candidate):
            counts[_key(candidate)] += 1
    return [
        [list(row) for row in key]
        for key, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:2]
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    submission_path = RUNTIME / "submission.json"
    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    candidates = {}
    for task_id, task in challenge.items():
        model = CompositeGeometryCandidate(task["train"])
        candidates[task_id] = [top_two_at_best_rank(model, pair["input"]) for pair in task["test"]]

    # Load public targets after all candidate predictions are complete.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    before_tasks = before_examples = after_tasks = after_examples = 0
    examples_with_fit = examples_with_alternatives = alternatives_used = alternatives_exact = 0
    distinct_before = distinct_after = newly_correct = regressions = 0
    for task_id, task in challenge.items():
        before_rows = []
        after_rows = []
        for index, pair in enumerate(task["test"]):
            target, source = labels[task_id][index], pair["input"]
            row = submission[task_id][index]
            choices = candidates[task_id][index]
            examples_with_fit += bool(choices)
            examples_with_alternatives += len(choices) > 1
            primary, second = row["attempt_1"], row["attempt_2"]
            baseline_ok = target in (primary, second) and target != source
            updated_second = second
            if second == primary and choices:
                selected = next((choice for choice in choices if choice != primary and choice != source), None)
                if selected is not None:
                    updated_second = selected
                    alternatives_used += 1
                    alternatives_exact += selected == target
            after_ok = target in (primary, updated_second) and target != source
            before_rows.append(baseline_ok)
            after_rows.append(after_ok)
            before_examples += baseline_ok
            after_examples += after_ok
            distinct_before += primary != second
            distinct_after += primary != updated_second
        before_task, after_task = all(before_rows), all(after_rows)
        before_tasks += before_task
        after_tasks += after_task
        newly_correct += after_task and not before_task
        regressions += before_task and not after_task

    report = {
        "schema": "arc2-composite-geometry-top-rank-attempt2-probe-v1",
        "tasks": len(challenge),
        "test_examples": sum(len(task["test"]) for task in challenge.values()),
        "candidate_generation_completed_before_labels_loaded": True,
        "labels_source": "public ARC-AGI-2 training outputs; offline scoring only",
        "runtime_received_targets": False,
        "v17_submission_sha256": sha(submission_path),
        "challenge_sha256": sha(CHALLENGE),
        "candidate_module_sha256": sha(ROOT / "接続/ARC2/複合幾何変換候補.py"),
        "examples_with_best_rank_fit": examples_with_fit,
        "examples_with_two_distinct_best_rank_predictions": examples_with_alternatives,
        "alternatives_used_to_fill_duplicate_pairs": alternatives_used,
        "selected_alternative_exact_examples": alternatives_exact,
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
        "selection_policy": "Preserve v17 attempt_1; when attempts are identical, use the highest-support distinct prediction at the simplest fitted program rank",
        "official_competition_score": "UNKNOWN_NOT_SUBMITTED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "examples_with_best_rank_fit", "examples_with_two_distinct_best_rank_predictions",
        "alternatives_used_to_fill_duplicate_pairs", "selected_alternative_exact_examples",
        "distinct_attempt_pairs_before", "distinct_attempt_pairs_after", "baseline_correct_tasks",
        "candidate_correct_tasks", "delta_tasks", "delta_examples", "newly_correct_tasks", "regressed_tasks"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
