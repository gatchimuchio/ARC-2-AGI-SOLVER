"""Support-only necessary condition for the same frozen six training phases.

No tree constructor, heldout query/target, HDS call, or scoring is used. A legal
leaf containing cell c needs one typed action matching c and sufficient other
matching cells/teacher inputs. Global matching support is an upper bound for
any descendant leaf, so failing this condition disproves every tree depth.
Passing is not evidence that any partition or bounded exact tree exists.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BASE = HERE / "prune_fit_diagnosis.py"
BASE_SHA256 = "9c1788a6421774167ea10076355e2ff47ca58fe1d9f2988287d57b46f3db4e7a"
MODULE_SHA256 = "119f390837e8c5ecf77eff8833ef7371c13bb565aa123f86f13b2076b931e6f0"
PARTITION_FIT = HERE / "fit_results/partition-fit-six-phases-20261027T0135Z.jsonl"
PARTITION_FIT_SHA256 = "f3ee2bb1e381f70e71a61299b4eb1737b72fe43a1c529ba73512f9c18ff8ca1b"
ABSENT_METADATA = ROOT / ".venv/Lib/site-packages/numpy-2.3.5.dist-info/direct_url.json"


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_base():
    if sha(BASE.read_bytes()) != BASE_SHA256:
        raise ValueError("pinned FIT-only helper changed")
    spec = importlib.util.spec_from_file_location("arc2_action_support_base", BASE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fingerprint(base):
    if base.MODULE_SHA256 != MODULE_SHA256:
        raise ValueError("wrong fixed tree module")
    pins = {"script_sha256": sha(Path(__file__).read_bytes()), "base_diagnostic_sha256": BASE_SHA256,
            "module_sha256": MODULE_SHA256, "previous_partition_fit_sha256": PARTITION_FIT_SHA256,
            "dependency_fingerprint": base.fingerprint()}
    return {"sha256": sha(encoded(pins)), **pins}


def action_support_condition(module, support, bounds):
    """Root-only upper bound, all actions before MDL filtering, each cell's roles.

    Input deduplication and physical cell counting follow CellConditionalTree.
    We intentionally ignore feature separability: failure suffices, success does
    not. No raw grid, target, feature vector or role tuple is returned.
    """
    if len(module.FEATURES) != 35 or len(module.PROGRAMS) != 21:
        raise ValueError("fixed 35-feature / 21-action grammar changed")
    unique = {}
    for pair in support:
        if not isinstance(pair, dict) or set(pair) != {"input", "output"}:
            raise ValueError("support schema differs")
        input_key = tuple(tuple(row) for row in pair["input"])
        if input_key in unique and unique[input_key]["output"] != pair["output"]:
            raise ValueError("conflicting_duplicate_input")
        unique[input_key] = pair
    ordered = [unique[key] for key in sorted(unique)]
    matching_cells = {program: 0 for program in module.PROGRAMS}
    matching_teachers = {program: set() for program in module.PROGRAMS}
    cell_actions = []
    for teacher_id, pair in enumerate(ordered):
        targets = (color for row in pair["output"] for color in row)
        for (_features, roles), target in zip(module._input_cells(pair["input"]), targets, strict=True):
            allowed = tuple(program for program in module.PROGRAMS
                            if module._program_value(program, roles) == target)
            cell_actions.append((teacher_id, allowed))
            for program in allowed:
                matching_cells[program] += 1
                matching_teachers[program].add(teacher_id)
    eligible = {program for program in module.PROGRAMS
                if matching_cells[program] >= bounds.minimum_cell_support
                and len(matching_teachers[program]) >= bounds.minimum_teacher_support}
    unsupported_cells = [(teacher_id, actions) for teacher_id, actions in cell_actions
                         if not any(action in eligible for action in actions)]
    allowed_histogram, supported_histogram = {}, {}
    for _teacher_id, actions in cell_actions:
        allowed_histogram[str(len(actions))] = allowed_histogram.get(str(len(actions)), 0) + 1
        supported = sum(action in eligible for action in actions)
        supported_histogram[str(supported)] = supported_histogram.get(str(supported), 0) + 1
    impossible = bool(unsupported_cells)
    return {"status": "NECESSARY_CONDITION_DISPROVEN" if impossible else "NO_ACTION_SUPPORT_DISPROOF",
            "scope": "root_whole_current_support_upper_bound_for_every_descendant_leaf",
            "raw_teacher_count": len(support), "distinct_input_teachers": len(ordered),
            "physical_cell_count": len(cell_actions), "typed_action_count": len(module.PROGRAMS),
            "minimum_teacher_support": bounds.minimum_teacher_support,
            "minimum_cell_support": bounds.minimum_cell_support,
            "globally_support_eligible_action_count": len(eligible),
            "cells_without_any_support_eligible_matching_action": len(unsupported_cells),
            "teachers_with_such_cells": len({teacher for teacher, _actions in unsupported_cells}),
            "allowed_action_count_histogram": allowed_histogram,
            "supported_allowed_action_count_histogram": supported_histogram,
            "action_supports": [{"program": program, "matching_cell_count": matching_cells[program],
                                 "matching_distinct_teacher_count": len(matching_teachers[program]),
                                 "globally_support_eligible": program in eligible}
                                for program in module.PROGRAMS],
            "grammar_impossible_at_any_depth": impossible,
            "all_21_actions_before_mdl_filter": True,
            "dynamic_roles_evaluated_per_own_input_cell": True,
            "passing_is_only_necessary_not_fit_or_partition_proof": True}


def run_worker(payload, expected_source):
    base = load_base()
    base.validate_payload(payload, "necessary_condition")
    sources = fingerprint(base)
    if sources["sha256"] != expected_source:
        raise ValueError("diagnostic source changed before worker")
    if ABSENT_METADATA.exists():
        raise ValueError("reviewed absent NumPy metadata appeared")
    blocked, absent_probes = [], []
    def guard(event, arguments):
        if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0]))
            if path.suffix.lower() in (".json", ".jsonl"):
                if path.resolve() == ABSENT_METADATA.resolve() and not path.exists():
                    absent_probes.append(str(path.resolve()))
                    raise FileNotFoundError("reviewed absent package metadata; no content opened")
                blocked.append(str(path.resolve()))
                raise RuntimeError("support-only worker JSON reads forbidden")
    sys.addaudithook(guard)
    sys.path.insert(0, str(ROOT))
    capture = io.StringIO()
    with redirect_stdout(capture):
        module = base.load_source(base.MODULE, "arc2_action_support_frozen_tree")
        if asdict(module.Bounds()) != base.DEFAULT_BOUNDS:
            raise ValueError("fixed bounds changed")
        def forbidden(*_args, **_kwargs):
            raise RuntimeError("tree fitting, queries and HDS are outside support-only diagnosis")
        module._connection = forbidden
        module.CellConditionalTree = forbidden
        module._evaluate = forbidden
        origins_before = base.runtime_origins(sources["dependency_fingerprint"], module)
        support = deepcopy(payload["support"])
        immutable = encoded(support)
        started, cpu_started = time.perf_counter(), time.process_time()
        condition = action_support_condition(module, support, module.Bounds(**payload["bounds"]))
        elapsed, cpu = time.perf_counter() - started, time.process_time() - cpu_started
        if encoded(support) != immutable:
            raise ValueError("support mutated")
        origins_after = base.runtime_origins(sources["dependency_fingerprint"], module)
    if blocked:
        raise RuntimeError("forbidden JSON open attempt was caught internally")
    if ABSENT_METADATA.exists() or fingerprint(base) != sources:
        raise ValueError("pinned source/metadata state changed")
    return {"state": "complete", "condition": condition, "source_sha256": sources["sha256"],
            "bounds": dict(base.DEFAULT_BOUNDS), "support_unchanged": True,
            "fit_calls": 0, "external_query_calls": 0, "hds_calls": 0, "scoring_calls": 0,
            "runtime_origins_before": origins_before, "runtime_origins_after": origins_after,
            "blocked_json_open_attempts": blocked, "json_content_opens": 0,
            "absent_numpy_metadata_probe_count": len(absent_probes),
            "exact_absent_metadata_path": str(ABSENT_METADATA.resolve()),
            "metadata_absent_before_and_after": True,
            "solver_seconds": round(elapsed, 6), "process_cpu_seconds": round(cpu, 6),
            "unexpected_stdout_sha256": sha(capture.getvalue().encode("utf-8"))}


def invoke(payload, sources):
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    started = time.perf_counter()
    try:
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker",
                                  "--expected-source-sha256", sources["sha256"]],
                                 input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", cwd=ROOT,
                                 env=env, timeout=90, check=False)
        result = json.loads(process.stdout) if process.returncode == 0 else {
            "state": "worker_exit", "return_code": process.returncode,
            "stderr_sha256": sha(process.stderr.encode("utf-8"))}
    except subprocess.TimeoutExpired:
        result = {"state": "timeout", "timeout_seconds": 90}
    except (json.JSONDecodeError, TypeError):
        result = {"state": "invalid_worker_output"}
    if not isinstance(result, dict):
        result = {"state": "invalid_worker_output"}
    result["wall_seconds"] = round(time.perf_counter() - started, 6)
    return result


def prepare(base, sources):
    prepared = base.run(SimpleNamespace(
        expected_script_sha256=BASE_SHA256, expected_study_sha256=base.STUDY_SHA256,
        expected_cohort_sha256=base.COHORT_SHA256,
        study=base.OLD_ROOT / "public_results/study20-20261027T0005Z.jsonl",
        cohort=base.OLD_ROOT / "public_results/study20-20261027T0005Z.cohort.json",
        execute=False, with_necessary_condition=False))
    previous_bytes = PARTITION_FIT.read_bytes()
    if sha(previous_bytes) != PARTITION_FIT_SHA256:
        raise ValueError("terminal partition FIT evidence differs from pin")
    previous = [json.loads(line) for line in previous_bytes.splitlines() if line.strip()]
    expected = [(case["cohort_index"], case["phase"]) for case in prepared["cases"]]
    if len(expected) != 6 or [(row["cohort_index"], row["phase"]) for row in previous] != expected:
        raise ValueError("selected phases differ from the same fixed six")
    if any(row["pruned_fit"].get("state") != "complete" for row in previous):
        raise ValueError("partition FIT records are not all terminal complete")
    for case, row in zip(prepared["cases"], previous, strict=True):
        case["previous_partition_fit_status"] = row["pruned_fit"]["fit"]["status"]
    return {"state": "prepared_support_only_no_fit", "sources": sources,
            "cases": prepared["cases"], "selected_phases": 6,
            "study_sha256": base.STUDY_SHA256, "cohort_sha256": base.COHORT_SHA256,
            "previous_partition_fit_sha256": PARTITION_FIT_SHA256,
            "bounds": dict(base.DEFAULT_BOUNDS), "after_support_includes_observed_feedback_pair": True,
            "unseen_pair_excluded_entirely": True, "fit_or_query_or_hds_or_scoring": False}


def run(args):
    base = load_base()
    sources = fingerprint(base)
    if sources["script_sha256"] != args.expected_script_sha256:
        raise ValueError("script differs from reviewed hash")
    prepared = prepare(base, sources)
    if not args.execute:
        return prepared
    output = args.output.resolve()
    summary_path = output.with_suffix(".summary.json")
    if not output.is_relative_to(HERE.resolve()):
        raise ValueError("new diagnostic evidence must stay in its own experiment")
    if output.exists() or summary_path.exists():
        raise FileExistsError("refuse to overwrite support-only evidence")
    training_bytes = base.TRAINING.read_bytes()
    cohort = json.loads((base.OLD_ROOT / "public_results/study20-20261027T0005Z.cohort.json").read_bytes())
    if sha(training_bytes) != cohort["training_file_sha256"]:
        raise ValueError("public training differs from pinned cohort")
    training = json.loads(training_bytes)
    rows = {row["index"]: row for row in cohort["rows"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    with output.open("x", encoding="utf-8") as stream:
        for case in prepared["cases"]:
            payload = base.make_payload(training, rows[case["cohort_index"]], case["phase"], base.DEFAULT_BOUNDS)
            base.validate_payload(payload, "necessary_condition")
            if sha(encoded(payload)) != case["current_support_payload_sha256"]:
                raise ValueError("support differs from existing fixed phase")
            result = invoke(payload, sources)
            record = {**case, "action_support": result}
            records.append(record)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"completed_phases": len(records), "cohort_index": case["cohort_index"],
                              "phase": case["phase"], "state": result["state"],
                              "condition_status": result.get("condition", {}).get("status")}), flush=True)
    unchanged = sources == fingerprint(base)
    complete = all(row["action_support"].get("state") == "complete" for row in records)
    capped = [row for row in records if row["previous_partition_fit_status"] == "fit_state_budget_exceeded"]
    summary = {**prepared, "state": "SUPPORT_DIAGNOSIS_COMPLETE" if complete else "SUPPORT_DIAGNOSIS_INCOMPLETE",
               "completed_at": datetime.now(timezone.utc).isoformat(), "completed_phases": len(records),
               "complete_worker_phases": sum(row["action_support"].get("state") == "complete" for row in records),
               "source_unchanged": unchanged, "output_sha256": sha(output.read_bytes()),
               "grammar_disproven_phases": sum(row["action_support"].get("condition", {}).get("grammar_impossible_at_any_depth", False) for row in records),
               "remaining_partition_capped_phases": len(capped),
               "remaining_partition_capped_disproven": sum(row["action_support"].get("condition", {}).get("grammar_impossible_at_any_depth", False) for row in capped),
               "fit_calls": 0, "external_query_calls": 0, "hds_calls": 0, "scoring_calls": 0,
               "passing_is_only_necessary_not_fit_proof": True, "performance_or_score_improvement_claimed": False}
    if not unchanged:
        raise ValueError("source changed during support-only diagnosis")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--expected-source-sha256")
    parser.add_argument("--expected-script-sha256")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output", type=Path, default=HERE / "fit_results/action-support-six-phases.jsonl")
    args = parser.parse_args()
    try:
        result = run_worker(json.load(sys.stdin), args.expected_source_sha256) if args.worker else run(args)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as error:
        print(json.dumps({"state": "diagnostic_error", "error_type": type(error).__name__}), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
