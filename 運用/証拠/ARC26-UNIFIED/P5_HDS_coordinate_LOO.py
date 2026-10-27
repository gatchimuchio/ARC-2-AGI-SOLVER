"""C2-051 public-training LOO for generic HDS coordinate-conditioned observations.

The candidate learns input-cell-color and zero-based cell-coordinate relations
to output color. The parent evaluator alone reads held-out outputs after solver
return.
Only aggregate metrics are written; no task IDs, grids, or fold rows are saved.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
BASE_SCRIPT = ROOT / "運用/証拠/ARC26-UNIFIED/P5_prior_memory_leakage_guard_LOO.py"
BASE_EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED/P5_prior_memory_leakage_guard_LOO.json"


def load_base_module():
    spec = importlib.util.spec_from_file_location("p5_c2_045_baseline", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the audited C2-045 evaluator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def training_manifest(files: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        raw = path.read_bytes()
        digest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
    return digest.hexdigest()


def hds_source_manifest(root: Path) -> str:
    folder = root / "HDS/学習系統/v0.4.2/hds学習系統"
    digest = hashlib.sha256()
    for path in sorted(folder.rglob("*.py")):
        digest.update(path.relative_to(folder).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def valid_grid(grid):
    return (
        isinstance(grid, list)
        and 1 <= len(grid) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(grid[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in grid
        )
    )


def same_shape(a, b):
    return valid_grid(a) and valid_grid(b) and len(a) == len(b) and len(a[0]) == len(b[0])


def local_features(grid, row, col):
    return grid[row][col], row, col


def local_input(learning_input_type, observation_type, features, output_color=None):
    center, row_index, column_index = features
    observations = [
        observation_type(("center_color",), center, "color"),
        observation_type(("row_index",), row_index, "count"),
        observation_type(("column_index",), column_index, "count"),
    ]
    if output_color is not None:
        observations.append(observation_type(("output_color",), output_color, "color"))
    raw = (center, row_index, column_index, output_color)
    return learning_input_type(
        原入力=raw,
        対象系境界="ARC2_local_cell_rule",
        観測群=tuple(observations),
    )


def hds_local_candidate(training_pairs, test_grid, engine_type, input_type, observation_type, diagnostics):
    if not valid_grid(test_grid):
        diagnostics["invalid_test_grid"] += 1
        return None
    if not training_pairs or any(not same_shape(pair.get("input"), pair.get("output")) for pair in training_pairs):
        diagnostics["shape_precondition_failed"] += 1
        return None

    engine = engine_type(最小支持数=3, 最大条件数=2)
    for pair in training_pairs:
        per_teacher_pairs = set()
        grid_in, grid_out = pair["input"], pair["output"]
        for row in range(len(grid_in)):
            for col in range(len(grid_in[0])):
                features = local_features(grid_in, row, col)
                per_teacher_pairs.add((features, grid_out[row][col]))
        # A repeated local pattern within one teacher grid is one support unit.
        for features, output_color in sorted(per_teacher_pairs, key=repr):
            engine.実行(local_input(input_type, observation_type, features, output_color))
            diagnostics["training_relation_records"] += 1

    predicted_grid = []
    for row in range(len(test_grid)):
        predicted_row = []
        for col in range(len(test_grid[0])):
            result = engine.照会(local_input(input_type, observation_type, local_features(test_grid, row, col)))
            diagnostics["cell_queries"] += 1
            values = [
                prediction.予測値
                for prediction in result.予測群
                if prediction.結果経路 == ("output_color",)
            ]
            requests = [
                request for request in result.追加観測要求群
                if request.結果経路 == ("output_color",)
            ]
            if requests:
                diagnostics["cells_with_additional_observation_request"] += 1
                return None
            if result.係争中原理群:
                diagnostics["cells_with_quarantined_principles"] += 1
                return None
            if result.競合群:
                diagnostics["cells_with_conflicting_predictions"] += 1
                return None
            if not values:
                diagnostics["cells_without_prediction"] += 1
                return None
            unique = {value for value in values}
            if len(unique) != 1:
                diagnostics["cells_with_disagreeing_values"] += 1
                return None
            color = next(iter(unique))
            if type(color) is not int or not 0 <= color <= 9:
                diagnostics["cells_with_invalid_output_color"] += 1
                return None
            predicted_row.append(color)
        predicted_grid.append(predicted_row)
    if not valid_grid(predicted_grid):
        diagnostics["invalid_candidate_grid"] += 1
        return None
    diagnostics["complete_candidate_grids"] += 1
    return predicted_grid


def run(pilot_tasks: int):
    base = load_base_module()
    baseline = json.loads(BASE_EVIDENCE.read_text(encoding="utf-8"))
    connector = base.connector
    connector_sha = sha256(ROOT / "接続/ARC2/HDS接続.py")
    if connector_sha != baseline["connector_sha256"]:
        raise RuntimeError("Connector differs from the C2-045 matched baseline")

    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    from hds学習系統.実行系 import HDS学習実行系
    from hds学習系統.型 import 学習入力, 観測事実

    reference = json.loads(base.REFERENCE_PATH.read_text(encoding="utf-8"))
    if reference.get("分割") != "training":
        raise RuntimeError("Approved prior memory is not training-only")
    source_ids = {item["課題ID"] for item in reference.get("教材", [])}
    prior = connector.事前教材を読む()
    if len(prior) != 2 or any(set(pair) != {"input", "output"} for pair in prior):
        raise RuntimeError("Approved prior memory shape changed")
    prior_inputs = {base.grid_key(pair["input"]) for pair in prior}

    files = sorted(base.TRAINING_DIR.glob("*.json"))
    data_manifest = training_manifest(files)
    if data_manifest != baseline["training_manifest_sha256"]:
        raise RuntimeError("Public training manifest differs from C2-045")
    eligible = []
    source_exclusions = overlap_exclusions = 0
    for path in files:
        task = json.loads(path.read_text(encoding="utf-8"))
        examples = task.get("train", [])
        if len(examples) < base.MIN_TEACHERS + 1:
            continue
        if path.stem in source_ids:
            source_exclusions += 1
            continue
        if any(base.grid_key(pair["input"]) in prior_inputs for pair in examples):
            overlap_exclusions += 1
            continue
        eligible.append(path)
    if (len(eligible) != baseline["eligible_task_count"]
            or source_exclusions != baseline["prior_source_task_count_excluded"]
            or overlap_exclusions != baseline["additional_input_overlap_task_count_excluded"]):
        raise RuntimeError("Leakage-guarded population differs from C2-045")
    if pilot_tasks < 0 or (pilot_tasks and pilot_tasks > len(eligible)):
        raise ValueError("Invalid pilot task count")
    selected = eligible[:pilot_tasks] if pilot_tasks else eligible

    metrics = {
        "baseline": Counter(),
        "candidate": Counter(),
    }
    diagnostics = Counter()
    baseline_seconds = candidate_seconds = 0.0
    folds = 0
    started = time.perf_counter()
    for task_index, path in enumerate(selected, start=1):
        task = json.loads(path.read_text(encoding="utf-8"))
        examples = task["train"]
        for heldout_index, heldout in enumerate(examples):
            teachers = [pair for i, pair in enumerate(examples) if i != heldout_index]
            solver_task = {"train": deepcopy(teachers), "test": [{"input": deepcopy(heldout["input"])}]}
            if set(solver_task["test"][0]) != {"input"}:
                raise RuntimeError("Held-out output crossed the solver boundary")

            t0 = time.perf_counter()
            baseline_result = connector.課題を解く(deepcopy(solver_task), [], 候補収集=True)
            baseline_seconds += time.perf_counter() - t0
            base_row = baseline_result.get("results", [{}])[0]
            base_answer = base_row.get("answer")
            base_has_answer = valid_grid(base_answer)
            first = base_answer if base_has_answer else heldout["input"]
            first_exact = base_has_answer and base_answer == heldout["output"]
            base_second = base.select_alternative(base_row.get("candidate_predictions", []), first)
            base_second_distinct = base_second is not None
            base_second_exact = base_second_distinct and base_second == heldout["output"]
            metrics["baseline"].update({
                "answer": int(base_has_answer),
                "fallback": int(not base_has_answer),
                "first_exact": int(first_exact),
                "first_wrong": int(base_has_answer and not first_exact),
                "distinct_second": int(base_second_distinct),
                "second_exact": int(base_second_exact),
                "second_wrong": int(base_second_distinct and not base_second_exact),
                "union_exact": int(first_exact or base_second_exact),
            })

            t0 = time.perf_counter()
            local_answer = hds_local_candidate(
                teachers, heldout["input"], HDS学習実行系, 学習入力, 観測事実, diagnostics
            )
            candidate_seconds += time.perf_counter() - t0
            local_distinct = local_answer is not None and local_answer != first
            local_exact = local_distinct and local_answer == heldout["output"]
            metrics["candidate"].update({
                "distinct_second": int(local_distinct),
                "second_exact": int(local_exact),
                "second_wrong": int(local_distinct and not local_exact),
                "union_exact": int(first_exact or local_exact),
                "fallback": int(local_answer is None),
            })
            folds += 1

        if task_index % (1 if pilot_tasks else 10) == 0 or task_index == len(selected):
            print(json.dumps({
                "eligible_tasks_done": task_index,
                "loo_folds_done": folds,
                "elapsed_seconds": round(time.perf_counter() - started, 1),
                "candidate_second_exact": int(metrics["candidate"]["second_exact"]),
                "complete_candidate_grids": int(diagnostics["complete_candidate_grids"]),
            }), flush=True)

    full = not pilot_tasks
    if full and folds != baseline["loo_fold_count"]:
        raise RuntimeError("Full LOO fold count differs from C2-045")
    metric_fields = ("answer", "fallback", "first_exact", "first_wrong", "distinct_second", "second_exact", "second_wrong", "union_exact")
    baseline_metrics = {k: int(metrics["baseline"][k]) for k in metric_fields if k in metrics["baseline"]}
    candidate_metrics = {k: int(metrics["candidate"][k]) for k in ("fallback", "distinct_second", "second_exact", "second_wrong", "union_exact")}
    previous_metrics = baseline["metrics_previous_current"]["previous_no_prior"]
    baseline_matches_prior = None
    if full:
        baseline_matches_prior = all(baseline_metrics[k] == int(previous_metrics[k]) for k in metric_fields)
        if not baseline_matches_prior:
            raise RuntimeError("Remeasured baseline differs from C2-045 previous_no_prior")
    delta = {
        "distinct_second": candidate_metrics["distinct_second"] - int(baseline_metrics.get("distinct_second", previous_metrics["distinct_second"])),
        "second_exact": candidate_metrics["second_exact"] - int(baseline_metrics.get("second_exact", previous_metrics["second_exact"])),
        "second_wrong": candidate_metrics["second_wrong"] - int(baseline_metrics.get("second_wrong", previous_metrics["second_wrong"])),
        "union_exact": candidate_metrics["union_exact"] - int(baseline_metrics.get("union_exact", previous_metrics["union_exact"])),
        "fallback": candidate_metrics["fallback"] - int(baseline_metrics.get("fallback", previous_metrics["fallback"])),
    }
    completed = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    evidence = {
        "schema": "arc2-hds-coordinate-loo.v1",
        "experiment_id": "ARC2-C2-051-HDS_COORDINATE_RULE",
        "run_type": "pilot" if pilot_tasks else "full",
        "completed_at_utc": completed,
        "data_source": "public ARC-AGI-2 training split only",
        "feature_definition": "input cell color + zero-based row and column indices",
        "support_rule": "HDS min_support=3, max_conditions=2; deduplicate identical feature/output pairs within each teacher grid",
        "training_manifest_sha256": data_manifest,
        "connector_sha256": connector_sha,
        "hds_source_manifest_sha256": hds_source_manifest(ROOT),
        "baseline_evidence_sha256": sha256(BASE_EVIDENCE),
        "eligible_task_population": len(eligible),
        "eligible_tasks_evaluated": len(selected),
        "loo_folds_evaluated": folds,
        "baseline_expected_folds": baseline["loo_fold_count"],
        "source_task_exclusions": source_exclusions,
        "prior_input_overlap_task_exclusions": overlap_exclusions,
        "baseline_condition": "C2-045 previous_no_prior; HDS connector unchanged",
        "baseline_metrics_remeasured": baseline_metrics,
        "baseline_matches_c2_045": baseline_matches_prior,
        "candidate_metrics": candidate_metrics,
        "candidate_minus_baseline": delta,
        "candidate_diagnostics_aggregate": {k: int(v) for k, v in diagnostics.items()},
        "baseline_solver_runtime_seconds": round(baseline_seconds, 3),
        "candidate_solver_runtime_seconds": round(candidate_seconds, 3),
        "combined_wall_runtime_seconds": round(time.perf_counter() - started, 3),
        "fallback_counted_correct": False,
        "heldout_output_passed_to_solver": False,
        "heldout_output_scored_after_solver_return": True,
        "hidden_or_evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "production_or_submission_changed": False,
    }
    suffix = "pilot" if pilot_tasks else "full"
    output = Path(__file__).with_name(f"P5_HDS_coordinate_LOO_{suffix}.json")
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    output.write_text(json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": output.relative_to(ROOT).as_posix(),
        "run_type": evidence["run_type"],
        "eligible_tasks": evidence["eligible_tasks_evaluated"],
        "loo_folds": folds,
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "delta": delta,
        "candidate_diagnostics": evidence["candidate_diagnostics_aggregate"],
        "baseline_matches_c2_045": baseline_matches_prior,
        "combined_wall_runtime_seconds": evidence["combined_wall_runtime_seconds"],
    }, ensure_ascii=False), flush=True)
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-tasks", type=int, default=0)
    args = parser.parse_args()
    run(args.pilot_tasks)


if __name__ == "__main__":
    main()
