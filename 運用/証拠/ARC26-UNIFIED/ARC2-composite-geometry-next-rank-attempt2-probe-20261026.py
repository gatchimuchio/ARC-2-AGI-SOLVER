"""Offline probe of a second, more complex teacher-consistent geometry program."""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from 接続.ARC2.複合幾何変換候補 import (  # noqa: E402
    CompositeGeometryCandidate,
    _geometry,
    _key,
    _prepare,
)
from 接続.ARC2.単純変換候補 import valid_grid  # noqa: E402


CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
RUNTIME = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v17-composite-geometry-20261026/full-runtime-output-20261026"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def second_hypothesis(model, query):
    """Return the first distinct consensus from a later complexity rank."""
    ranks = sorted({rank for _, _, rank in model.programs})
    if not ranks:
        return None, 0
    primary_rank = ranks[0]
    primary, _ = model.候補(query, {})
    if primary is None:
        return None, 0
    primary_key = _key(primary)
    for rank in ranks[1:]:
        outputs = Counter()
        for program, color_map, program_rank in model.programs:
            if program_rank != rank:
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
                outputs[_key(candidate)] += 1
        if len(outputs) != 1:
            continue
        alternative, support = next(iter(outputs.items()))
        if alternative != primary_key:
            return [list(row) for row in alternative], support
    return None, 0


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    submission_path = RUNTIME / "submission.json"
    submission = json.loads(submission_path.read_text(encoding="utf-8"))
    alternatives = {}
    support_counts = []
    for task_id, task in challenge.items():
        model = CompositeGeometryCandidate(task["train"])
        task_alternatives = []
        for pair in task["test"]:
            alternative, support = second_hypothesis(model, pair["input"])
            task_alternatives.append(alternative)
            if alternative is not None:
                support_counts.append(support)
        alternatives[task_id] = task_alternatives

    # Read targets only after every alternate prediction has been generated.
    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in TRAINING.glob("*.json")
    }
    before_tasks = before_examples = after_tasks = after_examples = 0
    alternatives_found = alternatives_distinct = alternatives_exact = 0
    changed_pairs = newly_correct_tasks = regressed_tasks = 0
    pair_distinct_before = pair_distinct_after = 0
    total_examples = 0
    for task_id, task in challenge.items():
        before_correct = []
        after_correct = []
        for index, pair in enumerate(task["test"]):
            target = labels[task_id][index]
            row = submission[task_id][index]
            alternative = alternatives[task_id][index]
            first = row["attempt_1"]
            second = row["attempt_2"]
            before = target in (first, second) and target != pair["input"]
            updated_second = second
            if alternative is not None:
                alternatives_found += 1
                alternatives_exact += alternative == target and alternative != pair["input"]
                if alternative != first and second == first:
                    alternatives_distinct += 1
                    updated_second = alternative
                    changed_pairs += 1
            after = target in (first, updated_second) and target != pair["input"]
            before_correct.append(before)
            after_correct.append(after)
            before_examples += before
            after_examples += after
            pair_distinct_before += first != second
            pair_distinct_after += first != updated_second
            total_examples += 1
        before_task, after_task = all(before_correct), all(after_correct)
        before_tasks += before_task
        after_tasks += after_task
        newly_correct_tasks += after_task and not before_task
        regressed_tasks += before_task and not after_task

    report = {
        "schema": "arc2-composite-geometry-next-rank-attempt2-probe-v1",
        "tasks": len(challenge),
        "test_examples": total_examples,
        "candidate_generation_completed_before_labels_loaded": True,
        "labels_source": "public ARC-AGI-2 training outputs; offline scoring only",
        "runtime_received_targets": False,
        "v17_submission_sha256": sha(submission_path),
        "challenge_sha256": sha(CHALLENGE),
        "candidate_module_sha256": sha(ROOT / "接続/ARC2/複合幾何変換候補.py"),
        "examples_with_distinct_later_rank_consensus": alternatives_found,
        "examples_with_at_least_two_consensus_programs": sum(count >= 2 for count in support_counts),
        "later_rank_exact_examples": alternatives_exact,
        "alternatives_used_to_fill_duplicate_pairs": alternatives_distinct,
        "distinct_attempt_pairs_before": pair_distinct_before,
        "distinct_attempt_pairs_after": pair_distinct_after,
        "baseline_correct_tasks": before_tasks,
        "baseline_correct_examples": before_examples,
        "candidate_correct_tasks": after_tasks,
        "candidate_correct_examples": after_examples,
        "delta_tasks": after_tasks - before_tasks,
        "delta_examples": after_examples - before_examples,
        "newly_correct_tasks": newly_correct_tasks,
        "regressed_tasks": regressed_tasks,
        "selection_policy": "Preserve v17 attempt_1; fill attempt_2 only when v17 attempts are identical and one later-ranked complexity class has a single distinct prediction",
        "official_competition_score": "UNKNOWN_NOT_SUBMITTED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "examples_with_distinct_later_rank_consensus", "examples_with_at_least_two_consensus_programs",
        "later_rank_exact_examples", "alternatives_used_to_fill_duplicate_pairs", "distinct_attempt_pairs_before",
        "distinct_attempt_pairs_after", "baseline_correct_tasks", "candidate_correct_tasks", "delta_tasks",
        "delta_examples", "newly_correct_tasks", "regressed_tasks"
    )}, ensure_ascii=False))


if __name__ == "__main__":
    main()
