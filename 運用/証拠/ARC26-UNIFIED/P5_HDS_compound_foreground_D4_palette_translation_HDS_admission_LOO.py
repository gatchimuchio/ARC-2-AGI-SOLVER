"""Evaluate C2-066 through the isolated HDS teacher-fit/admission path."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE_REPORT = ROOT / "運用/証拠/ARC2_公式スコア起点_20261024/P5_HDS_raw_candidate_LOO.json"
PRIOR_FULL_AUDIT = ROOT / "運用/証拠/ARC26-UNIFIED/P5_HDS_compound_foreground_D4_palette_translation_full_LOO.json"
BASE_RUNNER_PATH = ROOT / "運用/証拠/ARC26-UNIFIED/P5_HDS_edge_transform_output_equivalence_LOO.py"
FAMILY_SOURCE = ROOT / "運用/証拠/ARC26-UNIFIED/C2-066_compound_foreground_D4_palette_translation.py"
OVERLAY = ROOT / "運用/証拠/ARC26-UNIFIED/C2-067-targeted-HDS-consensus-overlay"
OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/C2-067-targeted-C2-066-policy-LOO.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_base_runner():
    spec = importlib.util.spec_from_file_location(
        "arc2_c2066_hds_admission_base_runner", BASE_RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load the HDS LOO helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def prepare_overlay():
    if OVERLAY.exists():
        raise FileExistsError(f"refusing to overwrite {OVERLAY}")
    if not FAMILY_SOURCE.is_file():
        raise FileNotFoundError(FAMILY_SOURCE)
    shutil.copytree(
        ROOT / "接続",
        OVERLAY / "接続",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    family_target = OVERLAY / "接続/ARC2/C2_066_compound_foreground_D4_palette_translation.py"
    shutil.copy2(FAMILY_SOURCE, family_target)

    connector_path = OVERLAY / "接続/ARC2/HDS接続.py"
    original = connector_path.read_bytes()
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    replacements = (
        (
            "from .全前景平行移動教材 import 全前景平行移動教材".encode("utf-8"),
            (
                "from .全前景平行移動教材 import 全前景平行移動教材"
                "\nfrom .C2_066_compound_foreground_D4_palette_translation "
                "import CompoundForegroundD4PaletteTranslation"
            ).replace("\n", newline.decode("ascii")).encode("utf-8"),
        ),
        (
            '    全前景移動 = 全前景平行移動教材(課題["train"])'.encode("utf-8"),
            (
                '    全前景移動 = 全前景平行移動教材(課題["train"])'
                "\n    C2_066_複合前景 = "
                'CompoundForegroundD4PaletteTranslation(課題["train"])'
            ).replace("\n", newline.decode("ascii")).encode("utf-8"),
        ),
        (
            '        ("ARC全前景平行移動", 全前景移動.候補, ()) ,'.replace(" ,", ",").encode("utf-8"),
            (
                '        ("ARC全前景平行移動", 全前景移動.候補, ()),'
                "\n        (\"ARC複合前景D4色写像平行移動\", "
                "C2_066_複合前景.候補, ()),"
            ).replace("\n", newline.decode("ascii")).encode("utf-8"),
        ),
        (
            "        elif 未解決理由:".encode("utf-8"),
            "        elif 未解決理由 and not 予測群:".encode("utf-8"),
        ),
    )
    for old, new in replacements:
        if original.count(old) != 1:
            raise RuntimeError(
                f"overlay patch anchor count was {original.count(old)}, expected one"
            )
        original = original.replace(old, new)
    connector_path.write_bytes(original)
    return {
        "overlay_hds_source_sha256": sha256(original),
        "overlay_family_source_sha256": sha256(family_target.read_bytes()),
    }


def score_pair(answer, target, valid_grid):
    valid = valid_grid(answer)
    exact = bool(valid and answer == target)
    return {
        "answer": int(valid),
        "exact": int(exact),
        "wrong": int(valid and not exact),
        "fallback": int(not valid),
        "union_exact": int(exact),
    }


def family_record(result, family_name):
    for record in (result or {}).get("families", []):
        if record.get("境界") == family_name:
            return record
    return None


def family_record_state(record):
    if record is None:
        return "missing"
    return (
        f"adopt={bool(record.get('採用可'))};"
        f"equivalent={bool(record.get('同値採用'))};"
        f"state={record.get('状態', 'unknown')}"
    )


def main():
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    for required in (BASELINE_REPORT, PRIOR_FULL_AUDIT, BASE_RUNNER_PATH):
        if not required.is_file():
            raise FileNotFoundError(required)

    start = time.perf_counter()
    base = load_base_runner()
    baseline_spec = json.loads(BASELINE_REPORT.read_text(encoding="utf-8"))
    prior = json.loads(PRIOR_FULL_AUDIT.read_text(encoding="utf-8"))
    protected_hds_source_sha = sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes())

    manifest = hashlib.sha256()
    eligible = []
    files = sorted(TRAINING_DIR.glob("*.json"))
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) >= base.SUPPORT_MINIMUM + 1:
            eligible.append(examples)
    if manifest.hexdigest() != baseline_spec["training_manifest_sha256"]:
        raise RuntimeError("public training manifest differs from the established baseline")
    if len(eligible) != baseline_spec["eligible_tasks"]:
        raise RuntimeError("eligible public training population differs from baseline")
    if prior.get("training_manifest_sha256") != manifest.hexdigest():
        raise RuntimeError("C2-066 pilot used a different public training manifest")
    if prior.get("teacher_fit_folds") != 4 or prior.get("candidate_applicable_folds") != 3:
        raise RuntimeError("C2-066 full scan does not match the expected affected-fold counts")

    overlay_hashes = prepare_overlay()
    baseline_solve = base.load_solver()
    overlay_solve = base.load_solver(OVERLAY)
    family_module = importlib.import_module(
        "接続.ARC2.C2_066_compound_foreground_D4_palette_translation"
    )
    family_class = family_module.CompoundForegroundD4PaletteTranslation

    cases = []
    fit_count = 0
    applicable_count = 0
    for examples in eligible:
        for heldout_index, heldout in enumerate(examples):
            teachers = [
                pair for index, pair in enumerate(examples)
                if index != heldout_index
            ]
            family = family_class(teachers)
            if not family._programs:
                continue
            fit_count += 1
            prediction, _ = family.候補(heldout["input"], {})
            applicable = prediction is not None
            applicable_count += int(applicable)
            cases.append((teachers, heldout, applicable))
    if fit_count != 4 or applicable_count != 3 or len(cases) != 4:
        raise RuntimeError(
            "isolated family pre-screen differs from the full public-training scan"
        )

    previous = Counter()
    current = Counter()
    family_selected = 0
    previous_exceptions = 0
    current_exceptions = 0
    unresolved_mentions = 0
    current_mechanisms = Counter()
    family_learning_outcomes = Counter()
    translation_learning_outcomes = Counter()
    quarantine_counts = Counter()
    status_counts = Counter()
    reason_counts = Counter()
    by_applicability = {
        "candidate_input_applicable": {"previous": Counter(), "current": Counter()},
        "candidate_input_not_applicable": {"previous": Counter(), "current": Counter()},
    }
    case_count = 0

    for teachers, heldout, applicable in cases:
        task = {"train": teachers, "test": [{"input": heldout["input"]}]}
        try:
            old_result = baseline_solve(task, [])
            old_row = (old_result or {}).get("results", [{}])[0]
            old_answer = old_row.get("answer")
        except Exception:
            old_answer = None
            old_row = {}
            old_result = {}
            previous_exceptions += 1
        try:
            new_result = overlay_solve(task, [])
            new_row = (new_result or {}).get("results", [{}])[0]
            new_answer = new_row.get("answer")
        except Exception:
            new_answer = None
            new_row = {}
            new_result = {}
            current_exceptions += 1

        # Held-out output is consulted only after both solvers have returned.
        target = heldout["output"]
        old_metrics = score_pair(old_answer, target, base.valid_grid)
        new_metrics = score_pair(new_answer, target, base.valid_grid)
        previous.update(old_metrics)
        current.update(new_metrics)
        applicability_group = (
            "candidate_input_applicable"
            if applicable
            else "candidate_input_not_applicable"
        )
        by_applicability[applicability_group]["previous"].update(old_metrics)
        by_applicability[applicability_group]["current"].update(new_metrics)
        family_name = "ARC複合前景D4色写像平行移動"
        selected = (
            new_row.get("family") == family_name
            or new_row.get("mechanism") == family_name
        )
        family_selected += int(selected)
        mechanism = new_row.get("family") or new_row.get("mechanism") or "unknown"
        current_mechanisms[str(mechanism)] += 1
        family_learning_outcomes[family_record_state(family_record(
            new_result, family_name
        ))] += 1
        translation_learning_outcomes[
            "previous:" + family_record_state(family_record(
                old_result, "ARC全前景平行移動"
            ))
        ] += 1
        translation_learning_outcomes[
            "current:" + family_record_state(family_record(
                new_result, "ARC全前景平行移動"
            ))
        ] += 1
        if isinstance(new_result, dict):
            quarantine_counts[str(new_result.get("quarantined", "missing"))] += 1
        status_counts[str(new_row.get("status", "answered" if new_answer is not None else "unknown"))] += 1
        reasons = new_row.get("reasons", [])
        if isinstance(reasons, list):
            for reason in reasons:
                reason_text = str(reason)
                reason_counts[reason_text] += 1
                unresolved_mentions += int(
                    "複合前景D4色写像平行移動" in reason_text
                )
        case_count += 1

    if case_count != 4:
        raise RuntimeError("did not evaluate every teacher-fit fold")

    previous_metrics = {key: int(previous[key]) for key in (
        "answer", "exact", "wrong", "fallback", "union_exact"
    )}
    current_metrics = {key: int(current[key]) for key in (
        "answer", "exact", "wrong", "fallback", "union_exact"
    )}
    delta = {
        key: current_metrics[key] - previous_metrics[key]
        for key in previous_metrics
    }

    prior_full = prior["full_cohort_previous_current"]["previous_hds_first_answer"]
    full_current = {
        key: int(prior_full[key]) + delta[key]
        for key in ("answer", "exact", "wrong", "fallback", "union_exact")
    }

    result = {
        "run_type": "isolated_hds_consensus_nonveto_targeted_C2-066_folds",
        "official_score_or_submission": False,
        "public_training_manifest_sha256": manifest.hexdigest(),
        "eligible_task_count": len(eligible),
        "public_training_fold_count": sum(len(examples) for examples in eligible),
        "teacher_fit_fold_count": fit_count,
        "candidate_input_applicable_fold_count": applicable_count,
        "hds_admission_folds_evaluated": case_count,
        "previous_hds_first_answer": previous_metrics,
        "current_hds_with_isolated_compound_family": current_metrics,
        "affected_fold_delta_current_minus_previous": delta,
        "previous_full_cohort_from_existing_baseline": {
            key: int(prior_full[key])
            for key in ("answer", "exact", "wrong", "fallback", "union_exact")
        },
        "derived_full_cohort_after_replacing_all_affected_folds": full_current,
        "derived_full_cohort_method": (
            "existing complete 1191-fold baseline plus matched deltas on every "
            "teacher-fit fold found by this full public-training pre-screen; "
            "1187 non-fit folds cannot activate this family"
        ),
        "compound_family_selected_as_solver_output_count": family_selected,
        "solver_exception_counts": {
            "previous": previous_exceptions,
            "current": current_exceptions,
        },
        "current_mechanism_counts_on_affected_folds": dict(current_mechanisms),
        "current_status_counts_on_affected_folds": dict(status_counts),
        "current_hold_reason_counts_on_affected_folds": dict(reason_counts),
        "previous_current_metrics_by_candidate_applicability": {
            group: {
                label: {key: int(counter[key]) for key in (
                    "answer", "exact", "wrong", "fallback", "union_exact"
                )}
                for label, counter in values.items()
            }
            for group, values in by_applicability.items()
        },
        "compound_family_learning_outcomes": dict(family_learning_outcomes),
        "existing_translation_family_learning_outcomes": dict(translation_learning_outcomes),
        "current_quarantined_count_counts": dict(quarantine_counts),
        "unresolved_reason_mentions_of_family": unresolved_mentions,
        "base_hds_source_sha256": protected_hds_source_sha,
        "overlay_hds_source_sha256": overlay_hashes["overlay_hds_source_sha256"],
        "candidate_family_source_sha256": overlay_hashes["overlay_family_source_sha256"],
        "prior_candidate_full_audit_sha256": sha256(PRIOR_FULL_AUDIT.read_bytes()),
        "prior_baseline_report_sha256": sha256(BASELINE_REPORT.read_bytes()),
        "overlay_path_relative": str(OVERLAY.relative_to(ROOT)),
        "heldout_output_passed_to_either_solver": False,
        "heldout_output_scored_after_both_solvers_return": True,
        "task_identifiers_or_grids_saved": False,
        "evaluation_solutions_read": False,
        "fallback_counted_correct": False,
        "production_code_or_notebook_changed": False,
        "official_submission_or_rerun": False,
        "elapsed_seconds": round(time.perf_counter() - start, 3),
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
