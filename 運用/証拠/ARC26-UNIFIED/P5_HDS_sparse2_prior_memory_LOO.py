"""Leakage-guarded public-training LOO ablation for approved prior memory.

Only the parent evaluator sees held-out outputs. The solver receives training
examples plus the test input, with either no prior or the fixed approved prior.
No task IDs, grids, answers, or per-fold rows are written to the artifact.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
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
REFERENCE_PATH = ROOT / "接続/ARC2/テンプレート充填教材.json"
SPARSE_TRAIN_PAIR_COUNT = 2


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


def grid_key(grid):
    return tuple(tuple(row) for row in grid)


def select_alternative(predictions, first):
    votes = Counter(
        grid_key(row["answer"])
        for row in predictions
        if isinstance(row, dict)
        and valid_grid(row.get("answer"))
        and grid_key(row["answer"]) != grid_key(first)
    )
    if not votes:
        return None
    maximum = max(votes.values())
    winners = [candidate for candidate, count in votes.items() if count == maximum]
    return [list(row) for row in winners[0]] if len(winners) == 1 else None


def score_result(result, heldout):
    row = result.get("results", [{}])[0]
    answer = row.get("answer")
    has_answer = valid_grid(answer)
    first = answer if has_answer else heldout["input"]
    first_exact = has_answer and answer == heldout["output"]
    guess = select_alternative(row.get("candidate_predictions", []), first)
    distinct = guess is not None
    second_exact = distinct and guess == heldout["output"]
    return {
        "answer": int(has_answer),
        "fallback": int(not has_answer),
        "first_exact": int(first_exact),
        "first_wrong": int(has_answer and not first_exact),
        "distinct_second": int(distinct),
        "second_exact": int(second_exact),
        "second_wrong": int(distinct and not second_exact),
        "union_exact": int(first_exact or second_exact),
        "candidate_votes": len(row.get("candidate_predictions", [])),
    }


def main(pilot_tasks: int = 0):
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    if reference.get("分割") != "training":
        raise RuntimeError("Approved prior memory is not training-only")
    sources = reference.get("教材", [])
    source_ids = {item["課題ID"] for item in sources}
    prior = connector.事前教材を読む()
    if len(prior) != 2 or any(set(pair) != {"input", "output"} for pair in prior):
        raise RuntimeError("Approved prior memory shape changed")
    prior_inputs = {grid_key(pair["input"]) for pair in prior}

    files = sorted(TRAINING_DIR.glob("*.json"))
    manifest = hashlib.sha256()
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())

    totals = {
        "previous_no_prior": Counter(),
        "current_approved_prior": Counter(),
    }
    condition_seconds = Counter()
    source_task_exclusions = input_overlap_exclusions = folds = 0
    eligible_paths = []
    for path in files:
        raw = path.read_bytes()
        task = json.loads(raw)
        examples = task.get("train", [])
        if len(examples) != SPARSE_TRAIN_PAIR_COUNT:
            continue
        if path.stem in source_ids:
            source_task_exclusions += 1
            continue
        # Exclude a whole task if any public training input overlaps a prior
        # input, preventing support leakage through either held-out or teachers.
        if any(grid_key(pair["input"]) in prior_inputs for pair in examples):
            input_overlap_exclusions += 1
            continue
        eligible_paths.append(path)

    if pilot_tasks < 0 or (pilot_tasks and pilot_tasks > len(eligible_paths)):
        raise ValueError("Invalid pilot task count")
    selected_paths = eligible_paths[:pilot_tasks] if pilot_tasks else eligible_paths
    eligible_tasks = 0
    started = time.perf_counter()

    for path in selected_paths:
        task = json.loads(path.read_bytes())
        examples = task["train"]
        eligible_tasks += 1
        for index, heldout in enumerate(examples):
            teachers = [pair for i, pair in enumerate(examples) if i != index]
            solver_task = {"train": teachers, "test": [{"input": deepcopy(heldout["input"])}]}
            if set(solver_task["test"][0]) != {"input"}:
                raise RuntimeError("Held-out output crossed the solver boundary")
            call_order = (
                ("previous_no_prior", [])
                if folds % 2 == 1
                else ("current_approved_prior", deepcopy(prior))
            )
            other_order = (
                ("current_approved_prior", deepcopy(prior))
                if call_order[0] == "previous_no_prior"
                else ("previous_no_prior", [])
            )
            results = {}
            for name, memory in (call_order, other_order):
                call_started = time.perf_counter()
                results[name] = connector.課題を解く(
                    deepcopy(solver_task), deepcopy(memory), 候補収集=True
                )
                condition_seconds[name] += time.perf_counter() - call_started
            for name, result in (
                ("previous_no_prior", results["previous_no_prior"]),
                ("current_approved_prior", results["current_approved_prior"]),
            ):
                totals[name].update(score_result(result, heldout))
            folds += 1

        if pilot_tasks or eligible_tasks % 25 == 0 or eligible_tasks == len(selected_paths):
            print(json.dumps({
                "eligible_tasks_done": eligible_tasks,
                "loo_folds_done": folds,
                "elapsed_seconds": round(time.perf_counter() - started, 1),
            }), flush=True)

    if not folds:
        raise RuntimeError("No leakage-safe sparse-task LOO folds were eligible")
    metrics = {name: dict(sorted(counts.items())) for name, counts in totals.items()}
    fields = sorted(set(metrics["previous_no_prior"]) | set(metrics["current_approved_prior"]))
    delta = {
        field: metrics["current_approved_prior"].get(field, 0)
        - metrics["previous_no_prior"].get(field, 0)
        for field in fields
    }
    previous_seconds = condition_seconds["previous_no_prior"]
    current_seconds = condition_seconds["current_approved_prior"]
    runtime_delta = current_seconds - previous_seconds
    evidence = {
        "schema": "arc2-p5-sparse-two-example-prior-loo.v1",
        "experiment_id": "ARC2-C2-060-SPARSE_TWO_EXAMPLE_PRIOR_MEMORY",
        "run_type": "pilot" if pilot_tasks else "full",
        "data_source": "public ARC-AGI-2 training split only",
        "conditions": {
            "previous": "one remaining within-task teacher pair, no prior examples",
            "current": "one remaining within-task teacher pair plus exactly two approved training prior examples",
            "task_training_pair_count": SPARSE_TRAIN_PAIR_COUNT,
        },
        "prior_reference_sha256": hashlib.sha256(REFERENCE_PATH.read_bytes()).hexdigest(),
        "training_manifest_sha256": manifest.hexdigest(),
        "connector_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
        "prior_source_task_count_excluded": source_task_exclusions,
        "additional_input_overlap_task_count_excluded": input_overlap_exclusions,
        "eligible_task_population": len(eligible_paths),
        "eligible_tasks_evaluated": eligible_tasks,
        "pilot_task_limit": pilot_tasks or None,
        "loo_fold_count": folds,
        "metrics_previous_current": metrics,
        "delta_current_minus_previous": delta,
        "runtime_seconds": {
            "previous_no_prior": round(previous_seconds, 3),
            "current_approved_prior": round(current_seconds, 3),
            "delta_current_minus_previous": round(runtime_delta, 3),
            "delta_percent": round(runtime_delta / previous_seconds * 100, 3)
            if previous_seconds
            else None,
            "combined_wall_seconds": round(time.perf_counter() - started, 3),
        },
        "fallback_as_correct": False,
        "first_answer_rows_exclude_fallback": True,
        "candidate_union_counts_only_distinct_second_answers": True,
        "heldout_output_passed_to_solver": False,
        "heldout_output_scored_only_after_solver_return": True,
        "hidden_or_evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "runtime_or_solver_changed": False,
        "production_or_submission_changed": False,
    }
    suffix = "pilot" if pilot_tasks else "full"
    output = Path(__file__).with_name(f"P5_HDS_sparse2_prior_memory_LOO_{suffix}.json")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    output.write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-tasks", type=int, default=0)
    args = parser.parse_args()
    main(args.pilot_tasks)
