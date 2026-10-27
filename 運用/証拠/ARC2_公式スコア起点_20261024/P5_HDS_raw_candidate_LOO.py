"""Evaluate HDS-approved mechanism proposals as a protected second guess on LOO."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
sys.path.insert(1, str(ROOT))
from 接続.ARC2.HDS接続 import 課題を解く  # noqa: E402


TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
SUPPORT_MINIMUM = 3


def valid_grid(value):
    return (
        isinstance(value, list)
        and 1 <= len(value) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(value[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in value
        )
    )


def key(grid):
    return tuple(tuple(row) for row in grid)


def select_alternative(predictions, first, minimum_votes):
    votes = Counter(
        key(row["answer"])
        for row in predictions
        if isinstance(row, dict)
        and valid_grid(row.get("answer"))
        and key(row["answer"]) != key(first)
    )
    if not votes:
        return None
    highest = max(votes.values())
    winners = [candidate for candidate, count in votes.items() if count == highest]
    if highest < minimum_votes or len(winners) != 1:
        return None
    return [list(row) for row in winners[0]]


def main():
    files = sorted(TRAINING_DIR.glob("*.json"))
    manifest = hashlib.sha256()
    eligible_tasks = folds = 0
    hds_answer_rows = first_exact = 0
    raw_candidate_folds = raw_candidate_votes = 0
    second1_folds = second1_exact = second1_wrong = 0
    union1_exact = 0
    second2_folds = second2_exact = second2_wrong = 0
    union2_exact = 0
    family_vote_histogram = Counter()
    started = time.perf_counter()

    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) < SUPPORT_MINIMUM + 1:
            continue
        eligible_tasks += 1
        for index, heldout in enumerate(examples):
            folds += 1
            teachers = [pair for i, pair in enumerate(examples) if i != index]
            result = 課題を解く(
                {"train": teachers, "test": [{"input": heldout["input"]}]},
                [],
                候補収集=True,
            )
            row = result.get("results", [{}])[0]
            answer = row.get("answer")
            has_first_answer = valid_grid(answer)
            if has_first_answer:
                hds_answer_rows += 1
                first = answer
            else:
                # Preserve the established input fallback for distinct-candidate
                # filtering, but never score a HOLD/fallback as an HDS answer.
                first = heldout["input"]
            is_first_exact = has_first_answer and first == heldout["output"]
            first_exact += int(is_first_exact)

            proposals = row.get("candidate_predictions", [])
            raw_candidate_votes += len(proposals)
            candidate_grids = {
                key(proposal["answer"])
                for proposal in proposals
                if isinstance(proposal, dict)
                and valid_grid(proposal.get("answer"))
                and key(proposal["answer"]) != key(first)
            }
            if candidate_grids:
                raw_candidate_folds += 1
            family_vote_histogram[str(len(candidate_grids))] += 1

            guess1 = select_alternative(proposals, first, minimum_votes=1)
            if guess1 is not None:
                second1_folds += 1
                is_exact = guess1 == heldout["output"]
                second1_exact += int(is_exact)
                second1_wrong += int(not is_exact)
            union1_exact += int(is_first_exact or guess1 == heldout["output"])

            guess2 = select_alternative(proposals, first, minimum_votes=2)
            if guess2 is not None:
                second2_folds += 1
                is_exact = guess2 == heldout["output"]
                second2_exact += int(is_exact)
                second2_wrong += int(not is_exact)
            union2_exact += int(is_first_exact or guess2 == heldout["output"])

        if eligible_tasks % 25 == 0:
            print(json.dumps({"eligible_tasks_done": eligible_tasks, "loo_folds_done": folds}, sort_keys=True), flush=True)

    result = {
        "schema": "arc2-p5-hds-raw-candidate-second-guess-loo.v1",
        "instruction_id": "ARC2-SCORE-GATE-20261024",
        "hds_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
        "probe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "training_manifest_sha256": manifest.hexdigest(),
        "data_source": "public ARC-AGI-2 training split only",
        "prior_examples_used": 0,
        "minimum_teacher_support": SUPPORT_MINIMUM,
        "eligible_tasks": eligible_tasks,
        "loo_folds": folds,
        "hds_first_answer_rows": hds_answer_rows,
        "hds_first_guess_exact": first_exact,
        "fallback_as_correct": False,
        "first_guess_scoring": "only non-HOLD HDS answers; input fallback excluded",
        "folds_with_any_distinct_raw_candidate": raw_candidate_folds,
        "raw_candidate_family_votes": raw_candidate_votes,
        "distinct_candidate_count_per_fold_histogram": dict(sorted(family_vote_histogram.items())),
        "second_guess_one_vote_folds": second1_folds,
        "second_guess_one_vote_exact": second1_exact,
        "second_guess_one_vote_wrong": second1_wrong,
        "first_or_one_vote_second_exact": union1_exact,
        "second_guess_two_vote_folds": second2_folds,
        "second_guess_two_vote_exact": second2_exact,
        "second_guess_two_vote_wrong": second2_wrong,
        "first_or_two_vote_second_exact": union2_exact,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
    }
    report = Path(__file__).with_suffix(".json")
    report.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
