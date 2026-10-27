"""Read-only trace of complete root candidates retained before the reviewed fit cap."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MODULE = HERE / "cell_conditional_tree.py"
FIT_HARNESS = HERE / "prune_fit_diagnosis.py"
PREPARATION = HERE / "fit_results/leaf1-fit-six-phases-20261027T0221Z.summary.json"
UNTRACED = HERE / "fit_results/leaf1-fit-six-phases-20261027T0221Z.jsonl"
OLD_ROOT = HERE.with_name("ARC2-cell-conditional-tree-rowcol")
STUDY = OLD_ROOT / "public_results/study20-20261027T0005Z.jsonl"
COHORT = OLD_ROOT / "public_results/study20-20261027T0005Z.cohort.json"
TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
MODULE_SHA256 = "66a5b525e42881ae35b2a125c7a8f85628a8cce9b95179fdd89c62b38b7e22d6"
EXPECTED_STUDY_SHA256 = "7de648df8fd18656ba55bc86e4949db4ee88b571fe795e63d7c3817aae79c526"
EXPECTED_COHORT_SHA256 = "f4ccbe47c84d0807f61a246d4622e3d46d5580e086bcb6d346195d06f84be5ba"
EXPECTED_PREPARATION_SHA256 = "0ba0b5963b3669374217c726edd48370337bd9becf0dfb557756fcbcf0dea781"
EXPECTED_UNTRACED_SHA256 = "73d5db77ded9829c80c11b807426ddd41fa4650dfd24c599f665a339bea4d28f"
EXPECTED_UNTRACED_WORKTREE_SHA256 = "207ecb33b952cfcde1e29de0c605432bc9b322380abbd31600f720b3c4d79200"
SUMMARY_FIELDS = ("status", "training_examples", "distinct_training_examples", "training_cells",
                  "fit_states", "work_units", "training_replayed")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_git_text(data: bytes) -> str:
    """Hash the LF form stored by this repository's text-file attributes."""
    return sha(data.replace(b"\r\n", b"\n"))


def encoded(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("module spec unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def root_trace(module, constructor, support):
    captured = {"event": None, "best": None, "alternatives": [], "exception_type": None, "exception": None}
    root_frame_id = None

    def tracer(frame, event, argument):
        nonlocal root_frame_id
        if event == "call" and frame.f_code.co_name == "fit" and frame.f_locals.get("depth") == 0:
            indices = frame.f_locals.get("indices")
            records = frame.f_locals.get("records")
            if isinstance(indices, tuple) and (records is None or indices == tuple(range(len(records)))):
                root_frame_id = id(frame)
                return tracer
            return None
        if root_frame_id == id(frame) and event in ("exception", "return") and captured["event"] is None:
            local = frame.f_locals
            best = local.get("best")
            alternatives = local.get("alternatives", [])
            captured.update(
                event=event,
                best=list(best) if best is not None else None,
                alternatives=deepcopy(alternatives) if isinstance(alternatives, list) else [],
            )
            if event == "exception" and isinstance(argument, tuple) and len(argument) >= 2:
                captured["exception_type"] = getattr(argument[0], "__name__", type(argument[0]).__name__)
                captured["exception"] = str(argument[1])[:120]
        return tracer if root_frame_id == id(frame) else None

    sys.settrace(tracer)
    try:
        model = constructor()
    finally:
        sys.settrace(None)
    return model, captured


def replay(module, forest, support):
    checked = mismatches = 0
    try:
        for pair in support:
            targets = [value for row in pair["output"] for value in row]
            for (features, roles), target in zip(module._input_cells(pair["input"]), targets, strict=True):
                checked += 1
                if module._evaluate(forest, features, roles) != target:
                    mismatches += 1
        return {"cells_checked": checked, "mismatches": mismatches, "consistent": mismatches == 0,
                "hold_reason": None}
    except module._Hold as error:
        return {"cells_checked": checked, "mismatches": None, "consistent": False,
                "hold_reason": str(error)[:120]}


def install_read_guard(root: Path):
    absent = root / ".venv/Lib/site-packages/numpy-2.3.5.dist-info/direct_url.json"
    probes = []

    def guard(event, arguments):
        if event == "open" and arguments and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0]))
            if path.suffix.lower() in (".json", ".jsonl"):
                if path.resolve() == absent.resolve() and not path.exists():
                    probes.append(True)
                    raise FileNotFoundError("reviewed absent package metadata")
                raise RuntimeError("FIT trace worker JSON reads forbidden")

    sys.addaudithook(guard)
    return probes


