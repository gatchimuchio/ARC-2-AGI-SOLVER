"""Input-stratified public LOO pilot for equivalent ambiguous edge transforms."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[3]
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE_REPORT = (
    ROOT
    / "運用/証拠/ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json"
)
BASE_RUNNER_PATH = (
    ROOT
    / "運用/証拠/ARC26-UNIFIED/P5_HDS_edge_transform_output_equivalence_LOO.py"
)


def load_base_runner():
    spec = importlib.util.spec_from_file_location(
        "arc2_p5_edge_equivalence_base", BASE_RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the C2-064 isolated runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def solver_request(solve, teachers, heldout_input):
    """Return a solver result without reading the held-out public output."""
    try:
        result = solve(
            {"train": teachers, "test": [{"input": heldout_input}]},
            [],
        )
    except Exception:
        return None, True
    return result, False


def score_returned_result(result, heldout_output, valid_grid):
    row = (result or {}).get("results", [{}])[0]
    answer = row.get("answer")
    valid = valid_grid(answer)
    exact = bool(valid and answer == heldout_output)
    return {
        "answer": int(valid),
        "exact": int(exact),
        "wrong": int(valid and not exact),
        "fallback": int(not valid),
    }


def merge_metrics(target, values):
    for key, value in values.items():
        target[key] += value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--budget-seconds", type=float, default=300.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name(
            "P5_HDS_edge_transform_output_equivalence_targeted.json"
        ),
    )
    args = parser.parse_args()
    if args.budget_seconds <= 0:
        raise SystemExit("--budget-seconds must be positive")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    base = load_base_runner()
    baseline_spec = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))

    files = sorted(TRAINING_DIR.glob("*.json"))
    manifest = hashlib.sha256()
    eligible = []
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) >= base.SUPPORT_MINIMUM + 1:
            eligible.append(examples)
    if manifest.hexdigest() != baseline_spec["training_manifest_sha256"]:
        raise RuntimeError("public training manifest differs from the baseline")
    if len(eligible) != baseline_spec["eligible_tasks"]:
        raise RuntimeError("eligible public training population differs from the baseline")

    started = time.perf_counter()
    previous = Counter()
    current = Counter()
    strata = {
        "equivalent_rendered_payloads": {
            "previous": Counter(),
            "current": Counter(),
            "folds": 0,
        },
        "different_or_invalid_rendered_payloads": {
            "previous": Counter(),
            "current": Counter(),
            "folds": 0,
        },
    }
    selected_tasks = 0
    selected_folds = 0
    ambiguity_count = Counter()
    previous_runtime = 0.0
    current_runtime = 0.0
    previous_exceptions = 0
    current_exceptions = 0
    time_cap_reached = False

    baseline_solve = base.load_solver()
    edge = importlib.import_module("接続.ARC2.既存辺対応抽出")
    grid_ops = importlib.import_module("接続.ARC2.既存格子操作")
    with tempfile.TemporaryDirectory(prefix="arc2-p5-c2-065-") as temporary_root:
        overlay, candidate_edge_sha = base.install_edge_output_equivalence(
            Path(temporary_root)
        )
        candidate_solve = base.load_solver(overlay)

        for examples in eligible:
            task_selected = False
            for index, heldout in enumerate(examples):
                heldout_input = heldout["input"]
                bbox = edge.infer_payload_color_bbox(heldout_input)
                if bbox is None:
                    continue
                _, detail = edge.infer_edge_guided_payload_transform(
                    heldout_input, bbox
                )
                if detail.get("failure") != "ambiguous_edge_payload_transform":
                    continue
                names = detail.get("matching_transforms", [])
                if len(names) != 2:
                    continue

                r0, c0, r1, c1 = bbox
                crop = [row[c0:c1] for row in heldout_input[r0:r1]]
                rendered = [
                    grid_ops.transform_grid_by_name(crop, name) for name in names
                ]
                unique_outputs = {
                    tuple(tuple(row) for row in output)
                    for output in rendered
                    if output is not None
                }
                if len(unique_outputs) == 1 and len(rendered) == len(names):
                    stratum = "equivalent_rendered_payloads"
                else:
                    stratum = "different_or_invalid_rendered_payloads"

                if time.perf_counter() - started >= args.budget_seconds:
                    time_cap_reached = True
                    break

                teachers = [
                    pair for teacher_index, pair in enumerate(examples)
                    if teacher_index != index
                ]
                call_started = time.perf_counter()
                previous_result, previous_error = solver_request(
                    baseline_solve, teachers, heldout_input
                )
                previous_runtime += time.perf_counter() - call_started
                call_started = time.perf_counter()
                current_result, current_error = solver_request(
                    candidate_solve, teachers, heldout_input
                )
                current_runtime += time.perf_counter() - call_started

                # The public held-out output is first read here, after both solvers return.
                heldout_output = heldout["output"]
                previous_values = score_returned_result(
                    previous_result, heldout_output, base.valid_grid
                )
                current_values = score_returned_result(
                    current_result, heldout_output, base.valid_grid
                )
                merge_metrics(previous, previous_values)
                merge_metrics(current, current_values)
                merge_metrics(strata[stratum]["previous"], previous_values)
                merge_metrics(strata[stratum]["current"], current_values)
                strata[stratum]["folds"] += 1
                ambiguity_count[str(len(names))] += 1
                previous_exceptions += int(previous_error)
                current_exceptions += int(current_error)
                selected_folds += 1
                task_selected = True
            if task_selected:
                selected_tasks += 1
            if time_cap_reached:
                break

    expected = {
        "equivalent_rendered_payloads": 3,
        "different_or_invalid_rendered_payloads": 3,
    }
    observed = {name: row["folds"] for name, row in strata.items()}
    if not time_cap_reached and observed != expected:
        raise RuntimeError(
            f"input-only ambiguity cohort changed: observed={observed}"
        )

    fields = ("answer", "exact", "wrong", "fallback")
    previous_metrics = {name: int(previous[name]) for name in fields}
    current_metrics = {name: int(current[name]) for name in fields}
    previous_metrics["union_exact"] = previous_metrics["exact"]
    current_metrics["union_exact"] = current_metrics["exact"]
    delta = {
        name: current_metrics[name] - previous_metrics[name]
        for name in (*fields, "union_exact")
    }
    strata_results = {}
    for name, row in strata.items():
        before = {field: int(row["previous"][field]) for field in fields}
        after = {field: int(row["current"][field]) for field in fields}
        before["union_exact"] = before["exact"]
        after["union_exact"] = after["exact"]
        strata_results[name] = {
            "folds": row["folds"],
            "previous": before,
            "current": after,
            "delta": {
                key: after[key] - before[key]
                for key in (*fields, "union_exact")
            },
        }

    result = {
        "schema": "arc2-p5-hds-edge-transform-equivalence-targeted-loo.v1",
        "experiment_id": "ARC2-C2-065-EDGE_TRANSFORM_AMBIGUITY_STRATIFIED_LOO",
        "run_type": "hypothesis_targeted_pilot",
        "data_source": "public ARC-AGI-2 training split only",
        "eligible_task_population": len(eligible),
        "eligible_fold_population": int(baseline_spec["loo_folds"]),
        "selection_rule": (
            "held-out input alone reports exactly two matching D4 edge transforms"
        ),
        "input_only_ambiguity_strata": observed,
        "ambiguous_matching_transform_count_histogram": dict(ambiguity_count),
        "selected_unique_tasks": selected_tasks,
        "selected_folds": selected_folds,
        "time_cap_reached": time_cap_reached,
        "runtime_budget_seconds": args.budget_seconds,
        "training_manifest_sha256": manifest.hexdigest(),
        "baseline_hds_source_sha256": hashlib.sha256(
            (ROOT / "接続/ARC2/HDS接続.py").read_bytes()
        ).hexdigest(),
        "baseline_edge_source_sha256": hashlib.sha256(
            (ROOT / "接続/ARC2/既存辺対応抽出.py").read_bytes()
        ).hexdigest(),
        "candidate_temporary_edge_sha256": candidate_edge_sha,
        "metrics_previous_current": {
            "previous_unique_transform_name": previous_metrics,
            "current_equivalent_output_acceptance": current_metrics,
        },
        "delta_current_minus_previous": delta,
        "strata": strata_results,
        "runtime_seconds": {
            "previous_unique_transform_name": round(previous_runtime, 3),
            "current_equivalent_output_acceptance": round(current_runtime, 3),
            "delta_current_minus_previous": round(
                current_runtime - previous_runtime, 3
            ),
            "combined_wall_seconds": round(time.perf_counter() - started, 3),
        },
        "solver_exceptions": {
            "previous": previous_exceptions,
            "current": current_exceptions,
        },
        "public_heldout_output_scored_after_both_solvers_return": True,
        "heldout_output_passed_to_solver": False,
        "fallback_counted_correct": False,
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "production_or_submission_changed": False,
        "official_submission_or_rerun": False,
    }
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
