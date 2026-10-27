"""Matched full public-training LOO for the isolated HDS non-veto policy."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE_REPORT = ROOT / "運用/証拠/ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json"
BASE_RUNNER_PATH = ROOT / "運用/証拠/ARC26-UNIFIED/P5_HDS_edge_transform_output_equivalence_LOO.py"
OVERLAY = ROOT / "運用/証拠/ARC26-UNIFIED/C2-067-full-policy-overlay"
OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/P5_HDS_consensus_unresolved_nonveto_full_LOO.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_base_runner():
    spec = importlib.util.spec_from_file_location(
        "arc2_c2067_hds_nonveto_full_runner", BASE_RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the full LOO helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def prepare_overlay():
    if OVERLAY.exists():
        raise FileExistsError(f"refusing to overwrite {OVERLAY}")
    shutil.copytree(
        ROOT / "接続",
        OVERLAY / "接続",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    connector_path = OVERLAY / "接続/ARC2/HDS接続.py"
    source = connector_path.read_bytes()
    anchor = "        elif 未解決理由:".encode("utf-8")
    replacement = "        elif 未解決理由 and not 予測群:".encode("utf-8")
    if source.count(anchor) != 1:
        raise RuntimeError("HDS arbitration patch anchor is not unique")
    source = source.replace(anchor, replacement)
    connector_path.write_bytes(source)
    return sha256(source)


def metrics_for(answer, target, valid_grid):
    valid = valid_grid(answer)
    exact = bool(valid and answer == target)
    return {
        "answer": int(valid),
        "exact": int(exact),
        "wrong": int(valid and not exact),
        "fallback": int(not valid),
        "union_exact": int(exact),
    }


def run_solver(solve, task):
    try:
        result = solve(task, [])
        row = (result or {}).get("results", [{}])[0]
        answer = row.get("answer")
        return answer, row, result or {}, False
    except Exception:
        return None, {}, {}, True


def main():
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    for path in (BASELINE_REPORT, BASE_RUNNER_PATH):
        if not path.is_file():
            raise FileNotFoundError(path)

    started = time.perf_counter()
    base = load_base_runner()
    baseline_spec = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    original_hds_sha = sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes())
    manifest = hashlib.sha256()
    files = sorted(TRAINING_DIR.glob("*.json"))
    eligible = []
    fold_count = 0
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) >= base.SUPPORT_MINIMUM + 1:
            eligible.append(examples)
            fold_count += len(examples)
    if manifest.hexdigest() != baseline_spec.get("training_manifest_sha256"):
        raise RuntimeError("public training manifest differs from the baseline")
    if len(eligible) != baseline_spec.get("eligible_tasks") or fold_count != 1191:
        raise RuntimeError("eligible public-training population differs from baseline")

    overlay_sha = prepare_overlay()
    baseline_solve = base.load_solver()
    current_solve = base.load_solver(OVERLAY)
    previous = Counter()
    current = Counter()
    status_counts = Counter()
    reason_counts = Counter()
    previous_exceptions = 0
    current_exceptions = 0
    regressions = 0
    newly_answered = 0
    newly_exact = 0
    previous_seconds = 0.0
    current_seconds = 0.0
    evaluated = 0

    for examples in eligible:
        for heldout_index, heldout in enumerate(examples):
            teachers = [
                pair for index, pair in enumerate(examples)
                if index != heldout_index
            ]
            task = {"train": teachers, "test": [{"input": heldout["input"]}]}

            call_started = time.perf_counter()
            old_answer, _old_row, _old_result, old_error = run_solver(
                baseline_solve, task
            )
            previous_seconds += time.perf_counter() - call_started
            previous_exceptions += int(old_error)

            call_started = time.perf_counter()
            new_answer, new_row, new_result, new_error = run_solver(
                current_solve, task
            )
            current_seconds += time.perf_counter() - call_started
            current_exceptions += int(new_error)

            # Held-out output is read only after both solvers have returned.
            target = heldout["output"]
            old_metrics = metrics_for(old_answer, target, base.valid_grid)
            new_metrics = metrics_for(new_answer, target, base.valid_grid)
            previous.update(old_metrics)
            current.update(new_metrics)
            regressions += int(old_metrics["exact"] and not new_metrics["exact"])
            newly_answered += int(new_metrics["answer"] and not old_metrics["answer"])
            newly_exact += int(new_metrics["exact"] and not old_metrics["exact"])
            status_counts[str(new_row.get(
                "status", "answered" if new_answer is not None else "unknown"
            ))] += 1
            for reason in new_row.get("reasons", []):
                reason_counts[str(reason)] += 1
            if isinstance(new_result.get("results"), list) and len(new_result["results"]) != 1:
                raise RuntimeError("solver returned an unexpected result count")
            evaluated += 1

    if evaluated != fold_count:
        raise RuntimeError("full LOO did not evaluate every eligible public fold")

    previous_metrics = {
        key: int(previous[key])
        for key in ("answer", "exact", "wrong", "fallback", "union_exact")
    }
    current_metrics = {
        key: int(current[key])
        for key in ("answer", "exact", "wrong", "fallback", "union_exact")
    }
    delta = {key: current_metrics[key] - previous_metrics[key] for key in previous_metrics}
    result = {
        "run_type": "matched_full_public_training_LOO_HDS_unresolved_family_nonveto",
        "eligible_task_count": len(eligible),
        "eligible_fold_count": fold_count,
        "evaluated_fold_count": evaluated,
        "training_manifest_sha256": manifest.hexdigest(),
        "previous_hds_first_answer": previous_metrics,
        "current_hds_nonveto_policy": current_metrics,
        "delta_current_minus_previous": delta,
        "regressions_previous_exact_to_current_not_exact": regressions,
        "newly_answered": newly_answered,
        "newly_exact": newly_exact,
        "solver_exceptions": {
            "previous": previous_exceptions,
            "current": current_exceptions,
        },
        "previous_solver_runtime_seconds": round(previous_seconds, 3),
        "current_solver_runtime_seconds": round(current_seconds, 3),
        "current_status_counts": dict(status_counts),
        "current_hold_reason_counts": dict(reason_counts),
        "base_hds_source_sha256": original_hds_sha,
        "policy_overlay_hds_source_sha256": overlay_sha,
        "baseline_report_sha256": sha256(BASELINE_REPORT.read_bytes()),
        "all_previous_and_current_folds_matched": True,
        "heldout_output_passed_to_either_solver": False,
        "heldout_output_scored_after_both_solvers_return": True,
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "fallback_counted_correct": False,
        "production_or_notebook_changed": False,
        "official_submission_or_rerun": False,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
