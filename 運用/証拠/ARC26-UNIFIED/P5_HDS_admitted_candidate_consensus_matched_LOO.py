"""Matched C2-068 candidate-consensus LOO against the C2-067 policy baseline."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE_REPORT = ROOT / "運用/証拠/ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json"
POLICY_REPORT = ROOT / "運用/証拠/ARC26-UNIFIED/P5_HDS_consensus_unresolved_nonveto_full_LOO.json"
CANDIDATE_PILOT_REPORT = ROOT / "運用/証拠/ARC26-UNIFIED/C2-068-targeted-C2-066-admitted-consensus-LOO.json"
BASE_RUNNER_PATH = ROOT / "運用/証拠/ARC26-UNIFIED/P5_HDS_edge_transform_output_equivalence_LOO.py"
POLICY_OVERLAY = ROOT / "運用/証拠/ARC26-UNIFIED/C2-067-full-policy-overlay"
CANDIDATE_OVERLAY = ROOT / "運用/証拠/ARC26-UNIFIED/C2-068-admitted-candidate-consensus-overlay"
FAMILY_SOURCE = ROOT / "運用/証拠/ARC26-UNIFIED/C2-066_compound_foreground_D4_palette_translation.py"
TARGET_OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/C2-068-matched-targeted-LOO.json"
FULL_OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/C2-068-matched-full-LOO.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_helper():
    spec = importlib.util.spec_from_file_location(
        "arc2_c2068_admitted_candidate_consensus_matched_loo", BASE_RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the matched LOO helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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
        result = solve(task, []) or {}
        row = (result.get("results") or [{}])[0]
        return row.get("answer"), False
    except Exception:
        return None, True


def main():
    for output in (TARGET_OUTPUT, FULL_OUTPUT):
        if output.exists():
            raise FileExistsError(f"refusing to overwrite {output}")
    for path in (
        BASELINE_REPORT, POLICY_REPORT, CANDIDATE_PILOT_REPORT,
        BASE_RUNNER_PATH, FAMILY_SOURCE,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    started = time.perf_counter()
    helper = load_helper()
    baseline = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    policy = json.loads(POLICY_REPORT.read_text(encoding="utf-8"))
    pilot = json.loads(CANDIDATE_PILOT_REPORT.read_text(encoding="utf-8"))
    policy_hds = POLICY_OVERLAY / "接続/ARC2/HDS接続.py"
    candidate_hds = CANDIDATE_OVERLAY / "接続/ARC2/HDS接続.py"
    candidate_family = CANDIDATE_OVERLAY / "接続/ARC2/C2_066_compound_foreground_D4_palette_translation.py"
    if not policy_hds.is_file() or not candidate_hds.is_file() or not candidate_family.is_file():
        raise FileNotFoundError("one of the frozen experiment overlays is missing")

    policy_hds_sha = sha256(policy_hds.read_bytes())
    candidate_hds_sha = sha256(candidate_hds.read_bytes())
    family_sha = sha256(candidate_family.read_bytes())
    root_hds_sha = sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes())
    if policy_hds_sha != policy["policy_overlay_hds_source_sha256"]:
        raise RuntimeError("C2-067 policy overlay changed after its full LOO")
    if candidate_hds_sha != pilot["overlay_hds_source_sha256"]:
        raise RuntimeError("C2-068 candidate overlay changed after its targeted run")
    if family_sha != pilot["candidate_family_source_sha256"]:
        raise RuntimeError("C2-066 family source differs from the targeted run")
    if root_hds_sha != policy["base_hds_source_sha256"] or root_hds_sha != pilot["base_hds_source_sha256"]:
        raise RuntimeError("the compared overlays do not share the recorded base HDS source")
    if not policy["all_previous_and_current_folds_matched"]:
        raise RuntimeError("C2-067 full LOO is not a complete matched baseline")
    if policy["delta_current_minus_previous"] != {
        "answer": 0, "exact": 0, "fallback": 0, "union_exact": 0, "wrong": 0
    }:
        raise RuntimeError("C2-067 policy baseline changed aggregate LOO metrics")

    manifest = hashlib.sha256()
    eligible = []
    fold_count = 0
    files = sorted(TRAINING_DIR.glob("*.json"))
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) >= helper.SUPPORT_MINIMUM + 1:
            eligible.append(examples)
            fold_count += len(examples)
    if manifest.hexdigest() != baseline["training_manifest_sha256"]:
        raise RuntimeError("public training manifest differs from the established baseline")
    if manifest.hexdigest() != policy["training_manifest_sha256"]:
        raise RuntimeError("C2-067 used a different public-training manifest")
    if len(eligible) != 267 or fold_count != 1191:
        raise RuntimeError("eligible public-training population differs from the fixed cohort")

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    candidate_solve = helper.load_solver(CANDIDATE_OVERLAY)
    family_module = importlib.import_module(
        "接続.ARC2.C2_066_compound_foreground_D4_palette_translation"
    )
    family_class = family_module.CompoundForegroundD4PaletteTranslation
    policy_solve = helper.load_solver(POLICY_OVERLAY)

    target_cases = []
    family_fit_count = 0
    candidate_applicable_count = 0
    for examples in eligible:
        for heldout_index, heldout in enumerate(examples):
            teachers = [pair for index, pair in enumerate(examples) if index != heldout_index]
            family = family_class(teachers)
            if not family._programs:
                continue
            family_fit_count += 1
            candidate, _ = family.候補(heldout["input"], {})
            applicable = candidate is not None and helper.valid_grid(candidate)
            candidate_applicable_count += int(applicable)
            target_cases.append((teachers, heldout, candidate, applicable))
    if family_fit_count != 4 or candidate_applicable_count != 3 or len(target_cases) != 4:
        raise RuntimeError("C2-066 family fit/applicability scan differs from its recorded audit")

    target_previous = Counter()
    target_current = Counter()
    target_previous_exceptions = 0
    target_current_exceptions = 0
    target_regressions = 0
    candidate_base_absent = 0
    candidate_added_answers = 0
    candidate_added_exact = 0
    candidate_added_wrong = 0
    for teachers, heldout, candidate, applicable in target_cases:
        task = {"train": teachers, "test": [{"input": heldout["input"]}]}
        previous_answer, previous_error = run_solver(policy_solve, task)
        current_answer, current_error = run_solver(candidate_solve, task)
        target_previous_exceptions += int(previous_error)
        target_current_exceptions += int(current_error)
        target = heldout["output"]
        old = metrics_for(previous_answer, target, helper.valid_grid)
        new = metrics_for(current_answer, target, helper.valid_grid)
        target_previous.update(old)
        target_current.update(new)
        target_regressions += int(old["exact"] and not new["exact"])
        if applicable and previous_answer is None:
            candidate_base_absent += 1
        contributes = bool(
            applicable and previous_answer is None and current_answer == candidate
        )
        candidate_added_answers += int(contributes)
        candidate_added_exact += int(contributes and new["exact"])
        candidate_added_wrong += int(contributes and new["wrong"])

    metric_keys = ("answer", "exact", "wrong", "fallback", "union_exact")
    target_previous_metrics = {key: int(target_previous[key]) for key in metric_keys}
    target_current_metrics = {key: int(target_current[key]) for key in metric_keys}
    target_delta = {
        key: target_current_metrics[key] - target_previous_metrics[key]
        for key in metric_keys
    }
    target_pass = bool(
        target_delta["exact"] > 0
        and target_regressions == 0
        and target_delta["wrong"] <= 0
        and target_previous_exceptions == 0
        and target_current_exceptions == 0
    )
    policy_metrics = policy["current_hds_nonveto_policy"]
    targeted_result = {
        "run_type": "matched_targeted_public_training_LOO_C2-068_vs_C2-067_policy",
        "status": "TARGETED_GATE_PASS_FULL_LOO_STARTED" if target_pass else "REJECTED_TARGETED_GATE",
        "eligible_task_count": len(eligible),
        "eligible_fold_count": fold_count,
        "family_teacher_fit_fold_count": family_fit_count,
        "candidate_input_applicable_fold_count": candidate_applicable_count,
        "targeted_folds_evaluated": len(target_cases),
        "baseline_c2_067_policy": target_previous_metrics,
        "candidate_c2_068_consensus": target_current_metrics,
        "delta_current_minus_baseline": target_delta,
        "regressions_baseline_exact_to_candidate_not_exact": target_regressions,
        "candidate_base_answer_absent_applicable_count": candidate_base_absent,
        "candidate_added_answer_count": candidate_added_answers,
        "candidate_added_exact_count": candidate_added_exact,
        "candidate_added_wrong_count": candidate_added_wrong,
        "solver_exceptions": {
            "baseline": target_previous_exceptions,
            "candidate": target_current_exceptions,
        },
        "training_manifest_sha256": manifest.hexdigest(),
        "baseline_policy_overlay_hds_source_sha256": policy_hds_sha,
        "candidate_overlay_hds_source_sha256": candidate_hds_sha,
        "candidate_family_source_sha256": family_sha,
        "root_hds_source_sha256": root_hds_sha,
        "policy_full_loo_report_sha256": sha256(POLICY_REPORT.read_bytes()),
        "original_targeted_report_sha256": sha256(CANDIDATE_PILOT_REPORT.read_bytes()),
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "heldout_output_passed_to_either_solver": False,
        "heldout_output_scored_after_both_solvers_return": True,
        "fallback_counted_correct": False,
        "production_or_notebook_changed": False,
        "official_submission_or_rerun": False,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    TARGET_OUTPUT.write_text(json.dumps(targeted_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(targeted_result, sort_keys=True), flush=True)
    if not target_pass:
        return

    previous = Counter()
    current = Counter()
    previous_exceptions = 0
    current_exceptions = 0
    regressions = 0
    newly_answered = 0
    newly_exact = 0
    previous_seconds = 0.0
    current_seconds = 0.0
    evaluated = 0
    full_started = time.perf_counter()
    for examples in eligible:
        for heldout_index, heldout in enumerate(examples):
            teachers = [pair for index, pair in enumerate(examples) if index != heldout_index]
            task = {"train": teachers, "test": [{"input": heldout["input"]}]}
            call_started = time.perf_counter()
            previous_answer, previous_error = run_solver(policy_solve, task)
            previous_seconds += time.perf_counter() - call_started
            previous_exceptions += int(previous_error)
            call_started = time.perf_counter()
            current_answer, current_error = run_solver(candidate_solve, task)
            current_seconds += time.perf_counter() - call_started
            current_exceptions += int(current_error)
            target = heldout["output"]
            old = metrics_for(previous_answer, target, helper.valid_grid)
            new = metrics_for(current_answer, target, helper.valid_grid)
            previous.update(old)
            current.update(new)
            regressions += int(old["exact"] and not new["exact"])
            newly_answered += int(new["answer"] and not old["answer"])
            newly_exact += int(new["exact"] and not old["exact"])
            evaluated += 1
    if evaluated != fold_count:
        raise RuntimeError("full matched LOO did not evaluate every eligible public fold")

    previous_metrics = {key: int(previous[key]) for key in metric_keys}
    current_metrics = {key: int(current[key]) for key in metric_keys}
    delta = {key: current_metrics[key] - previous_metrics[key] for key in metric_keys}
    full_gate = bool(
        delta["exact"] > 0
        and regressions == 0
        and delta["wrong"] <= 0
        and previous_exceptions == 0
        and current_exceptions == 0
    )
    full_result = {
        "run_type": "matched_full_public_training_LOO_C2-068_vs_C2-067_policy",
        "status": "FULL_GATE_PASS_PENDING_SEPARATE_PROMOTION_REVIEW" if full_gate else "REJECTED_FULL_LOO",
        "eligible_task_count": len(eligible),
        "eligible_fold_count": fold_count,
        "evaluated_fold_count": evaluated,
        "training_manifest_sha256": manifest.hexdigest(),
        "baseline_c2_067_policy": previous_metrics,
        "candidate_c2_068_consensus": current_metrics,
        "delta_current_minus_baseline": delta,
        "regressions_baseline_exact_to_candidate_not_exact": regressions,
        "newly_answered": newly_answered,
        "newly_exact": newly_exact,
        "solver_exceptions": {
            "baseline": previous_exceptions,
            "candidate": current_exceptions,
        },
        "baseline_solver_runtime_seconds": round(previous_seconds, 3),
        "candidate_solver_runtime_seconds": round(current_seconds, 3),
        "family_teacher_fit_fold_count": family_fit_count,
        "candidate_input_applicable_fold_count": candidate_applicable_count,
        "targeted_report_sha256": sha256(TARGET_OUTPUT.read_bytes()),
        "policy_full_loo_report_sha256": sha256(POLICY_REPORT.read_bytes()),
        "baseline_policy_overlay_hds_source_sha256": policy_hds_sha,
        "candidate_overlay_hds_source_sha256": candidate_hds_sha,
        "candidate_family_source_sha256": family_sha,
        "root_hds_source_sha256": root_hds_sha,
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "all_folds_matched": True,
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "heldout_output_passed_to_either_solver": False,
        "heldout_output_scored_after_both_solvers_return": True,
        "fallback_counted_correct": False,
        "production_or_notebook_changed": False,
        "official_submission_or_rerun": False,
        "elapsed_full_loo_seconds": round(time.perf_counter() - full_started, 3),
        "elapsed_total_seconds": round(time.perf_counter() - started, 3),
    }
    FULL_OUTPUT.write_text(json.dumps(full_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(full_result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
