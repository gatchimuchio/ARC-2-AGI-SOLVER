"""Pilot output-equivalence acceptance for ambiguous edge-guided D4 transforms."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[3]
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
HDS_DIR = ROOT / "HDS/学習系統/v0.4.2"
BASELINE_REPORT = ROOT / "運用/証拠/ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json"
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


def load_solver(overlay: Path | None = None):
    for name in tuple(sys.modules):
        if name == "接続" or name.startswith("接続."):
            del sys.modules[name]
    if overlay is None:
        sys.path.insert(0, str(ROOT))
    else:
        sys.path.insert(0, str(overlay))
    sys.path.insert(1, str(HDS_DIR))
    importlib.invalidate_caches()
    module = importlib.import_module("接続.ARC2.HDS接続")
    return module.課題を解く


def install_edge_output_equivalence(temporary_root: Path):
    overlay = temporary_root / "overlay"
    (overlay / "接続").mkdir(parents=True)
    init_source = ROOT / "接続/__init__.py"
    if init_source.is_file():
        shutil.copy2(init_source, overlay / "接続/__init__.py")
    else:
        (overlay / "接続/__init__.py").write_text("", encoding="utf-8")
    shutil.copytree(
        ROOT / "接続/ARC2",
        overlay / "接続/ARC2",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    target = overlay / "接続/ARC2/既存辺対応抽出.py"
    source = target.read_text(encoding="utf-8")
    original = (
        '    if len(matching_transforms) != 1:\n'
        '        return None, {\n'
        '            "failure": "ambiguous_edge_payload_transform",\n'
        '            "side_constraints": constraints,\n'
        '            "matching_transforms": matching_transforms,\n'
        '            "side_records": side_records,\n'
        '        }\n'
        '    return matching_transforms[0], {\n'
        '        "side_constraints": constraints,\n'
        '        "side_records": side_records,\n'
        '    }\n'
    )
    candidate = (
        '    if not matching_transforms:\n'
        '        return None, {\n'
        '            "failure": "no_edge_payload_transform_matches_guides",\n'
        '            "side_constraints": constraints,\n'
        '            "matching_transforms": matching_transforms,\n'
        '            "side_records": side_records,\n'
        '        }\n'
        '    output_equivalent = False\n'
        '    if len(matching_transforms) > 1:\n'
        '        min_row, min_col, max_row, max_col = bbox\n'
        '        crop = [row[min_col:max_col] for row in grid[min_row:max_row]]\n'
        '        rendered = [transform_grid_by_name(crop, name) for name in matching_transforms]\n'
        '        unique_outputs = {tuple(tuple(row) for row in output) for output in rendered if output is not None}\n'
        '        if len(unique_outputs) != 1 or len(rendered) != len(matching_transforms):\n'
        '            return None, {\n'
        '                "failure": "ambiguous_edge_payload_transform",\n'
        '                "side_constraints": constraints,\n'
        '                "matching_transforms": matching_transforms,\n'
        '                "side_records": side_records,\n'
        '            }\n'
        '        output_equivalent = True\n'
        '    return matching_transforms[0], {\n'
        '        "side_constraints": constraints,\n'
        '        "side_records": side_records,\n'
        '        "matching_transform_count": len(matching_transforms),\n'
        '        "all_matching_transforms_render_same_grid": output_equivalent,\n'
        '    }\n'
    )
    if source.count(original) != 1:
        raise RuntimeError("expected exactly one edge-transform ambiguity gate")
    source = source.replace(original, candidate, 1)
    target.write_text(source, encoding="utf-8", newline="\n")
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return overlay, digest


def score_call(solve, teachers, heldout):
    result = solve(
        {"train": teachers, "test": [{"input": heldout["input"]}]},
        [],
    )
    row = result.get("results", [{}])[0]
    answer = row.get("answer")
    valid = valid_grid(answer)
    exact = bool(valid and answer == heldout["output"])
    return {
        "answer": int(valid),
        "exact": int(exact),
        "wrong": int(valid and not exact),
        "fallback": int(not valid),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-tasks", type=int, default=4)
    parser.add_argument("--budget-seconds", type=float, default=300.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("P5_HDS_edge_transform_output_equivalence_LOO_pilot.json"),
    )
    args = parser.parse_args()
    if not 1 <= args.pilot_tasks <= 4:
        raise SystemExit("--pilot-tasks must be between 1 and 4")
    if args.budget_seconds <= 0:
        raise SystemExit("--budget-seconds must be positive")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    baseline = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    files = sorted(TRAINING_DIR.glob("*.json"))
    eligible = []
    manifest = hashlib.sha256()
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) >= SUPPORT_MINIMUM + 1:
            eligible.append((raw, examples))
    if manifest.hexdigest() != baseline["training_manifest_sha256"]:
        raise RuntimeError("public training manifest differs from the baseline")
    if len(eligible) != baseline["eligible_tasks"]:
        raise RuntimeError("eligible public training population differs from the baseline")

    started = time.perf_counter()
    previous = Counter()
    current = Counter()
    previous_runtime = 0.0
    current_runtime = 0.0
    folds = tasks_done = 0
    time_cap_reached = False
    temporary_directory = tempfile.TemporaryDirectory(prefix="arc2-p5-edge-output-equivalence-")
    try:
        baseline_solve = load_solver()
        overlay, variant_sha = install_edge_output_equivalence(Path(temporary_directory.name))
        candidate_solve = load_solver(overlay)
        for raw, examples in eligible:
            if tasks_done >= args.pilot_tasks:
                break
            for index, heldout in enumerate(examples):
                if time.perf_counter() - started >= args.budget_seconds:
                    time_cap_reached = True
                    break
                teachers = [pair for i, pair in enumerate(examples) if i != index]
                call_started = time.perf_counter()
                previous.update(score_call(baseline_solve, teachers, heldout))
                previous_runtime += time.perf_counter() - call_started
                call_started = time.perf_counter()
                current.update(score_call(candidate_solve, teachers, heldout))
                current_runtime += time.perf_counter() - call_started
                folds += 1
            if time_cap_reached:
                break
            tasks_done += 1
            print(
                json.dumps(
                    {
                        "eligible_tasks_done": tasks_done,
                        "loo_folds_done": folds,
                        "elapsed_seconds": round(time.perf_counter() - started, 1),
                    },
                    sort_keys=True,
                ),
                flush=True,
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
        result = {
            "schema": "arc2-p5-hds-edge-transform-output-equivalence-loo.v1",
            "experiment_id": "ARC2-C2-064-EDGE_TRANSFORM_OUTPUT_EQUIVALENCE",
            "run_type": "pilot",
            "data_source": "public ARC-AGI-2 training split only",
            "eligible_task_population": len(eligible),
            "pilot_task_limit": args.pilot_tasks,
            "eligible_tasks_evaluated": tasks_done,
            "loo_folds": folds,
            "time_cap_reached": time_cap_reached,
            "runtime_budget_seconds": args.budget_seconds,
            "training_manifest_sha256": manifest.hexdigest(),
            "baseline_hds_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
            "baseline_edge_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/既存辺対応抽出.py").read_bytes()).hexdigest(),
            "candidate_temporary_edge_sha256": variant_sha,
            "metrics_previous_current": {
                "previous_unique_transform_name": previous_metrics,
                "current_equivalent_output_acceptance": current_metrics,
            },
            "delta_current_minus_previous": delta,
            "runtime_seconds": {
                "previous_unique_transform_name": round(previous_runtime, 3),
                "current_equivalent_output_acceptance": round(current_runtime, 3),
                "delta_current_minus_previous": round(current_runtime - previous_runtime, 3),
                "combined_wall_seconds": round(time.perf_counter() - started, 3),
            },
            "fallback_counted_correct": False,
            "heldout_output_passed_to_solver": False,
            "heldout_output_scored_only_after_solver_return": True,
            "evaluation_solutions_read": False,
            "task_identifiers_or_grids_saved": False,
            "production_or_submission_changed": False,
            "official_submission_or_rerun": False,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    finally:
        temporary_directory.cleanup()


if __name__ == "__main__":
    main()
