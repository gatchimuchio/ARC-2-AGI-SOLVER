"""Measure Kaggle attempt-1/attempt-2 behavior on held-out public ARC2 training."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
HDS_DIR = ROOT / "HDS/学習系統/v0.4.2"
EXPECTED_TRAINING_TASKS = 1000


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


def load_runtime():
    for name in tuple(sys.modules):
        if name == "接続" or name.startswith("接続."):
            del sys.modules[name]
    sys.path.insert(0, str(ROOT))
    sys.path.insert(1, str(HDS_DIR))
    importlib.invalidate_caches()
    return importlib.import_module("接続.ARC2.HDS接続")


def unique_second(candidates, first):
    votes = Counter()
    if not isinstance(candidates, list):
        return None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        grid = item.get("answer")
        if valid_grid(grid) and grid != first:
            votes[tuple(tuple(row) for row in grid)] += 1
    if not votes:
        return None
    maximum = max(votes.values())
    winners = [grid for grid, count in votes.items() if count == maximum]
    if len(winners) != 1:
        return None
    return [list(row) for row in winners[0]]


def score_prediction(prediction, heldout_output):
    valid = valid_grid(prediction)
    exact = valid and prediction == heldout_output
    return {"valid": int(valid), "exact": int(exact), "wrong": int(valid and not exact), "fallback": int(not valid)}


def call(solver, prior, teachers, heldout, collect):
    result = solver(
        {"train": teachers, "test": [{"input": heldout["input"]}]},
        prior,
        候補収集=collect,
    )
    rows = result.get("results") if isinstance(result, dict) else None
    row = rows[0] if isinstance(rows, list) and len(rows) == 1 and isinstance(rows[0], dict) else {}
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-tasks", type=int, default=4)
    parser.add_argument("--sample-seed", type=int, default=20261025)
    parser.add_argument("--budget-seconds", type=float, default=600.0)
    parser.add_argument("--disable-prior", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.pilot_tasks < 1 or args.budget_seconds <= 0:
        raise SystemExit("pilot tasks and time budget must be positive")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    files = sorted(TRAINING_DIR.glob("*.json"))
    if len(files) != EXPECTED_TRAINING_TASKS:
        raise RuntimeError(f"training task count changed: {len(files)}")
    manifest = hashlib.sha256()
    parsed = []
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        parsed.append((path.name, json.loads(raw)))

    runtime = load_runtime()
    available_prior = runtime.事前教材を読む()
    prior = [] if args.disable_prior else available_prior
    template = json.loads((ROOT / "接続/ARC2/テンプレート充填教材.json").read_text(encoding="utf-8"))
    prior_sources = {item["課題ID"] for item in template["教材"]}
    training_stems = {Path(name).stem for name, _ in parsed}
    prior_sources_in_training = prior_sources & training_stems
    eligible = [(name, task) for name, task in parsed if Path(name).stem not in prior_sources]
    if len(eligible) < args.pilot_tasks:
        raise RuntimeError("not enough training tasks after excluding template-prior source tasks")
    rng = random.Random(args.sample_seed)
    selected = rng.sample(eligible, args.pilot_tasks)
    if any(Path(name).stem in prior_sources for name, _ in selected):
        raise RuntimeError("template-prior source task entered held-out sample")

    previous = Counter()
    current_attempt1 = Counter()
    current_attempt2 = Counter()
    current_pair = Counter()
    attempted_second = 0
    folds = 0
    baseline_vs_current_attempt1_different = 0
    regressions = 0
    started = time.perf_counter()
    for task_index, (_, task) in enumerate(selected, 1):
        examples = task.get("train", [])
        for heldout_index, heldout in enumerate(examples):
            if time.perf_counter() - started >= args.budget_seconds:
                break
            teachers = [pair for index, pair in enumerate(examples) if index != heldout_index]
            baseline_row = call(runtime.課題を解く, prior, teachers, heldout, False)
            current_row = call(runtime.課題を解く, prior, teachers, heldout, True)
            baseline_answer = baseline_row.get("answer")
            current_answer = current_row.get("answer")
            previous.update(score_prediction(baseline_answer, heldout["output"]))
            current_attempt1.update(score_prediction(current_answer, heldout["output"]))
            if baseline_answer != current_answer:
                baseline_vs_current_attempt1_different += 1
            if valid_grid(baseline_answer) and baseline_answer == heldout["output"] and not (
                valid_grid(current_answer) and current_answer == heldout["output"]
            ):
                regressions += 1

            first_for_adapter = current_answer if valid_grid(current_answer) else heldout["input"]
            second = unique_second(current_row.get("candidate_predictions"), first_for_adapter)
            if second is not None:
                attempted_second += 1
                second_score = score_prediction(second, heldout["output"])
            else:
                second_score = {"valid": 0, "exact": 0, "wrong": 0}
            current_attempt2.update(second_score)
            pair_score = {
                "valid": int(valid_grid(current_answer) or second is not None),
                "exact": int(
                    (valid_grid(current_answer) and current_answer == heldout["output"])
                    or (second is not None and second == heldout["output"])
                ),
                "wrong": int(
                    (valid_grid(current_answer) and current_answer != heldout["output"])
                    or (second is not None and second != heldout["output"])
                ),
                "fallback": int(not valid_grid(current_answer) and second is None),
            }
            current_pair.update(pair_score)
            folds += 1
        if time.perf_counter() - started >= args.budget_seconds:
            break
        print(json.dumps({"tasks_done": task_index, "folds_done": folds, "elapsed_seconds": round(time.perf_counter() - started, 1)}), flush=True)

    complete = folds == sum(len(task.get("train", [])) for _, task in selected)
    fields = ("valid", "exact", "wrong", "fallback")
    result = {
        "schema": "arc2-p4-attempt12-public-training-loo.v3",
        "experiment_id": "ARC26-ARC2-P4-KAGGLE-ATTEMPT12-LOO",
        "data_source": "public ARC-AGI-2 training split only",
        "eligible_population_after_prior_source_exclusion": len(eligible),
        "selected_tasks": args.pilot_tasks,
        "sample_seed": args.sample_seed,
        "loo_folds": folds,
        "complete": complete,
        "stop_reason": "all_selected_folds" if complete else "time_budget",
        "time_budget_seconds": args.budget_seconds,
        "training_manifest_sha256": manifest.hexdigest(),
        "runtime_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
        "submission_adapter_sha256": hashlib.sha256((ROOT / "接続/ARC2/Kaggle提出.py").read_bytes()).hexdigest(),
        "template_sha256": hashlib.sha256((ROOT / "接続/ARC2/テンプレート充填教材.json").read_bytes()).hexdigest(),
        "prior_examples_available": len(available_prior),
        "prior_examples_loaded": len(prior),
        "prior_enabled": not args.disable_prior,
        "template_prior_source_tasks_total": len(prior_sources),
        "template_prior_source_tasks_present_in_training": len(prior_sources_in_training),
        "prior_source_tasks_excluded_from_loo": len(prior_sources_in_training),
        "previous_attempt1": {key: int(previous[key]) for key in fields},
        "current_attempt1_with_collection": {key: int(current_attempt1[key]) for key in fields},
        "current_unique_attempt2_only": {key: int(current_attempt2[key]) for key in ("valid", "exact", "wrong")},
        "current_attempt_pair": {key: int(current_pair[key]) for key in fields},
        "unique_second_selected": attempted_second,
        "attempt1_output_differences_vs_previous": baseline_vs_current_attempt1_different,
        "attempt1_exact_regressions": regressions,
        "delta_attempt1_exact": int(current_attempt1["exact"] - previous["exact"]),
        "delta_pair_exact_vs_previous_attempt1": int(current_pair["exact"] - previous["exact"]),
        "fallback_counted_correct": False,
        "heldout_output_passed_to_solver": False,
        "heldout_output_scored_only_after_solver_return": True,
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "official_submission_or_rerun": False,
        "production_code_changed_by_runner": False,
        "runtime_seconds": round(time.perf_counter() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()