def worker(payload):
    fit = load_module(FIT_HARNESS, "arc2_leaf_fit_harness_for_root_trace")
    sources = fit.fingerprint()
    if sources["sha256"] != payload["expected_source_sha256"]:
        raise ValueError("reviewed source fingerprint changed")
    if sha(MODULE.read_bytes()) != MODULE_SHA256 or payload["module_sha256"] != MODULE_SHA256:
        raise ValueError("tree module pin mismatch")
    data = payload["payload"]
    fit.validate_payload(data, "pruned_fit")
    if sha(encoded(data)) != payload["payload_sha256"]:
        raise ValueError("input DTO digest mismatch")
    probes = install_read_guard(ROOT)
    sys.path.insert(0, str(ROOT))
    module = load_module(MODULE, "arc2_leaf_min1_root_trace_worker")
    if sha(MODULE.read_bytes()) != MODULE_SHA256 or len(module.FEATURES) != 35 or len(module.PROGRAMS) != 21:
        raise ValueError("reviewed candidate grammar changed")
    expected_bounds = dict(fit.FIT_BOUNDS)
    if data["bounds"] != expected_bounds or module.Bounds().__dict__ != fit.EXPECTED_MODULE_DEFAULT_BOUNDS:
        raise ValueError("bounds changed")

    def no_hds():
        raise RuntimeError("HDS is outside this fit-only trace")

    module._connection = no_hds
    origins_before = fit.runtime_origins(sources, module)
    started = time.perf_counter()
    model, capture = root_trace(
        module,
        lambda: module.CellConditionalTree(deepcopy(data["support"]), bounds=module.Bounds(**data["bounds"])),
        data["support"],
    )
    elapsed = round(time.perf_counter() - started, 6)
    best = capture["best"]
    alternatives = capture["alternatives"]
    forest = {"cost": best, "choices": alternatives} if best is not None and alternatives else None
    forest_replay = replay(module, forest, data["support"]) if forest else None
    individual = [replay(module, {"cost": best, "choices": [tree]}, data["support"])
                  for tree in alternatives] if best is not None else []
    result = {
        "state": "complete", "payload_sha256": payload["payload_sha256"],
        "status": model.status, "fit_states": model.fit_states, "work_units": model.work_units,
        "training_examples": model.training_examples, "distinct_training_examples": model.distinct_training_examples,
        "training_cells": model.training_cells, "training_replayed": model.training_replayed,
        "root_terminal_event": capture["event"], "root_exception_type": capture["exception_type"],
        "root_exception": capture["exception"], "root_cost": best,
        "retained_complete_root_candidate_count": len(alternatives),
        "retained_root_forest_sha256": sha(encoded(forest)) if forest else None,
        "retained_root_forest_training_replay": forest_replay,
        "individual_candidate_training_consistency": [row["consistent"] for row in individual],
        "trace_elapsed_seconds": elapsed, "timing_comparable": False,
        "external_query_calls": 0, "hds_calls": 0, "scoring_calls": 0,
        "json_content_opens": 0, "absent_numpy_metadata_probe_count": len(probes),
        "runtime_origins_before": origins_before,
        "runtime_origins_after": fit.runtime_origins(sources, module),
        "raw_grids_saved": False,
    }
    if model.status not in {"fit_state_budget_exceeded", "work_budget_exceeded", "alternative_budget_exceeded", "no_exact_bounded_tree"}:
        raise ValueError("unexpected case status")
    if model.fit_states > fit.FIT_BOUNDS["max_fit_states"] + 1 or model.work_units > fit.FIT_BOUNDS["max_work_units"]:
        raise ValueError("fit cap changed")
    if capture["event"] not in {"exception", "return"}:
        raise ValueError("root fit frame was not observed")
    if forest_replay and (forest_replay["cells_checked"] != model.training_cells or not forest_replay["consistent"]):
        raise ValueError("retained complete forest fails current-teacher replay")
    return result


def synthetic_control(script_path: Path, expected_source: str):
    fixture = {
        "mode": "synthetic_control", "expected_source_sha256": expected_source,
        "module_sha256": MODULE_SHA256, "trace_script_sha256": sha(script_path.read_bytes()),
    }
    completed = subprocess.run(
        [sys.executable, str(script_path), "--worker"], input=json.dumps(fixture),
        capture_output=True, text=True, encoding="utf-8", timeout=90,
        cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )
    result = json.loads(completed.stdout) if completed.returncode == 0 else {"state": "worker_exit", "returncode": completed.returncode, "stderr_sha256": sha(completed.stderr.encode())}
    if result.get("state") != "complete" or not result.get("status_work_state_equal") or not result.get("forest_equal"):
        raise RuntimeError("synthetic trace passivity control failed")
    return result


