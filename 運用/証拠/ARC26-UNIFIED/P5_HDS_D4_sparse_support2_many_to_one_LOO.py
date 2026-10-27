"""Pilot sparse D4 support two combined with a deterministic many-to-one palette."""

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
SPARSE_TRAIN_PAIR_COUNT = 3
EXPECTED_POPULATION = 575


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
    sys.path.insert(0, str(ROOT if overlay is None else overlay))
    sys.path.insert(1, str(HDS_DIR))
    importlib.invalidate_caches()
    module = importlib.import_module("接続.ARC2.HDS接続")
    return module.課題を解く


def install_sparse_d4_candidate(temporary_root: Path):
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
    target = overlay / "接続/ARC2/格子D4教材.py"
    source = target.read_text(encoding="utf-8")
    support_original = "        self.必要支持数 = 3\n"
    support_candidate = "        self.必要支持数 = 2 if isinstance(教師群, (list, tuple)) and len(教師群) == 2 else 3\n"
    reverse_check = (
        "            if 出力色 in 逆向き and 逆向き[出力色] != 入力色:\n"
        "                return False\n"
    )
    reverse_assignment = "            逆向き[出力色] = 入力色\n"
    if source.count(support_original) != 1:
        raise RuntimeError("expected exactly one D4-family support threshold")
    if source.count(reverse_check) != 1 or source.count(reverse_assignment) != 1:
        raise RuntimeError("expected exactly one reverse-palette uniqueness guard")
    source = source.replace(support_original, support_candidate, 1)
    source = source.replace(reverse_check, "", 1)
    source = source.replace(reverse_assignment, "", 1)
    target.write_text(source, encoding="utf-8", newline="\n")
    return overlay, hashlib.sha256(source.encode("utf-8")).hexdigest()


def score_call(solve, teachers, heldout):
    result = solve(
        {"train": teachers, "test": [{"input": heldout["input"]}]},
        [],
    )
    answer = result.get("results", [{}])[0].get("answer")
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
        default=Path(__file__).with_name("P5_HDS_D4_sparse_support2_many_to_one_LOO_pilot.json"),
    )
    args = parser.parse_args()
    if not 1 <= args.pilot_tasks <= 4:
        raise SystemExit("--pilot-tasks must be between 1 and 4")
    if args.budget_seconds <= 0:
        raise SystemExit("--budget-seconds must be positive")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite {args.output}")

    files = sorted(TRAINING_DIR.glob("*.json"))
    manifest = hashlib.sha256()
    eligible = []
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) == SPARSE_TRAIN_PAIR_COUNT:
            eligible.append((raw, examples))
    if len(eligible) != EXPECTED_POPULATION:
        raise RuntimeError(f"sparse task population changed: expected {EXPECTED_POPULATION}, got {len(eligible)}")

    started = time.perf_counter()
    previous = Counter()
    current = Counter()
    previous_runtime = current_runtime = 0.0
    folds = tasks_done = 0
    time_cap_reached = False
    temporary_directory = tempfile.TemporaryDirectory(prefix="arc2-p5-d4-sparse-merged-")
    try:
        previous_solve = load_solver()
        overlay, candidate_sha = install_sparse_d4_candidate(Path(temporary_directory.name))
        current_solve = load_solver(overlay)
        for _, examples in eligible:
            if tasks_done >= args.pilot_tasks:
                break
            for index, heldout in enumerate(examples):
                if time.perf_counter() - started >= args.budget_seconds:
                    time_cap_reached = True
                    break
                teachers = [pair for i, pair in enumerate(examples) if i != index]
                call_started = time.perf_counter()
                previous.update(score_call(previous_solve, teachers, heldout))
                previous_runtime += time.perf_counter() - call_started
                call_started = time.perf_counter()
                current.update(score_call(current_solve, teachers, heldout))
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
            "schema": "arc2-p5-hds-d4-sparse-support2-many-to-one-loo.v1",
            "experiment_id": "ARC2-C2-063-D4_SPARSE_SUPPORT_TWO_MANY_TO_ONE",
            "run_type": "pilot",
            "data_source": "public ARC-AGI-2 training split only",
            "sparse_task_training_pair_count": SPARSE_TRAIN_PAIR_COUNT,
            "eligible_task_population": len(eligible),
            "pilot_task_limit": args.pilot_tasks,
            "eligible_tasks_evaluated": tasks_done,
            "loo_folds": folds,
            "time_cap_reached": time_cap_reached,
            "runtime_budget_seconds": args.budget_seconds,
            "training_manifest_sha256": manifest.hexdigest(),
            "baseline_d4_source_sha256": hashlib.sha256((ROOT / "接続/ARC2/格子D4教材.py").read_bytes()).hexdigest(),
            "candidate_temporary_d4_sha256": candidate_sha,
            "metrics_previous_current": {
                "previous_current_connector": previous_metrics,
                "current_sparse_two_teacher_many_to_one": current_metrics,
            },
            "delta_current_minus_previous": delta,
            "runtime_seconds": {
                "previous_current_connector": round(previous_runtime, 3),
                "current_sparse_two_teacher_many_to_one": round(current_runtime, 3),
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
