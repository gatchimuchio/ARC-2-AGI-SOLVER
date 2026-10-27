"""Leaf-only MIN1 ablation FIT diagnosis; global support2/cell2/caps unchanged.

Parent reads the frozen cohort/public training. Every fresh worker receives
only current support input/output pairs and one fixed bounds dictionary.
After support includes the already-observed F pair; U is excluded completely.
There are no heldout query fields, heldout targets, HDS calls or scoring calls.
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
import traceback


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MODULE = HERE / "cell_conditional_tree.py"
OLD_ROOT = HERE.with_name("ARC2-cell-conditional-tree-rowcol")
HARNESS = OLD_ROOT / "public_harness.py"
TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
MODULE_SHA256 = "66a5b525e42881ae35b2a125c7a8f85628a8cce9b95179fdd89c62b38b7e22d6"
OLD_MODULE_SHA256 = "0664c6ef1878f434c963125a767a65a35a4737aff9132a5091c05a5c316a5ac2"
HARNESS_SHA256 = "6deb75bc2cc980e1e7b59aa11354bd6b3ff02f01bc36b4fffdc64bf27479232e"
STUDY_SHA256 = "9e2dac77349f098f8130d97028ab7fd15a57717dfe5e481a1c652db5ccfbd316"
COHORT_SHA256 = "f4ccbe47c84d0807f61a246d4622e3d46d5580e086bcb6d346195d06f84be5ba"
RECORDED_SOURCE_SHA256 = "a15209df6436553d37a96d62c67f07574a68eca353844ec93905a51233257b77"
FEATURE_COUNT, ACTION_COUNT = 35, 21
DEFAULT_BOUNDS = {"max_depth": 3, "max_nodes": 15, "max_teachers": 8,
                  "max_training_cells": 4096, "minimum_teacher_support": 2,
                  "minimum_cell_support": 2, "max_fit_states": 256,
                  "max_alternatives": 32, "max_work_units": 2_000_000}
EXPECTED_MODULE_DEFAULT_BOUNDS = {**DEFAULT_BOUNDS, "minimum_leaf_teacher_support": 2}
FIT_BOUNDS = {**DEFAULT_BOUNDS, "minimum_leaf_teacher_support": 1}
BASELINE_ROOT = HERE.with_name("ARC2-cell-conditional-tree-rowcol-action-support-prune")
BASELINE_MODULE_SHA256 = "405065a7d8260f6b618e3b7cb1a90103f3e610250438eb5db7abf9c3289d366c"
BASELINE_FIT = BASELINE_ROOT / "fit_results/action-pruned-fit-six-phases-20261027T0151Z.jsonl"
BASELINE_FIT_SHA256 = "d327205ecbbb2f3520fa7c47dd0085bf38835519ab79ece49aa4127689a5ca06"
BASELINE_SOURCE_SHA256 = "ad6ddc1ca6f7fdaffcd04b5b7eab57d58831d14dfaf50d633d453d5c8b55bb40"
SUMMARY_FIELDS = ("status", "training_examples", "distinct_training_examples",
                  "training_cells", "fit_states", "work_units", "training_replayed")


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_source(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def fingerprint():
    if sha(MODULE.read_bytes()) != MODULE_SHA256:
        raise ValueError("reviewed pruned tree module changed")
    if sha((BASELINE_ROOT / "cell_conditional_tree.py").read_bytes()) != BASELINE_MODULE_SHA256:
        raise ValueError("frozen405 baseline module changed")
    if sha((OLD_ROOT / "cell_conditional_tree.py").read_bytes()) != OLD_MODULE_SHA256 or sha(HARNESS.read_bytes()) != HARNESS_SHA256:
        raise ValueError("recorded ROWCOL source or harness changed")
    harness = load_source(HARNESS, "arc2_tree_fit_diagnosis_harness")
    original = harness.source_fingerprint()
    if original["sha256"] != RECORDED_SOURCE_SHA256:
        raise ValueError("current runtime sources differ from recorded ROWCOL study")
    script_sha = sha(Path(__file__).read_bytes())
    pins = {"script_sha256": script_sha, "pruned_module_sha256": MODULE_SHA256,
            "old_module_sha256": OLD_MODULE_SHA256, "recorded_harness_sha256": HARNESS_SHA256,
            "study_sources": original, "baseline_module_sha256": BASELINE_MODULE_SHA256,
            "baseline_fit_sha256": BASELINE_FIT_SHA256,
            "global_generator_teacher_minimum": 2, "local_leaf_ablation_minimum": 1}
    return {"sha256": sha(encoded(pins)), **pins}


def valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and isinstance(grid[0], list) and 1 <= len(grid[0]) <= 30
            and all(isinstance(row, list) and len(row) == len(grid[0])
                    and all(type(color) is int and 0 <= color <= 9 for color in row) for row in grid))


def validate_payload(payload, mode):
    if not isinstance(payload, dict) or set(payload) != {"support", "bounds"}:
        raise ValueError("workers accept only support pairs and fixed bounds")
    if mode not in ("necessary_condition", "pruned_fit", "pruned_fit_with_condition"):
        raise ValueError("unknown diagnostic mode")
    if not isinstance(payload["bounds"], dict) or payload["bounds"] != FIT_BOUNDS or any(type(value) is not int for value in payload["bounds"].values()):
        raise ValueError("unreviewed fit bounds")
    support = payload["support"]
    if not isinstance(support, list) or not 3 <= len(support) <= DEFAULT_BOUNDS["max_teachers"]:
        raise ValueError("invalid current support count")
    if any(not isinstance(pair, dict) or set(pair) != {"input", "output"}
           or not valid_grid(pair["input"]) or not valid_grid(pair["output"]) for pair in support):
        raise ValueError("support must contain only current input/output teachers")
    if any((len(pair["input"]), len(pair["input"][0])) != (len(pair["output"]), len(pair["output"][0])) for pair in support):
        raise ValueError("FIT diagnosis requires shape-preserving support")
    if len({encoded(pair["input"]) for pair in support}) != len(support):
        raise ValueError("support inputs must be distinct")


def necessary_condition(module, support):
    """Empty same-feature action intersection disproves this grammar at ANY depth.

    Use ALL programs, including nonminimal ones, and each cell's OWN roles.
    Nonempty groups prove neither bounded fit nor sufficient teacher support.
    No raw feature vectors, program labels or target colors leave this function.
    """
    if len(module.FEATURES) != FEATURE_COUNT or len(module.PROGRAMS) != ACTION_COUNT:
        raise ValueError("unexpected frozen feature/program grammar")
    groups = {}
    counts = {}
    checked_cells = 0
    for pair in support:
        if set(pair) != {"input", "output"} or not valid_grid(pair["input"]) or not valid_grid(pair["output"]) or (len(pair["input"]), len(pair["input"][0])) != (len(pair["output"]), len(pair["output"][0])):
            raise ValueError("invalid shape-preserving support")
        targets = (color for row in pair["output"] for color in row)
        for (features, roles), target in zip(module._input_cells(pair["input"]), targets, strict=True):
            if len(features) != FEATURE_COUNT:
                raise ValueError("feature extraction changed")
            viable = {program for program in module.PROGRAMS
                      if module._program_value(program, roles) == target}
            if features in groups:
                groups[features].intersection_update(viable)
            else:
                groups[features] = viable
            counts[features] = counts.get(features, 0) + 1
            checked_cells += 1
    impossible = [features for features, programs in groups.items() if not programs]
    return {"checked_cells": checked_cells, "full_feature_groups": len(groups),
            "inexpressible_groups": len(impossible),
            "cells_in_inexpressible_groups": sum(counts[features] for features in impossible),
            "grammar_impossible_at_any_depth": bool(impossible),
            "nonempty_intersections_are_only_necessary": True}


def selected_cases(records):
    """Selection reads cell-tree fit status only; no scores/query predictions."""
    selected = []
    for record in records:
        for phase in ("before", "after"):
            evidence = record["results"]["rowcol35"][phase]["evidence"]
            state = evidence["model_fitted"]["typed_state"]
            if evidence["state"] == "complete" and state["status"] == "fit_state_budget_exceeded":
                if (state["bounds"] != DEFAULT_BOUNDS or state["feature_indices"] != list(range(FEATURE_COUNT))
                        or evidence["arm_feature_count"] != FEATURE_COUNT or evidence["typed_action_count"] != ACTION_COUNT):
                    raise ValueError("recorded budget case used a different grammar or bounds")
                selected.append({"cohort_index": record["cohort_index"], "phase": phase,
                                 "recorded_default": {field: state[field] for field in SUMMARY_FIELDS},
                                 "recorded_source_sha256": evidence["source_sha256"]})
    return selected


def make_payload(training, row, phase, bounds):
    indices = list(row["support_indices"])
    if (not indices or any(type(index) is not int or index < 0 for index in indices)
            or len(indices) != len(set(indices)) or type(row["feedback_index"]) is not int
            or type(row["unseen_index"]) is not int or row["feedback_index"] < 0 or row["unseen_index"] < 0
            or row["feedback_index"] == row["unseen_index"]
            or row["feedback_index"] in indices or row["unseen_index"] in indices):
        raise ValueError("support/F/U indices are not disjoint")
    if phase == "after":
        indices.append(row["feedback_index"])
    elif phase != "before":
        raise ValueError("unknown support phase")
    if row["unseen_index"] in indices:
        raise ValueError("heldout U entered support")
    pairs = training[row["task_id"]]["train"]
    return {"support": [{"input": deepcopy(pairs[index]["input"]),
                         "output": deepcopy(pairs[index]["output"])} for index in indices],
            "bounds": dict(bounds)}


def runtime_origins(sources, module):
    expected = {row["path"]: row["sha256"] for row in sources["study_sources"]["files"]}
    checked = []
    for name, loaded in sorted(tuple(sys.modules.items())):
        if name == "接続.ARC2" or name.startswith("接続.ARC2."):
            required = (ROOT / "接続/ARC2").resolve()
        elif name == "hds学習系統" or name.startswith("hds学習系統."):
            required = (ROOT / "HDS/学習系統/v0.4.2").resolve()
        else:
            continue
        filename = getattr(loaded, "__file__", None)
        if filename is None:
            if not all(Path(path).resolve().is_relative_to(required) for path in getattr(loaded, "__path__", [])):
                raise ValueError("runtime namespace escaped pinned worktree")
            continue
        actual = Path(filename).resolve()
        if not actual.is_relative_to(required):
            raise ValueError("runtime import escaped pinned worktree")
        relative = actual.relative_to(ROOT).as_posix()
        digest = sha(actual.read_bytes())
        if expected.get(relative) != digest:
            raise ValueError("runtime source differs from study pin")
        checked.append({"module": name, "path": relative, "sha256": digest})
    if Path(module.__file__).resolve() != MODULE.resolve():
        raise ValueError("wrong tree module imported")
    if sha(Path(module.__file__).read_bytes()) != sources["pruned_module_sha256"]:
        raise ValueError("pruned module differs from pin")
    return {"module_count": len(checked), "module_origins_sha256": sha(encoded(checked)),
            "all_origins_pinned_current_worktree": True}


def run_worker(payload, mode, expected_source):
    validate_payload(payload, mode)
    sources = fingerprint()
    if sources["sha256"] != expected_source:
        raise ValueError("diagnostic source changed before worker")
    absent = ROOT / ".venv/Lib/site-packages/numpy-2.3.5.dist-info/direct_url.json"
    blocked_json, absent_probes = [], []
    def guard(event, arguments):
        if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0]))
            if path.suffix.lower() in (".json", ".jsonl"):
                if path.resolve() == absent.resolve() and not path.exists():
                    absent_probes.append(str(path.resolve()))
                    raise FileNotFoundError("reviewed absent package metadata")
                blocked_json.append(str(path.resolve()))
                raise RuntimeError("FIT worker dataset/JSON file reads forbidden")
    sys.addaudithook(guard)
    sys.path.insert(0, str(ROOT))
    module = load_source(MODULE, "arc2_cell_tree_fit_only")
    if asdict(module.Bounds()) != EXPECTED_MODULE_DEFAULT_BOUNDS:
        raise ValueError("default bounds differ from reviewed baseline")
    def no_hds():
        raise RuntimeError("HDS calls are outside FIT-only diagnosis")
    module._connection = no_hds
    origins_before = runtime_origins(sources, module)
    support = deepcopy(payload["support"])
    immutable = encoded(support)
    started, cpu_started = time.perf_counter(), time.process_time()
    if len(module.FEATURES) != FEATURE_COUNT or len(module.PROGRAMS) != ACTION_COUNT:
        raise ValueError("reviewed 35-feature/21-action grammar changed")
    result = {"state": "complete", "mode": mode,
              "fit_executed": False, "default_full_feature_count": FEATURE_COUNT,
              "typed_action_count": ACTION_COUNT, "bounds": dict(FIT_BOUNDS),
              "external_query_calls": 0, "hds_calls": 0, "scoring_calls": 0}
    if mode in ("necessary_condition", "pruned_fit_with_condition"):
        result["condition"] = necessary_condition(module, support)
    captured = io.StringIO()
    if mode in ("pruned_fit", "pruned_fit_with_condition"):
        with redirect_stdout(captured):
            model = module.CellConditionalTree(support, bounds=module.Bounds(**payload["bounds"]))
        result["fit_executed"] = True
        result["fit"] = {field: getattr(model, field) for field in SUMMARY_FIELDS}
        if model.feature_indices != tuple(range(FEATURE_COUNT)) or asdict(model.bounds) != FIT_BOUNDS:
            raise ValueError("constructor changed frozen grammar or bounds")
        result["constructor_training_replay_only"] = True
    if encoded(support) != immutable:
        raise ValueError("current support was mutated")
    if blocked_json:
        raise RuntimeError("forbidden JSON read was caught inside helper")
    result.update(solver_seconds=round(time.perf_counter() - started, 6),
                  process_cpu_seconds=round(time.process_time() - cpu_started, 6),
                  support_unchanged=True, unexpected_stdout_sha256=sha(captured.getvalue().encode("utf-8")),
                  blocked_json_open_attempts=blocked_json, json_content_opens=0,
                  absent_numpy_metadata_probe_count=len(absent_probes),
                  exact_absent_metadata_path=str(absent.resolve()),
                  source_sha256=sources["sha256"], runtime_origins_before=origins_before,
                  runtime_origins_after=runtime_origins(sources, module))
    if fingerprint() != sources:
        raise ValueError("diagnostic source changed during worker")
    return result


def invoke(payload, mode, source_sha256, timeout=90):
    if not 0 < timeout <= 90:
        raise ValueError("worker wall limit must not exceed 90 seconds")
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    started = time.perf_counter()
    try:
        process = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker", mode,
                                  "--expected-source-sha256", source_sha256],
                                 input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", cwd=ROOT,
                                 env=env, timeout=timeout, check=False)
        result = json.loads(process.stdout) if not process.returncode else {"state": "worker_exit", "return_code": process.returncode,
                                                                        "stderr_sha256": sha(process.stderr.encode("utf-8"))}
    except subprocess.TimeoutExpired:
        result = {"state": "timeout", "timeout_seconds": timeout}
    except (json.JSONDecodeError, TypeError):
        result = {"state": "invalid_worker_output"}
    if not isinstance(result, dict):
        result = {"state": "invalid_worker_output"}
    result["wall_seconds"] = round(time.perf_counter() - started, 6)
    return result


def diagnose_case(payload, invoke_worker, with_condition=False):
    """One same-budget worker; optional condition never changes/short-circuits fit."""
    validate_payload(payload, "pruned_fit")
    return invoke_worker(deepcopy(payload), "pruned_fit_with_condition" if with_condition else "pruned_fit")


def run(args):
    sources = fingerprint()
    if sources["script_sha256"] != args.expected_script_sha256:
        raise ValueError("diagnostic script differs from reviewed SHA")
    if args.expected_study_sha256 != STUDY_SHA256 or args.expected_cohort_sha256 != COHORT_SHA256:
        raise ValueError("only the reviewed ROWCOL study and cohort are allowed")
    study_bytes, cohort_bytes = args.study.read_bytes(), args.cohort.read_bytes()
    if sha(study_bytes) != args.expected_study_sha256 or sha(cohort_bytes) != args.expected_cohort_sha256:
        raise ValueError("study/cohort evidence differs from reviewed SHA")
    cohort = json.loads(cohort_bytes)
    records = [json.loads(line) for line in study_bytes.splitlines() if line.strip()]
    if len(records) != cohort["tasks_requested"] or len({row["cohort_index"] for row in records}) != len(records):
        raise ValueError("study is not terminal with its full requested cohort")
    if cohort["source_sha256"] != sources["study_sources"]["sha256"]:
        raise ValueError("current sources differ from recorded default study")
    training_bytes = TRAINING.read_bytes()
    if sha(training_bytes) != cohort["training_file_sha256"]:
        raise ValueError("training differs from recorded study")
    training = json.loads(training_bytes)
    cases = selected_cases(records)
    if len(cases) != 6:
        raise ValueError("expected exactly six recorded ROWCOL budget phases")
    rows = {row["index"]: row for row in cohort["rows"]}
    if any(case["recorded_source_sha256"] != cohort["source_sha256"] for case in cases):
        raise ValueError("selected phase source pin mismatch")
    baseline_bytes = BASELINE_FIT.read_bytes()
    if sha(baseline_bytes) != BASELINE_FIT_SHA256:
        raise ValueError("frozen405 terminal FIT evidence differs from pin")
    baseline_rows = [json.loads(line) for line in baseline_bytes.splitlines() if line.strip()]
    if [(row["cohort_index"], row["phase"]) for row in baseline_rows] != [(case["cohort_index"], case["phase"]) for case in cases]:
        raise ValueError("frozen405 phases differ from selected six")
    for case, baseline in zip(cases, baseline_rows, strict=True):
        evidence = baseline["pruned_fit"]
        if evidence.get("state") != "complete" or evidence.get("source_sha256") != BASELINE_SOURCE_SHA256 or evidence.get("bounds") != DEFAULT_BOUNDS:
            raise ValueError("frozen405 evidence is not terminal with original bounds/source")
        case["ancestor_recorded_default"] = case["recorded_default"]
        case["ancestor_source_sha256"] = case["recorded_source_sha256"]
        case["recorded_default"] = evidence["fit"]
        case["recorded_source_sha256"] = BASELINE_SOURCE_SHA256
        case["baseline_support_payload_sha256"] = baseline["current_support_payload_sha256"]
    for case in cases:
        payload = make_payload(training, rows[case["cohort_index"]], case["phase"], FIT_BOUNDS)
        validate_payload(payload, "pruned_fit")
        if len(payload["support"]) != case["recorded_default"]["training_examples"]:
            raise ValueError("current support count differs from recorded phase")
        case["current_support_payload_sha256"] = sha(encoded(payload))
        case["current_support_only_sha256"] = sha(encoded(payload["support"]))
        baseline_payload = {"support": payload["support"], "bounds": dict(DEFAULT_BOUNDS)}
        if sha(encoded(baseline_payload)) != case["baseline_support_payload_sha256"]:
            raise ValueError("support differs from frozen405 input payload")
    prepared = {"state": "prepared_no_fit", "selected_phases": len(cases), "cases": cases,
                "sources": sources, "study_sha256": sha(study_bytes), "cohort_sha256": sha(cohort_bytes),
                "bounds": dict(FIT_BOUNDS), "grammar": {"features": FEATURE_COUNT, "actions": ACTION_COUNT},
                "budget_expansion": False, "worker_mode": "pruned_fit_with_condition" if args.with_necessary_condition else "pruned_fit",
                "after_support_includes_observed_feedback_pair": True,
                "unseen_pair_excluded_entirely": True, "heldout_queries_or_scoring": False,
                "old_configuration": {"module_sha256": BASELINE_MODULE_SHA256,
                    "bounds": dict(DEFAULT_BOUNDS), "implicit_local_leaf_minimum": 2,
                    "terminal_fit_sha256": BASELINE_FIT_SHA256},
                "new_configuration": {"module_sha256": MODULE_SHA256, "bounds": dict(FIT_BOUNDS)},
                "global_generator_minimum_unchanged": 2, "minimum_cells_unchanged": 2,
                "numerical_hds_support_not_modified_or_exercised_by_fit_only": True,
                "recorded_default_is_frozen405_not_ancestor0664": True}
    if not args.execute:
        return prepared
    output, summary_path = args.output.resolve(), args.output.resolve().with_suffix(".summary.json")
    if not output.is_relative_to(HERE.resolve()):
        raise ValueError("diagnostic evidence must stay in its own experiment")
    if output.exists() or summary_path.exists():
        raise FileExistsError("refuse to overwrite FIT diagnosis evidence")
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = []
    with output.open("x", encoding="utf-8") as stream:
        for case in cases:
            payload = make_payload(training, rows[case["cohort_index"]], case["phase"], FIT_BOUNDS)
            if len(payload["support"]) != case["recorded_default"]["training_examples"]:
                raise ValueError("current support count differs from recorded default phase")
            if sha(encoded(payload)) != case["current_support_payload_sha256"]:
                raise ValueError("ablation support/config differs from prepared payload")
            diagnosis = diagnose_case(payload, lambda data, mode: invoke(data, mode, sources["sha256"]), args.with_necessary_condition)
            record = {**case, "pruned_fit": diagnosis}
            fit = diagnosis.get("fit")
            record["delta_vs_frozen405"] = ({field: fit[field] - case["recorded_default"][field]
                for field in SUMMARY_FIELDS if field != "status"} if fit is not None else None)
            completed.append(record)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"completed_phases": len(completed), "selected_phases": len(cases),
                              "cohort_index": case["cohort_index"], "phase": case["phase"],
                              "worker_state": diagnosis["state"], "fit_status": diagnosis.get("fit", {}).get("status")}), flush=True)
    if fingerprint() != sources:
        raise ValueError("diagnostic sources changed during parent run")
    summary = {**prepared, "state": "FIT_DIAGNOSIS_COMPLETE", "completed_at": datetime.now(timezone.utc).isoformat(),
               "completed_phases": len(completed), "output_sha256": sha(output.read_bytes()),
               "grammar_disproven_phases": sum(row["pruned_fit"].get("condition", {}).get("grammar_impossible_at_any_depth", False) for row in completed),
               "pruned_fits_executed": sum(row["pruned_fit"].get("fit_executed", False) for row in completed),
               "worker_wall_limit_seconds": 90, "performance_or_score_improvement_claimed": False}
    with summary_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=("necessary_condition", "pruned_fit", "pruned_fit_with_condition"))
    parser.add_argument("--expected-source-sha256")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--prepare-only", action="store_true")
    operation.add_argument("--execute", action="store_true", help="explicitly run the six fit-only workers after review")
    parser.add_argument("--with-necessary-condition", action="store_true")
    parser.add_argument("--expected-script-sha256")
    parser.add_argument("--expected-study-sha256", default=STUDY_SHA256)
    parser.add_argument("--expected-cohort-sha256", default=COHORT_SHA256)
    parser.add_argument("--study", type=Path, default=OLD_ROOT / "public_results/study20-20261027T0005Z.jsonl")
    parser.add_argument("--cohort", type=Path, default=OLD_ROOT / "public_results/study20-20261027T0005Z.cohort.json")
    parser.add_argument("--output", type=Path, default=HERE / "fit_results/leaf-min1-six-phases.jsonl")
    args = parser.parse_args()
    try:
        if args.worker:
            result = run_worker(json.load(sys.stdin), args.worker, args.expected_source_sha256)
        else:
            if not all((args.expected_script_sha256, args.expected_study_sha256, args.expected_cohort_sha256)):
                raise ValueError("parent requires reviewed script/study/cohort SHA pins")
            result = run(args)
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as error:
        # No raw exception body: support/color labels never leak to evidence.
        safe = {"state": "diagnostic_error", "error_type": type(error).__name__,
                "frames": [{"file": Path(frame.filename).name, "function": frame.name, "line": frame.lineno}
                           for frame in traceback.extract_tb(error.__traceback__)]}
        print(json.dumps(safe), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