def run_worker_mode(script_path: Path):
    request = json.load(sys.stdin)
    if request.get("mode") == "synthetic_control":
        fit = load_module(FIT_HARNESS, "arc2_leaf_fit_harness_for_synthetic_control")
        if fit.fingerprint()["sha256"] != request["expected_source_sha256"]:
            raise ValueError("reviewed source fingerprint changed")
        if sha_git_text(script_path.read_bytes()) != request["trace_script_sha256"] or sha(MODULE.read_bytes()) != MODULE_SHA256:
            raise ValueError("synthetic trace source pin mismatch")
        probes = install_read_guard(ROOT)
        sys.path.insert(0, str(ROOT))
        module = load_module(MODULE, "arc2_leaf_min1_root_trace_synthetic")
        if len(module.FEATURES) != 35 or len(module.PROGRAMS) != 21:
            raise ValueError("synthetic grammar mismatch")
        module._connection = lambda: (_ for _ in ()).throw(RuntimeError("HDS forbidden"))
        support = [
            {"input": [[0, value, value], [0, 0, 0]],
             "output": [[0, 6 if value == 1 else value, 6 if value == 1 else value], [0, 0, 0]]}
            for value in (1, 2, 3)
        ]
        bounds = dict(fit.FIT_BOUNDS)
        bounds.update(max_fit_states=4096, max_work_units=32_000_000, max_alternatives=128, minimum_leaf_teacher_support=1)
        feature_indices = (module.FEATURES.index("context_4"),)
        traced, capture = root_trace(module, lambda: module.CellConditionalTree(deepcopy(support), bounds=module.Bounds(**bounds), feature_indices=feature_indices), support)
        untraced = module.CellConditionalTree(deepcopy(support), bounds=module.Bounds(**bounds), feature_indices=feature_indices)
        result = {"state": "complete", "status_work_state_equal": (traced.status, traced.fit_states, traced.work_units, traced.training_replayed) == (untraced.status, untraced.fit_states, untraced.work_units, untraced.training_replayed),
                  "forest_equal": traced.forest == untraced.forest, "status": traced.status,
                  "fit_states": traced.fit_states, "work_units": traced.work_units,
                  "root_terminal_event": capture["event"], "retained_complete_root_candidate_count": len(capture["alternatives"]),
                  "retained_root_forest_training_replay": replay(module, {"cost": capture["best"], "choices": capture["alternatives"]}, support) if capture["best"] is not None and capture["alternatives"] else None,
                  "json_content_opens": 0, "absent_numpy_metadata_probe_count": len(probes), "raw_grids_saved": False}
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return result
    if request.get("trace_script_sha256") != sha_git_text(script_path.read_bytes()):
        raise ValueError("trace script hash mismatch")
    result = worker(request)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


