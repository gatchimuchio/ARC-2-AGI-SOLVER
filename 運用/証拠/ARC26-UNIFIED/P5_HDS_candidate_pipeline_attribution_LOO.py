"""Attribute generic HDS candidate pipeline outcomes on public-training LOO.

This is an observational run: it does not change HDS decisions or candidate
outputs. It records only aggregate mechanism-family outcome counts; no task
identifiers, grids, or held-out outputs are written.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
sys.path.insert(1, str(ROOT))
from 接続.ARC2 import HDS接続 as connector  # noqa: E402


TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "運用/証拠/ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json"
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


def select_alternative(predictions, first):
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
    if len(winners) != 1:
        return None
    return [list(row) for row in winners[0]]


def main():
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    original_learning = connector.候補機構を学習
    by_family = defaultdict(Counter)

    def observe_candidate_learning(engine, task, prior, boundary, candidate_fn):
        record = original_learning(engine, task, prior, boundary, candidate_fn)
        if record.get("採用可") and record.get("同値採用"):
            category = "exact_teacher_fit_and_equality_admitted"
        elif record.get("採用可"):
            category = "exact_teacher_fit_without_equality_admission"
        elif record.get("状態") == "充足する候補なし":
            category = "mechanism_produced_no_candidate"
        elif record.get("状態") == "教師反例により不採用":
            category = "candidate_rejected_by_teacher_counterexample"
        else:
            category = "other_rejection"
        by_family[boundary][category] += 1
        return record

    connector.候補機構を学習 = observe_candidate_learning
    files = sorted(TRAINING_DIR.glob("*.json"))
    manifest = hashlib.sha256()
    eligible_tasks = folds = answer_rows = first_exact = 0
    candidate_folds = candidate_votes = union_exact = 0
    answer_statuses = Counter()
    alternatives_by_fold = Counter()
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
            result = connector.課題を解く(
                {"train": teachers, "test": [{"input": heldout["input"]}]},
                [],
                候補収集=True,
            )
            row = result.get("results", [{}])[0]
            answer_statuses[str(row.get("status", "<missing>"))] += 1
            answer = row.get("answer")
            has_answer = valid_grid(answer)
            if has_answer:
                answer_rows += 1
                first = answer
            else:
                # Input fallback is only used to exclude duplicate candidates.
                first = heldout["input"]
            is_first_exact = has_answer and first == heldout["output"]
            first_exact += int(is_first_exact)

            proposals = row.get("candidate_predictions", [])
            candidate_votes += len(proposals)
            alternative_grids = {
                key(proposal["answer"])
                for proposal in proposals
                if isinstance(proposal, dict)
                and valid_grid(proposal.get("answer"))
                and key(proposal["answer"]) != key(first)
            }
            candidate_folds += int(bool(alternative_grids))
            alternatives_by_fold[str(len(alternative_grids))] += 1
            guess = select_alternative(proposals, first)
            union_exact += int(is_first_exact or guess == heldout["output"])

        if eligible_tasks % 25 == 0:
            print(
                json.dumps(
                    {
                        "eligible_tasks_done": eligible_tasks,
                        "loo_folds_done": folds,
                        "elapsed_seconds": round(time.perf_counter() - started, 1),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

    overall = Counter()
    for counts in by_family.values():
        overall.update(counts)
    result = {
        "schema": "arc2-p5-hds-candidate-pipeline-attribution-loo.v1",
        "instruction_id": "ARC26-UNIFIED-RUN-003",
        "run_kind": "observational; decision behavior unchanged",
        "data_source": "public ARC-AGI-2 training split only",
        "prior_examples_used": 0,
        "minimum_teacher_support": SUPPORT_MINIMUM,
        "eligible_tasks": eligible_tasks,
        "loo_folds": folds,
        "training_manifest_sha256": manifest.hexdigest(),
        "baseline_training_manifest_sha256": baseline["training_manifest_sha256"],
        "baseline_loo_folds": baseline["loo_folds"],
        "production_hds_source_sha256": hashlib.sha256(
            (ROOT / "接続/ARC2/HDS接続.py").read_bytes()
        ).hexdigest(),
        "candidate_module_families": len(by_family),
        "candidate_module_outcomes": dict(sorted(overall.items())),
        "candidate_module_outcomes_by_family": {
            family: dict(sorted(counts.items()))
            for family, counts in sorted(by_family.items())
        },
        "answer_statuses": dict(sorted(answer_statuses.items())),
        "first_answer_rows": answer_rows,
        "first_answer_exact": first_exact,
        "fallback_as_correct": False,
        "fallback_input_used_only_for_candidate_deduplication": True,
        "folds_with_distinct_candidate": candidate_folds,
        "raw_candidate_family_votes": candidate_votes,
        "distinct_candidate_count_per_fold_histogram": dict(
            sorted(alternatives_by_fold.items(), key=lambda item: int(item[0]))
        ),
        "first_or_one_vote_second_exact": union_exact,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
    }
    result["manifest_matches_baseline"] = (
        result["training_manifest_sha256"] == baseline["training_manifest_sha256"]
    )
    result["metrics_match_baseline"] = (
        folds == baseline["loo_folds"]
        and answer_rows == baseline["hds_first_answer_rows"]
        and first_exact == baseline["hds_first_guess_exact"]
        and candidate_folds == baseline["folds_with_any_distinct_raw_candidate"]
        and candidate_votes == baseline["raw_candidate_family_votes"]
        and union_exact == baseline["first_or_one_vote_second_exact"]
    )
    report = Path(__file__).with_suffix(".json")
    report.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
