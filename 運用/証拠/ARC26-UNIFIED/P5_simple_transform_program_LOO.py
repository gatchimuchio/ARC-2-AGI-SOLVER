"""Probe prior-compatible simple grid programs on public ARC2 training LOO.

The candidate sees teacher pairs and the held-out input only. Held-out outputs
stay in the parent scorer. Results contain aggregate counts, never IDs or grids.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
HDS_DIR = ROOT / "HDS/学習系統/v0.4.2"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from 接続.ARC2.単純変換候補 import apply_model, key, predict_pool, valid_grid


def hds_admits(runtime, model, teachers, prior):
    minimum_support = (
        2
        if len(teachers) == 2 and teachers[0]["input"] != teachers[1]["input"]
        else 3
    )
    machine = runtime.HDS学習実行系(最小支持数=minimum_support)
    for pair in teachers:
        machine.実行(runtime.格子観測(pair))

    def candidate(input_grid, _expected):
        return apply_model(model, input_grid), {}

    record = runtime.候補機構を学習(
        machine,
        {"train": teachers, "test": []},
        prior,
        "ARC単純変換プログラム",
        candidate,
    )
    return bool(record["採用可"] and record["同値採用"]), record.get("状態", "unknown")


def unique_second(candidates, first):
    votes = Counter()
    if not isinstance(candidates, list):
        return None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        grid = item.get("answer")
        if valid_grid(grid) and key(grid) != key(first):
            votes[key(grid)] += 1
    if not votes:
        return None
    top = max(votes.values())
    winners = [grid for grid, count in votes.items() if count == top]
    return [list(row) for row in winners[0]] if len(winners) == 1 else None


def load_runtime():
    for name in tuple(sys.modules):
        if name == "接続" or name.startswith("接続."):
            del sys.modules[name]
    sys.path.insert(0, str(ROOT))
    sys.path.insert(1, str(HDS_DIR))
    importlib.invalidate_caches()
    return importlib.import_module("接続.ARC2.HDS接続")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-examples", type=int, default=3)
    parser.add_argument("--max-folds", type=int)
    parser.add_argument("--budget-seconds", type=float, default=1800)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")
    if args.min_examples < 3 or args.budget_seconds <= 0:
        raise SystemExit("min-examples must be >=3 and budget must be positive")

    files = sorted(TRAINING.glob("*.json"))
    manifest = hashlib.sha256()
    loaded = []
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        loaded.append((path, json.loads(raw)))
    runtime = load_runtime()
    prior = runtime.事前教材を読む()
    template = json.loads((ROOT / "接続/ARC2/テンプレート充填教材.json").read_text(encoding="utf-8"))
    prior_sources = {item["課題ID"] for item in template["教材"]}

    folds = eligible = candidate_folds = unique_candidate_folds = ambiguous_folds = 0
    candidate_any_exact = candidate_first_exact = candidate_consensus_exact = 0
    baseline_calls = baseline_exact = baseline_fallback = baseline_second_exact = 0
    paired_before_exact = paired_after_exact = regressions = gains = 0
    gated_calls = gated_admitted = gated_rejected = 0
    gated_before_exact = gated_after_exact = gated_gains = gated_regressions = 0
    gated_states = Counter()
    candidate_models_total = candidate_distinct_total = 0
    by_teacher_count = {}
    started = time.perf_counter()
    stop = False
    for path, task in loaded:
        task_id = path.stem
        examples = task.get("train", [])
        if task_id in prior_sources or len(examples) < args.min_examples:
            continue
        eligible += 1
        for heldout_index, heldout in enumerate(examples):
            if args.max_folds is not None and folds >= args.max_folds:
                stop = True
                break
            if time.perf_counter() - started >= args.budget_seconds:
                stop = True
                break
            teachers = [pair for index, pair in enumerate(examples) if index != heldout_index]
            models, pool, simplest, simplest_model = predict_pool(
                teachers,
                heldout["input"],
            )
            folds += 1
            candidate_models_total += len(models)
            candidate_distinct_total += len(pool)
            stats = by_teacher_count.setdefault(str(len(teachers)), {"folds": 0, "candidate_folds": 0, "unique_folds": 0, "ambiguous_folds": 0, "candidate_any_exact": 0, "consensus_exact": 0, "paired_gains": 0, "paired_regressions": 0})
            stats["folds"] += 1
            target_key = key(heldout["output"])
            candidate_any_exact += int(target_key in pool)
            stats["candidate_any_exact"] += int(target_key in pool)
            if pool:
                candidate_folds += 1
                stats["candidate_folds"] += 1
                candidate_first_exact += int(valid_grid(simplest) and key(simplest) == target_key)
            if len(pool) == 1:
                unique_candidate_folds += 1
                stats["unique_folds"] += 1
                consensus = next(iter(pool))
                is_consensus_exact = consensus == target_key
                candidate_consensus_exact += int(is_consensus_exact)
                stats["consensus_exact"] += int(is_consensus_exact)
                gated_calls += 1
                is_admitted, gate_state = hds_admits(
                    runtime, simplest_model, teachers, prior
                )
                gated_states[gate_state] += 1
                gated_admitted += int(is_admitted)
                gated_rejected += int(not is_admitted)
                baseline_calls += 1
                result = runtime.課題を解く({"train": teachers, "test": [{"input": heldout["input"]}]}, prior, 候補収集=True)
                row = result.get("results", [{}])[0]
                answer = row.get("answer")
                first_valid = valid_grid(answer)
                baseline_fallback += int(not first_valid)
                baseline_exact += int(first_valid and key(answer) == target_key)
                first_for_adapter = answer if first_valid else heldout["input"]
                old_second = unique_second(row.get("candidate_predictions"), first_for_adapter)
                baseline_second_exact += int(old_second is not None and key(old_second) == target_key)
                before = first_valid and key(answer) == target_key or old_second is not None and key(old_second) == target_key
                gated_before_exact += int(before)
                gated_after = before
                if is_admitted:
                    candidate_key = key(apply_model(simplest_model, heldout["input"]))
                    gated_after = gated_after or candidate_key == target_key
                gated_after_exact += int(gated_after)
                gated_gains += int(gated_after and not before)
                gated_regressions += int(before and not gated_after)
                if first_valid:
                    new_second = old_second if old_second is not None else (next(iter(pool)) if next(iter(pool)) != key(answer) else None)
                    after = key(answer) == target_key or new_second is not None and new_second == target_key
                else:
                    new_first = next(iter(pool))
                    new_second = old_second if old_second is not None and key(old_second) != new_first else None
                    after = new_first == target_key or new_second is not None and new_second == target_key
                paired_before_exact += int(before)
                paired_after_exact += int(after)
                gains += int(after and not before)
                regressions += int(before and not after)
                stats["paired_gains"] += int(after and not before)
                stats["paired_regressions"] += int(before and not after)
            else:
                ambiguous_folds += int(len(pool) > 1)
                stats["ambiguous_folds"] += int(len(pool) > 1)
            if folds % 100 == 0:
                print(json.dumps({"folds_done": folds, "candidate_folds": candidate_folds, "paired_hds_calls": baseline_calls, "elapsed_seconds": round(time.perf_counter() - started, 1)}), flush=True)
        if stop:
            break

    complete = not stop
    source_hashes = {
        "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "simple_transform_candidate": hashlib.sha256(
            (ROOT / "接続/ARC2/単純変換候補.py").read_bytes()
        ).hexdigest(),
        "hds_connector": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
        "submission_adapter": hashlib.sha256((ROOT / "接続/ARC2/Kaggle提出.py").read_bytes()).hexdigest(),
    }
    result = {
        "schema": "arc2-v5-simple-transform-program-loo.v3",
        "experiment_id": "ARC26-ARC2-V5-P5-SIMPLE-TRANSFORM-PROGRAM-LOO-CURRENT-TEACHERS",
        "data_source": "public ARC-AGI-2 training split only",
        "evaluation_solutions_read_by_parent_only": True,
        "heldout_output_passed_to_solver": False,
        "task_identifiers_or_grids_saved": False,
        "fallback_counted_correct": False,
        "min_source_task_examples": args.min_examples,
        "eligible_tasks": eligible,
        "loo_folds": folds,
        "complete": complete,
        "stop_reason": "budget_or_fold_limit" if stop else "all_eligible_folds",
        "budget_seconds": args.budget_seconds,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "training_manifest_sha256": manifest.hexdigest(),
        "prior_examples_loaded_in_paired_hds_calls": len(prior),
        "prior_source_tasks_excluded": len(prior_sources),
        "candidate_programs_fit_on_current_task_teachers_only": True,
        "candidate_programs": ["D4 orientation", "color map", "crop background", "integer scale", "uniform downscale", "tile"],
        "candidate_folds": candidate_folds,
        "unique_candidate_folds": unique_candidate_folds,
        "ambiguous_candidate_folds": ambiguous_folds,
        "candidate_models_total": candidate_models_total,
        "distinct_candidate_predictions_total": candidate_distinct_total,
        "candidate_any_model_exact_upper_bound": candidate_any_exact,
        "simplest_model_exact": candidate_first_exact,
        "unique_consensus_exact": candidate_consensus_exact,
        "paired_hds_calls": baseline_calls,
        "paired_hds_first_exact": baseline_exact,
        "paired_hds_first_fallback": baseline_fallback,
        "paired_hds_second_exact": baseline_second_exact,
        "paired_before_exact_union": paired_before_exact,
        "paired_after_exact_union": paired_after_exact,
        "paired_delta_exact": paired_after_exact - paired_before_exact,
        "paired_gains": gains,
        "paired_regressions": regressions,
        "hds_gate_calls": gated_calls,
        "hds_gate_admitted": gated_admitted,
        "hds_gate_rejected": gated_rejected,
        "hds_gate_states": dict(gated_states),
        "hds_gated_before_exact_union": gated_before_exact,
        "hds_gated_after_exact_union": gated_after_exact,
        "hds_gated_delta_exact": gated_after_exact - gated_before_exact,
        "hds_gated_gains": gated_gains,
        "hds_gated_regressions": gated_regressions,
        "by_teacher_example_count": by_teacher_count,
        "source_sha256": source_hashes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
