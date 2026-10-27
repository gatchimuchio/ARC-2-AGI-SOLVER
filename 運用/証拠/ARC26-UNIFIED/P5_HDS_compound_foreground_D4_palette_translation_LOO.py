"""Public-training pilot for a compound rigid foreground transform family."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import random
import sys
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
TRANSFORMS = (
    "identity",
    "rot90",
    "rot180",
    "rot270",
    "flip_h",
    "flip_v",
    "transpose",
    "anti_transpose",
)


def load_base_runner():
    spec = importlib.util.spec_from_file_location(
        "arc2_p5_compound_foreground_base", BASE_RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the public LOO baseline helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def background_and_bbox(grid):
    counts = Counter(value for row in grid for value in row)
    if not counts:
        return None, None
    maximum = max(counts.values())
    modes = [value for value, count in counts.items() if count == maximum]
    if len(modes) != 1:
        return None, None
    background = modes[0]
    cells = [
        (row, col)
        for row, values in enumerate(grid)
        for col, value in enumerate(values)
        if value != background
    ]
    if not cells:
        return background, None
    return background, (
        min(row for row, _ in cells),
        min(col for _, col in cells),
        max(row for row, _ in cells) + 1,
        max(col for _, col in cells) + 1,
    )


def pair_programs(pair, transform_grid_by_name):
    source = pair.get("input")
    target = pair.get("output")
    if not source or not target or len(source) != len(target):
        return set()
    if any(len(row) != len(source[0]) for row in source + target):
        return set()

    source_bg, source_bbox = background_and_bbox(source)
    target_bg, target_bbox = background_and_bbox(target)
    if source_bbox is None or target_bbox is None:
        return set()
    sr0, sc0, sr1, sc1 = source_bbox
    tr0, tc0, tr1, tc1 = target_bbox
    source_crop = [row[sc0:sc1] for row in source[sr0:sr1]]
    target_crop = [row[tc0:tc1] for row in target[tr0:tr1]]
    programs = set()

    for transform in TRANSFORMS:
        rendered = transform_grid_by_name(source_crop, transform)
        if (
            rendered is None
            or len(rendered) != len(target_crop)
            or any(len(row) != len(target_crop[0]) for row in rendered)
        ):
            continue
        mapping = {source_bg: target_bg}
        reverse = {target_bg: source_bg}
        valid = True
        for source_row, target_row in zip(rendered, target_crop):
            for source_color, target_color in zip(source_row, target_row):
                if source_color == source_bg:
                    if target_color != target_bg:
                        valid = False
                        break
                    continue
                if target_color == target_bg:
                    valid = False
                    break
                if (
                    source_color in mapping
                    and mapping[source_color] != target_color
                ) or (
                    target_color in reverse
                    and reverse[target_color] != source_color
                ):
                    valid = False
                    break
                mapping[source_color] = target_color
                reverse[target_color] = source_color
            if not valid:
                break
        if not valid:
            continue
        programs.add(
            (
                transform,
                tr0 - sr0,
                tc0 - sc0,
                tuple(sorted(mapping.items())),
            )
        )
    return programs


def merge_programs(left, right):
    if left[:3] != right[:3]:
        return None
    mapping = dict(left[3])
    reverse = {target: source for source, target in mapping.items()}
    for source, target in right[3]:
        if source in mapping and mapping[source] != target:
            return None
        if target in reverse and reverse[target] != source:
            return None
        mapping[source] = target
        reverse[target] = source
    return left[:3] + (tuple(sorted(mapping.items())),)


def fit_programs(teachers, transform_grid_by_name):
    states = None
    for pair in teachers:
        candidates = pair_programs(pair, transform_grid_by_name)
        if not candidates:
            return set()
        if states is None:
            states = candidates
            continue
        merged = set()
        for state in states:
            for candidate in candidates:
                result = merge_programs(state, candidate)
                if result is not None:
                    merged.add(result)
        if not merged:
            return set()
        states = merged
    return states or set()


def apply_program(grid, program, transform_grid_by_name):
    transform, delta_row, delta_col, mapping_items = program
    mapping = dict(mapping_items)
    source_bg, bbox = background_and_bbox(grid)
    if bbox is None or source_bg not in mapping:
        return None
    r0, c0, r1, c1 = bbox
    crop = [row[c0:c1] for row in grid[r0:r1]]
    rendered = transform_grid_by_name(crop, transform)
    if rendered is None:
        return None
    target_bg = mapping[source_bg]
    height = len(grid)
    width = len(grid[0])
    out_r0 = r0 + delta_row
    out_c0 = c0 + delta_col
    if (
        out_r0 < 0
        or out_c0 < 0
        or out_r0 + len(rendered) > height
        or out_c0 + len(rendered[0]) > width
    ):
        return None
    output = [[target_bg for _ in range(width)] for _ in range(height)]
    for row_index, row in enumerate(rendered):
        for col_index, color in enumerate(row):
            if color == source_bg:
                mapped = target_bg
            elif color in mapping and mapping[color] != target_bg:
                mapped = mapping[color]
            else:
                return None
            output[out_r0 + row_index][out_c0 + col_index] = mapped
    return output


def candidate_output(grid, programs, transform_grid_by_name, valid_grid):
    outputs = []
    for program in programs:
        output = apply_program(grid, program, transform_grid_by_name)
        if output is None or not valid_grid(output):
            return None
        outputs.append(tuple(tuple(row) for row in output))
    unique = set(outputs)
    if len(unique) != 1:
        return None
    return [list(row) for row in next(iter(unique))]


def reservoir_add(reservoir, group, seen, limit, rng):
    if len(reservoir) < limit:
        reservoir.append(group)
    else:
        index = rng.randrange(seen + 1)
        if index < limit:
            reservoir[index] = group


def baseline_request(solve, teachers, heldout_input):
    try:
        result = solve(
            {"train": teachers, "test": [{"input": heldout_input}]},
            [],
        )
    except Exception:
        return None, True
    row = (result or {}).get("results", [{}])[0]
    return row.get("answer"), False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-tasks", type=int, default=12)
    parser.add_argument("--budget-seconds", type=float, default=300.0)
    parser.add_argument(
        "--full-loo",
        action="store_true",
        help="evaluate every candidate-applicable fold after the positive pilot",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name(
            "P5_HDS_compound_foreground_D4_palette_translation_pilot.json"
        ),
    )
    args = parser.parse_args()
    if args.sample_tasks < 1 or args.budget_seconds <= 0:
        raise SystemExit("sample size and time budget must be positive")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    base = load_base_runner()
    baseline_spec = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    files = sorted(TRAINING_DIR.glob("*.json"))
    manifest = hashlib.sha256()
    eligible_tasks = 0
    teacher_fit_folds = 0
    applicable_folds = 0
    applicable_tasks = 0
    reservoir = []
    full_loo_task_cases = []
    rng = None
    transform_grid_by_name = None
    started = time.perf_counter()

    # First build a manifest and confirm it matches the previous/current baseline.
    raw_by_task = []
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) >= base.SUPPORT_MINIMUM + 1:
            raw_by_task.append(examples)
    if manifest.hexdigest() != baseline_spec["training_manifest_sha256"]:
        raise RuntimeError("public training manifest differs from the baseline")
    if len(raw_by_task) != baseline_spec["eligible_tasks"]:
        raise RuntimeError("eligible public training population differs from the baseline")

    rng = random.Random(int(manifest.hexdigest()[:16], 16))
    base_solve = base.load_solver()
    grid_ops = importlib.import_module("接続.ARC2.既存格子操作")
    transform_grid_by_name = grid_ops.transform_grid_by_name

    for examples in raw_by_task:
        eligible_tasks += 1
        task_cases = []
        for heldout_index, heldout in enumerate(examples):
            teachers = [
                pair for index, pair in enumerate(examples)
                if index != heldout_index
            ]
            programs = fit_programs(teachers, transform_grid_by_name)
            if not programs:
                continue
            teacher_fit_folds += 1
            prediction = candidate_output(
                heldout["input"], programs, transform_grid_by_name, base.valid_grid
            )
            if prediction is None:
                continue
            applicable_folds += 1
            task_cases.append((examples, heldout_index, programs, prediction))
        if task_cases:
            applicable_tasks += 1
            if args.full_loo:
                full_loo_task_cases.append(task_cases)
            else:
                reservoir_add(
                    reservoir,
                    task_cases,
                    applicable_tasks - 1,
                    args.sample_tasks,
                    rng,
                )

    pre_screen_seconds = time.perf_counter() - started
    if not reservoir and not full_loo_task_cases:
        result = {
            "schema": "arc2-p5-hds-compound-foreground-d4-palette-translation-loo.v1",
            "experiment_id": "ARC2-C2-066-COMPOUND_FOREGROUND_D4_PALETTE_TRANSLATION",
            "run_type": "hypothesis_targeted_pilot",
            "data_source": "public ARC-AGI-2 training split only",
            "eligible_task_population": eligible_tasks,
            "eligible_fold_population": int(baseline_spec["loo_folds"]),
            "teacher_fit_folds": teacher_fit_folds,
            "candidate_applicable_folds": applicable_folds,
            "candidate_applicable_tasks": applicable_tasks,
            "selected_tasks": 0,
            "selected_folds": 0,
            "no_candidate_applicability": True,
            "pre_screen_seconds": round(pre_screen_seconds, 3),
            "training_manifest_sha256": manifest.hexdigest(),
            "evaluation_solutions_read": False,
            "task_identifiers_or_grids_saved": False,
            "production_or_submission_changed": False,
            "official_submission_or_rerun": False,
        }
        args.output.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(result, sort_keys=True))
        return

    baseline = Counter()
    current = Counter()
    candidate_only = Counter()
    baseline_runtime = 0.0
    candidate_runtime = 0.0
    baseline_exceptions = 0
    regressions = 0
    sampled_folds = 0
    newly_answered_count = 0
    newly_exact_count = 0
    sample_started = time.perf_counter()
    time_cap_reached = False

    selected_cases = []
    if args.full_loo:
        for task_cases in full_loo_task_cases:
            selected_cases.extend(task_cases)
    else:
        for task_cases in reservoir:
            selected_cases.append(rng.choice(task_cases))
    for examples, heldout_index, programs, prediction in selected_cases:
        if time.perf_counter() - sample_started >= args.budget_seconds:
            time_cap_reached = True
            break
        heldout = examples[heldout_index]
        teachers = [
            pair for index, pair in enumerate(examples)
            if index != heldout_index
        ]
        call_started = time.perf_counter()
        baseline_answer, baseline_error = baseline_request(
            base_solve, teachers, heldout["input"]
        )
        baseline_exceptions += int(baseline_error)
        baseline_runtime += time.perf_counter() - call_started
        call_started = time.perf_counter()
        candidate_answer = candidate_output(
            heldout["input"], programs, transform_grid_by_name, base.valid_grid
        )
        candidate_runtime += time.perf_counter() - call_started

        # Read the public held-out target only after both candidate generators return.
        target = heldout["output"]
        baseline_valid = base.valid_grid(baseline_answer)
        baseline_exact = bool(baseline_valid and baseline_answer == target)
        candidate_valid = base.valid_grid(candidate_answer)
        candidate_exact = bool(candidate_valid and candidate_answer == target)
        current_exact = baseline_exact or candidate_exact
        regressions += int(baseline_exact and not current_exact)
        newly_answered_count += int(candidate_valid and not baseline_valid)
        newly_exact_count += int(candidate_exact and not baseline_exact)

        baseline["answer"] += int(baseline_valid)
        baseline["exact"] += int(baseline_exact)
        baseline["wrong"] += int(baseline_valid and not baseline_exact)
        baseline["fallback"] += int(not baseline_valid)
        current["answer"] += int(baseline_valid or candidate_valid)
        current["exact"] += int(current_exact)
        current["wrong"] += int((baseline_valid or candidate_valid) and not current_exact)
        current["fallback"] += int(not (baseline_valid or candidate_valid))
        candidate_only["answer"] += int(candidate_valid)
        candidate_only["exact"] += int(candidate_exact)
        candidate_only["wrong"] += int(candidate_valid and not candidate_exact)
        candidate_only["fallback"] += int(not candidate_valid)
        sampled_folds += 1

    fields = ("answer", "exact", "wrong", "fallback")
    previous_metrics = {name: int(baseline[name]) for name in fields}
    current_metrics = {name: int(current[name]) for name in fields}
    candidate_metrics = {name: int(candidate_only[name]) for name in fields}
    previous_metrics["union_exact"] = previous_metrics["exact"]
    current_metrics["union_exact"] = current_metrics["exact"]
    candidate_metrics["union_exact"] = candidate_metrics["exact"]
    matched_delta = {
        name: current_metrics[name] - previous_metrics[name]
        for name in (*fields, "union_exact")
    }

    full_cohort_metrics = None
    full_cohort_delta = None
    if args.full_loo and not time_cap_reached:
        baseline_answers = int(baseline_spec["hds_first_answer_rows"])
        baseline_exact = int(baseline_spec["hds_first_guess_exact"])
        baseline_fallback = int(baseline_spec["loo_folds"]) - baseline_answers
        baseline_wrong = baseline_answers - baseline_exact
        affected_baseline_exact = int(baseline["exact"])
        # Only affected folds can change; baseline aggregate covers all other folds.
        full_previous = {
            "answer": baseline_answers,
            "exact": baseline_exact,
            "wrong": baseline_wrong,
            "fallback": baseline_fallback,
            "union_exact": baseline_exact,
        }
        full_current = {
            "answer": baseline_answers + newly_answered_count,
            "exact": baseline_exact + newly_exact_count,
            "wrong": baseline_wrong + int(candidate_only["wrong"]),
            "fallback": baseline_fallback - newly_answered_count,
        }
        full_current["union_exact"] = full_current["exact"]
        full_cohort_metrics = {
            "previous_hds_first_answer": full_previous,
            "current_hds_plus_compound_candidate_union": full_current,
            "candidate_only_on_affected_folds": candidate_metrics,
            "matched_affected_folds": {
                "folds": sampled_folds,
                "previous": {**previous_metrics},
                "current": {**current_metrics},
            },
            "baseline_source_report": str(BASELINE_REPORT.relative_to(ROOT)),
            "baseline_source_elapsed_seconds": baseline_spec["elapsed_seconds"],
            "baseline_affected_fold_exact_count": affected_baseline_exact,
            "candidate_new_answer_count_on_affected_folds": newly_answered_count,
            "candidate_new_exact_count_on_affected_folds": newly_exact_count,
        }
        full_cohort_delta = {
            name: full_current[name] - full_previous[name]
            for name in (*fields, "union_exact")
        }
    delta = full_cohort_delta if full_cohort_delta is not None else matched_delta
    result = {
        "schema": "arc2-p5-hds-compound-foreground-d4-palette-translation-loo.v1",
        "experiment_id": "ARC2-C2-066-COMPOUND_FOREGROUND_D4_PALETTE_TRANSLATION",
        "run_type": "full_matched_loo" if args.full_loo else "hypothesis_targeted_pilot",
        "data_source": "public ARC-AGI-2 training split only",
        "eligible_task_population": eligible_tasks,
        "eligible_fold_population": int(baseline_spec["loo_folds"]),
        "teacher_fit_folds": teacher_fit_folds,
        "candidate_applicable_folds": applicable_folds,
        "candidate_applicable_tasks": applicable_tasks,
        "selected_tasks": applicable_tasks if args.full_loo else len(reservoir),
        "selected_folds": sampled_folds,
        "full_loo_requested": args.full_loo,
        "full_loo_complete": bool(
            args.full_loo and not time_cap_reached and sampled_folds == applicable_folds
        ),
        "sample_tasks_limit": args.sample_tasks,
        "sample_seed_from_manifest": True,
        "pre_screen_seconds": round(pre_screen_seconds, 3),
        "pilot_seconds": round(time.perf_counter() - sample_started, 3),
        "time_cap_reached": time_cap_reached,
        "training_manifest_sha256": manifest.hexdigest(),
        "baseline_hds_source_sha256": hashlib.sha256(
            (ROOT / "接続/ARC2/HDS接続.py").read_bytes()
        ).hexdigest(),
        "baseline_report_sha256": hashlib.sha256(
            BASELINE_REPORT.read_bytes()
        ).hexdigest(),
        "metrics_previous_current": {
            "previous_hds_first_answer": previous_metrics,
            "current_hds_plus_compound_candidate_union": current_metrics,
            "compound_candidate_only": candidate_metrics,
        },
        "full_cohort_previous_current": full_cohort_metrics,
        "affected_fold_delta_current_minus_previous": matched_delta,
        "delta_current_minus_previous": delta,
        "regressions_previous_exact_to_current_not_exact": regressions,
        "solver_exceptions": {"baseline": baseline_exceptions},
        "baseline_solver_runtime_seconds": round(baseline_runtime, 3),
        "candidate_prediction_runtime_seconds": round(candidate_runtime, 3),
        "combined_wall_seconds": round(time.perf_counter() - started, 3),
        "heldout_output_passed_to_solver": False,
        "public_heldout_output_scored_after_both_generators_return": True,
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