def run_parent(output: Path):
    fit = load_module(FIT_HARNESS, "arc2_leaf_fit_harness_for_root_trace_parent")
    sources = fit.fingerprint()
    preparation = json.loads(PREPARATION.read_bytes())
    study_bytes, cohort_bytes, training_bytes = STUDY.read_bytes(), COHORT.read_bytes(), TRAINING.read_bytes()
    if sha_git_text(study_bytes) != EXPECTED_STUDY_SHA256 or sha_git_text(cohort_bytes) != EXPECTED_COHORT_SHA256:
        raise ValueError("reviewed public study/cohort hashes changed")
    preparation_bytes, untraced_bytes = PREPARATION.read_bytes(), UNTRACED.read_bytes()
    if sha_git_text(preparation_bytes) != EXPECTED_PREPARATION_SHA256 or sha_git_text(untraced_bytes) != EXPECTED_UNTRACED_SHA256:
        raise ValueError("reviewed leaf1 preparation/output repository hashes changed")
    cohort = json.loads(cohort_bytes)
    if sha(training_bytes) != cohort["training_file_sha256"]:
        raise ValueError("public training differs from the reviewed cohort")
    if sha(encoded(sources)) != sha(encoded(preparation["sources"])):
        raise ValueError("frozen runtime sources differ from the reviewed preparation")
    if preparation["state"] != "FIT_DIAGNOSIS_COMPLETE" or preparation["output_sha256"] != EXPECTED_UNTRACED_WORKTREE_SHA256:
        raise ValueError("leaf1 FIT evidence is not terminal or hash-pinned")
    training = json.loads(training_bytes)
    rows = {row["index"]: row for row in cohort["rows"]}
    previous = {}
    for line in UNTRACED.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            previous[(row["cohort_index"], row["phase"])] = row["pruned_fit"]["fit"]
    script_path = Path(__file__).resolve()
    trace_script_sha = sha_git_text(script_path.read_bytes())
    records = []
    expected_payload_hashes = []
    for case in preparation["cases"]:
        payload = fit.make_payload(training, rows[case["cohort_index"]], case["phase"], fit.FIT_BOUNDS)
        payload_hash = sha(fit.encoded(payload))
        if payload_hash != case["current_support_payload_sha256"]:
            raise ValueError("six guarded support DTO changed")
        expected_payload_hashes.append(payload_hash)
        request = {"payload": payload, "payload_sha256": payload_hash,
                   "expected_source_sha256": sources["sha256"], "module_sha256": MODULE_SHA256,
                   "trace_script_sha256": trace_script_sha}
        completed = subprocess.run(
            [sys.executable, str(script_path), "--worker"], input=json.dumps(request, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", timeout=90,
            cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        )
        if completed.returncode != 0:
            safe_tail = " | ".join(completed.stderr.splitlines()[-4:])[:500]
            raise RuntimeError("trace worker failed: " + str(completed.returncode) + ":" + safe_tail)
        result = json.loads(completed.stdout)
        baseline = previous[(case["cohort_index"], case["phase"])]
        equality = all(result.get(field) == baseline.get(field) for field in SUMMARY_FIELDS)
        result.update(cohort_index=case["cohort_index"], phase=case["phase"],
                      untraced_status_work_state_equal=equality,
                      source_sha256=sources["sha256"], support_payload_sha256=payload_hash)
        if not equality:
            raise RuntimeError("trace changed fit status/counters")
        records.append(result)
        print(json.dumps({"completed_phases": len(records), "selected_phases": len(preparation["cases"]),
                          "cohort_index": case["cohort_index"], "phase": case["phase"],
                          "fit_status": result["status"], "retained_roots": result["retained_complete_root_candidate_count"]}), flush=True)
    synthetic = synthetic_control(script_path, sources["sha256"])
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() or output.with_suffix(".summary.json").exists():
        raise FileExistsError("refuse to overwrite root trace output")
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    summary = {
        "schema": "arc2-fit-root-retention-trace-v1", "track": "ARC2",
        "status": "COMPLETE", "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "trace_script_sha256": trace_script_sha,
        "trace_script_execution_worktree_sha256": sha(script_path.read_bytes()),
        "module_sha256": MODULE_SHA256,
        "source_sha256": sources["sha256"], "study_sha256": EXPECTED_STUDY_SHA256,
        "study_execution_worktree_sha256": sha(study_bytes),
        "cohort_sha256": EXPECTED_COHORT_SHA256, "training_sha256": sha(training_bytes),
        "preparation_sha256": EXPECTED_PREPARATION_SHA256,
        "preparation_execution_worktree_sha256": sha(preparation_bytes),
        "untraced_records_sha256": EXPECTED_UNTRACED_SHA256,
        "untraced_records_execution_worktree_sha256": sha(untraced_bytes),
        "text_hash_policy": "Repository text hashes use LF-normalized bytes; execution worktree hashes preserve the original CRLF observation.",
        "selected_phases": len(records), "support_payload_sha256s": expected_payload_hashes,
        "all_traced_status_work_state_match_untraced": all(row["untraced_status_work_state_equal"] for row in records),
        "retained_complete_root_candidates_total": sum(row["retained_complete_root_candidate_count"] for row in records),
        "training_consistent_retained_candidates_total": sum(sum(row["individual_candidate_training_consistency"]) for row in records),
        "trace_times_comparable": False, "synthetic_passivity_control": synthetic,
        "heldout_queries": 0, "hds_calls": 0, "scoring_calls": 0,
        "raw_grids_saved": False, "official_score_claimed": False,
        "rows_path": output.relative_to(ROOT).as_posix(), "rows_sha256": sha(output.read_bytes()),
    }
    with output.with_suffix(".summary.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"state": "COMPLETE", "phases": len(records),
                      "retained_root_candidates": summary["retained_complete_root_candidates_total"],
                      "output_sha256": summary["rows_sha256"], "synthetic_passivity": synthetic["status_work_state_equal"]}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--output", type=Path, default=HERE / "fit_results/root-retention-trace-20261027T0247Z.jsonl")
    args = parser.parse_args()
    if args.worker:
        run_worker_mode(Path(__file__).resolve())
    else:
        run_parent(args.output.resolve())


if __name__ == "__main__":
    main()
