"""Isolated candidate/HDS-admission comparison and A -> A+F batch refit.

No full submission worker, prior memory, or persistent update is exercised.
Heldout U targets exist only in the parent scorer. Default execution is a
20-task public-training study; --prepare-only freezes the cohort without fits.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MODULE = HERE / "feature_predicate_transform.py"
TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
ARMS = ("feature_neighbor", "feature_predicate")
PHASES = ("before", "after")
QUERY_ROLES = ("feedback", "unseen")
HDS_BASELINE_BOUNDARY = "ARC2公開隔離特徴近傍変換"
_BLOCKED_JSON = []
_ABSENT_NUMPY_METADATA = (ROOT / ".venv/Lib/site-packages/numpy-2.3.5.dist-info/direct_url.json").resolve()
_ABSENT_METADATA_PROBES = []


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def valid_grid(value):
    return (isinstance(value, list) and 1 <= len(value) <= 30
            and all(isinstance(row, list) and len(row) == len(value[0]) and 1 <= len(row) <= 30
                    and all(type(color) is int and 0 <= color <= 9 for color in row) for row in value))


def contains_grid(value):
    if valid_grid(value):
        return True
    if isinstance(value, dict):
        return any(contains_grid(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(contains_grid(item) for item in value)
    return False


def _load_module():
    spec = importlib.util.spec_from_file_location("arc2_feature_predicate_experiment", MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source_fingerprint():
    if _ABSENT_NUMPY_METADATA.exists():
        raise RuntimeError("reviewed NumPy metadata absence changed; JSON access is not authorized")
    paths = [Path(__file__), MODULE]
    for folder in (ROOT / "接続/ARC2", ROOT / "HDS/学習系統/v0.4.2"):
        paths.extend(folder.rglob("*.py"))
    paths = sorted(set(path.resolve() for path in paths))
    if not all(path.is_file() for path in paths):
        raise FileNotFoundError("experiment module must be finalized before cohort preparation")
    rows = [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path.read_bytes())} for path in paths]
    absence = {"path": _ABSENT_NUMPY_METADATA.relative_to(ROOT).as_posix(), "state": "ABSENT"}
    return {"sha256": sha(encoded({"sources": rows, "import_metadata_probe": absence})),
            "file_count": len(rows), "files": rows, "import_metadata_probe": absence}


def freeze_cohort(training, tasks, seed):
    """Eligibility and U/F choice use train count and input grids only."""
    eligible = []
    for task_id in sorted(training):
        pairs = training[task_id]["train"]
        if (6 <= len(pairs) <= 9 and all(valid_grid(pair.get("input")) for pair in pairs)
                and len({sha(encoded(pair["input"])) for pair in pairs}) == len(pairs)):
            eligible.append(task_id)
    if len(eligible) < tasks:
        raise ValueError(f"requested {tasks} unique tasks but only {len(eligible)} eligible")
    rng = random.Random(seed)
    selected = rng.sample(eligible, tasks)
    rows = []
    for index, task_id in enumerate(selected):
        pairs = training[task_id]["train"]
        unseen, feedback = rng.sample(range(len(pairs)), 2)
        support = [i for i in range(len(pairs)) if i not in (unseen, feedback)]
        rows.append({"index": index, "task_id": task_id, "support_indices": support,
                     "feedback_index": feedback, "unseen_index": unseen,
                     "query_roles": list(QUERY_ROLES),
                     "query_input_sha256": [sha(encoded(pairs[i]["input"])) for i in (feedback, unseen)],
                     "before_support": len(support), "after_support": len(support) + 1,
                     "arm_order": list(ARMS if index % 2 == 0 else reversed(ARMS))})
    return {"schema": "arc2-feature-predicate-public-cohort-v1", "seed": seed,
            "eligible_task_count": len(eligible), "tasks_requested": tasks,
            "selection_uses_targets": False, "candidate_feature_indices": list(range(25)), "rows": rows}


def make_payload(training, row, arm, phase, fingerprint):
    pairs = training[row["task_id"]]["train"]
    indices = list(row["support_indices"])
    if phase == "after":
        indices.append(row["feedback_index"])
    return {"arm": arm, "support": [deepcopy(pairs[index]) for index in indices],
            "queries": [{"input": deepcopy(pairs[index]["input"])} for index in
                        (row["feedback_index"], row["unseen_index"])],
            "source_sha256": fingerprint, "feature_indices": list(range(25))}


def validate_payload(payload):
    if set(payload) != {"arm", "support", "queries", "source_sha256", "feature_indices"} or payload["arm"] not in ARMS:
        raise ValueError("invalid worker payload")
    coordinates = payload["feature_indices"]
    if (not isinstance(coordinates, list) or not coordinates
            or any(type(index) is not int or not 0 <= index < 25 for index in coordinates)
            or coordinates != sorted(set(coordinates))):
        raise ValueError("invalid fixed candidate feature grammar")
    support, queries = payload["support"], payload["queries"]
    if not isinstance(support, list) or not 4 <= len(support) <= 8:
        raise ValueError("both phases require four to eight support examples")
    if any(set(pair) != {"input", "output"} or not valid_grid(pair["input"])
           or not valid_grid(pair["output"]) for pair in support):
        raise ValueError("invalid current public training support")
    if len(queries) != 2 or any(set(pair) != {"input"} or not valid_grid(pair["input"]) for pair in queries):
        raise ValueError("query targets and identifiers are forbidden")
    if len({sha(encoded(pair["input"])) for pair in support}) != len(support):
        raise ValueError("support inputs must be distinct")


def count_diagnostics(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, item in value.items():
        if isinstance(item, (int, float, bool)) or item is None:
            result[str(key)] = item
        elif isinstance(item, str) and len(item) <= 160:
            result[str(key)] = item
        elif isinstance(item, dict) and all(type(v) in (int, float, bool) for v in item.values()):
            result[str(key)] = item
    return result


def semantic_state(machine):
    rules = []
    for rule in machine._現行原理群():
        enum = lambda value: str(getattr(value, "value", value))
        rules.append({"boundary": rule.対象系境界, "relation": rule.関係型,
                      "conditions": rule.条件経路群, "result": rule.結果経路,
                      "state": enum(rule.状態), "adoption": enum(rule.採用状態),
                      "support_count": len(rule.根拠参照群),
                      "counterexample_count": len(rule.反証参照群),
                      "mapping_sha256": sha(encoded([rule.対応表, rule.対応値表]))})
    rules.sort(key=encoded)
    return {"semantic_rule_sha256": sha(encoded(rules)), "semantic_rules": rules,
            "experience_count": machine.台帳.件数("観測台帳"),
            "update_count": machine.台帳.件数("更新台帳"),
            "active_principle_count": len(machine._有効原理群()),
            "quarantined_principle_count": len(machine._係争中原理群())}


def model_state(model, arm):
    if arm == "feature_predicate":
        state = model.model_state()
    else:
        state = {"type": "FeatureNeighborTransform", "training_examples": len(model.teachers),
                 "features": model.features, "models": model.models,
                 "applicability_limit": model.applicability_limit}
    if contains_grid(state):
        raise ValueError("model state contains a raw integer grid; evidence export refused")
    return {"sha256": sha(encoded(state)), "typed_state": state}


def worker():
    payload = json.load(sys.stdin)
    validate_payload(payload)
    if source_fingerprint()["sha256"] != payload["source_sha256"]:
        raise ValueError("source changed before worker")
    # No worker may open public datasets, memory JSON, or persisted answer files.
    def guard(event, arguments):
        if event == "open" and isinstance(arguments[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(arguments[0]))
            if path.suffix.lower() in (".json", ".jsonl"):
                if path.resolve() == _ABSENT_NUMPY_METADATA and not path.exists():
                    _ABSENT_METADATA_PROBES.append(_ABSENT_NUMPY_METADATA.relative_to(ROOT).as_posix())
                    raise FileNotFoundError(str(_ABSENT_NUMPY_METADATA))  # Never permit the underlying open.
                _BLOCKED_JSON.append(path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name)
                raise RuntimeError("experiment worker JSON file access forbidden")
    sys.addaudithook(guard)
    for path in (ROOT, ROOT / "HDS/学習系統/v0.4.2"):
        sys.path.insert(0, str(path))
    from 接続.ARC2 import HDS接続 as hds
    from 接続.ARC2.特徴近傍変換選択 import FeatureNeighborTransform
    module = _load_module()
    support, arm = deepcopy(payload["support"]), payload["arm"]
    immutable_support_hash = sha(encoded(support))
    started, cpu_started = time.perf_counter(), time.process_time()
    captured = io.StringIO()
    with redirect_stdout(captured):
        model = (FeatureNeighborTransform(support) if arm == "feature_neighbor"
                 else module.FeaturePredicateTransform(support, feature_indices=tuple(payload["feature_indices"])))
        fitted_state = model_state(model, arm)
        machine = module.new_hds_machine()
        initial = semantic_state(machine)
        if arm == "feature_predicate":
            admission = model.admit_to_hds(machine, support)
        else:
            admission = hds.候補機構を学習(machine, {"train": support}, [],
                                      HDS_BASELINE_BOUNDARY, model.候補)
        admitted_state = semantic_state(machine)
        rows = []
        for query in payload["queries"]:
            grid = deepcopy(query["input"])
            direct, diagnostic = model.候補(grid, {})
            if not (admission.get("採用可") and admission.get("同値採用")):
                result = {"answer": None, "status": "training_admission_hold",
                          "reasons": ["current_training_not_fully_admitted"], "hds_queried": False}
            elif arm == "feature_predicate":
                result = model.query_via_hds(machine, deepcopy(grid))
            elif direct is not None:
                result = hds.出力格子(machine, hds.観測へ({"候補": direct}, HDS_BASELINE_BOUNDARY),
                                     同値必須=True, 観測診断=True)
                result["hds_queried"] = True
            else:
                result = {"answer": None, "status": "candidate_hold", "hds_queried": False}
            rows.append({"direct": direct if valid_grid(direct) else None,
                         "hds": result.get("answer") if valid_grid(result.get("answer")) else None,
                         "direct_diagnostic": count_diagnostics(diagnostic),
                         "hds_status": str(result.get("status", "unknown")),
                         "hds_queried": bool(result.get("hds_queried")),
                         "equality_admitted": bool(result.get("equality_admitted")),
                         "hds_observation_requests": count_diagnostics(result.get("observation_request_counts", {}))})
        final_model = model_state(model, arm)
        final = semantic_state(machine)
    if sha(encoded(support)) != immutable_support_hash:
        raise ValueError("candidate mutated current public support")
    response = {"state": "complete", "rows": rows,
                "effective_feature_indices": list(range(25)) if arm == "feature_neighbor" else payload["feature_indices"],
                "admission": count_diagnostics(admission), "model_fitted": fitted_state,
                "model_final": final_model, "model_unchanged_after_query": fitted_state == final_model,
                "hds_initial": initial, "hds_admitted": admitted_state, "hds_final": final,
                "hds_semantics_unchanged_after_query": admitted_state == final,
                "solver_seconds": round(time.perf_counter() - started, 6),
                "process_cpu_seconds": round(time.process_time() - cpu_started, 6),
                "unexpected_stdout_sha256": sha(captured.getvalue().encode("utf-8")),
                "absent_import_metadata_probes": {"path": _ABSENT_NUMPY_METADATA.relative_to(ROOT).as_posix(),
                                                  "state": "ABSENT", "probe_count": len(_ABSENT_METADATA_PROBES),
                                                  "content_reads": 0},
                "source_sha256": payload["source_sha256"]}
    print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def invoke(payload, timeout):
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    started = time.perf_counter()
    try:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--worker"],
                                input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout,
                                cwd=ROOT, env=env, check=False)
        if result.returncode:
            value = {"state": "worker_exit", "return_code": result.returncode,
                     "stderr_sha256": sha(result.stderr.encode("utf-8"))}
        else:
            try:
                value = json.loads(result.stdout)
            except json.JSONDecodeError:
                value = {"state": "invalid_worker_output"}
    except subprocess.TimeoutExpired:
        value = {"state": "timeout", "timeout_seconds": timeout}
    if not isinstance(value, dict):
        value = {"state": "invalid_worker_output"}
    value["wall_seconds"] = round(time.perf_counter() - started, 6)
    if value.get("state") == "complete" and (not isinstance(value.get("rows"), list)
                                              or len(value["rows"]) != 2
                                              or any(not isinstance(row, dict) for row in value["rows"])):
        value = {"state": "invalid_worker_row_count", "wall_seconds": value["wall_seconds"]}
    return value


def score_result(result, expected):
    """Failures retain every requested query in the scoring denominator."""
    scored, safe = [], deepcopy(result)
    for index, target in enumerate(expected):
        row = result.get("rows", [])[index] if result.get("state") == "complete" else {}
        scored.append({kind + "_exact": bool(valid_grid(row.get(kind)) and row[kind] == target)
                       for kind in ("direct", "hds")}
                      | {kind + "_prediction_sha256": sha(encoded(row.get(kind))) for kind in ("direct", "hds")}
                      | {kind + "_abstain_or_failure": not valid_grid(row.get(kind)) for kind in ("direct", "hds")}
                      | {"complete": result.get("state") == "complete", "query_role": QUERY_ROLES[index]})
    for row in safe.get("rows", []):
        row.pop("direct", None)
        row.pop("hds", None)
    if contains_grid(safe):
        raise ValueError("raw grid escaped into evidence")
    return scored, safe


def summarize(records, requested):
    totals = {}
    for arm in ARMS:
        totals[arm] = {}
        for role in QUERY_ROLES:
            entry = {}
            for phase in PHASES:
                results = [record["results"][arm][phase] for record in records]
                scores = [result["scores"][QUERY_ROLES.index(role)] for result in results]
                entry[phase] = {"requested": requested, "scored_tasks": len(scores),
                                "complete": sum(score["complete"] for score in scores),
                                **{kind + "_exact": sum(score[kind + "_exact"] for score in scores)
                                   for kind in ("direct", "hds")}}
            for kind in ("direct", "hds"):
                comparisons = [(record["results"][arm]["before"]["scores"][QUERY_ROLES.index(role)][kind + "_exact"],
                                record["results"][arm]["after"]["scores"][QUERY_ROLES.index(role)][kind + "_exact"])
                               for record in records]
                entry[kind + "_delta"] = entry["after"][kind + "_exact"] - entry["before"][kind + "_exact"]
                entry[kind + "_gains"] = sum(not a and b for a, b in comparisons)
                entry[kind + "_regressions"] = sum(a and not b for a, b in comparisons)
            totals[arm][role] = entry
        totals[arm]["states"] = dict(Counter(record["results"][arm][phase]["evidence"]["state"]
                                             for record in records for phase in PHASES))
        pairs = [(record["results"][arm]["before"], record["results"][arm]["after"]) for record in records]
        completed = [(a, b) for a, b in pairs if a["evidence"]["state"] == b["evidence"]["state"] == "complete"]
        totals[arm]["paired_evidence"] = {
            "requested": requested, "both_complete": len(completed),
            "model_state_changed": sum(a["evidence"]["model_fitted"]["sha256"] != b["evidence"]["model_fitted"]["sha256"]
                                       for a, b in completed),
            "hds_admitted_semantic_state_changed": sum(a["evidence"]["hds_admitted"]["semantic_rule_sha256"]
                                                        != b["evidence"]["hds_admitted"]["semantic_rule_sha256"]
                                                        for a, b in completed),
            **{kind + "_unseen_prediction_changed": sum(a["scores"][1][kind + "_prediction_sha256"]
                                                          != b["scores"][1][kind + "_prediction_sha256"]
                                                          for a, b in completed) for kind in ("direct", "hds")},
            "model_query_mutations": sum(not part["evidence"].get("model_unchanged_after_query", True)
                                         for pair in completed for part in pair),
            "hds_query_semantic_mutations": sum(not part["evidence"].get("hds_semantics_unchanged_after_query", True)
                                               for pair in completed for part in pair),
        }
    for phase in PHASES:
        for kind in ("direct", "hds"):
            comparisons = [(record["results"][ARMS[0]][phase]["scores"][1][kind + "_exact"],
                            record["results"][ARMS[1]][phase]["scores"][1][kind + "_exact"])
                           for record in records]
            totals.setdefault("candidate_vs_old_selector_unseen", {})[phase + "_" + kind] = {
                "previous": sum(a for a, _ in comparisons), "current": sum(b for _, b in comparisons),
                "delta": sum(int(b) - int(a) for a, b in comparisons),
                "gains": sum(not a and b for a, b in comparisons),
                "regressions": sum(a and not b for a, b in comparisons), "requested": requested,
                "new_correct_old_wrong": sum(not a and b for a, b in comparisons),
                "hypothetical_two_candidate_union_exact": sum(a or b for a, b in comparisons),
                "union_scope": "candidate-family complementarity only; not full submission-policy evidence"}
    return totals


def run(args):
    module_sha = sha(MODULE.read_bytes())
    if not args.prepare_only and not args.expected_module_sha256:
        raise ValueError("actual study requires explicit --expected-module-sha256")
    if args.expected_module_sha256 and module_sha != args.expected_module_sha256:
        raise ValueError("experimental module differs from reviewed SHA")
    sources = source_fingerprint()
    training_bytes = TRAINING.read_bytes()
    training = json.loads(training_bytes)
    cohort = freeze_cohort(training, args.tasks, args.seed)
    cohort.update(source_sha256=sources["sha256"], training_file_sha256=sha(training_bytes),
                  timeout_seconds=args.timeout_seconds)
    cohort_bytes = encoded(cohort) + b"\n"
    if args.expected_cohort_sha256 and sha(cohort_bytes) != args.expected_cohort_sha256:
        raise ValueError("cohort differs from reviewed pre-result cohort")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    cohort_path = output.with_suffix(".cohort.json")
    if output.exists() or cohort_path.exists() or output.with_suffix(".summary.json").exists():
        raise FileExistsError("refuse to overwrite prior study/cohort evidence")
    cohort_path.write_bytes(cohort_bytes)
    if args.prepare_only:
        return {"state": "cohort_frozen_no_solver_execution", "cohort": str(cohort_path),
                "cohort_sha256": sha(cohort_path.read_bytes()), "sources": sources}
    records = []
    with output.open("x", encoding="utf-8") as stream:
        for row in cohort["rows"]:
            results = {arm: {} for arm in ARMS}
            # F target is observed only for after-phase support. U target is never sent.
            raw = {arm: {} for arm in ARMS}
            for phase in PHASES:
                for arm in row["arm_order"]:
                    raw[arm][phase] = invoke(make_payload(training, row, arm, phase, sources["sha256"]), args.timeout_seconds)
            pairs = training[row["task_id"]]["train"]
            expected = [pairs[index]["output"] for index in (row["feedback_index"], row["unseen_index"])]
            for arm in ARMS:
                for phase in PHASES:
                    scores, safe = score_result(raw[arm][phase], expected)
                    results[arm][phase] = {"scores": scores, "evidence": safe}
            record = {"cohort_index": row["index"], "task_id": row["task_id"], "results": results}
            records.append(record)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            print(json.dumps({"completed_tasks": len(records), "requested_tasks": args.tasks,
                              "states": {arm: {phase: results[arm][phase]["evidence"]["state"] for phase in PHASES}
                                         for arm in ARMS}}), flush=True)
    final_sources = source_fingerprint()
    summary = {"schema": "arc2-feature-predicate-public-study-v1", "state": "COMPLETE",
               "completed_at": datetime.now(timezone.utc).isoformat(), "requested_tasks": args.tasks,
               "requested_queries_per_arm_phase": args.tasks * 2, "cohort_sha256": sha(cohort_path.read_bytes()),
               "source_unchanged": sources == final_sources, "sources": sources,
               "training_file_sha256": sha(training_bytes), "output_sha256": sha(output.read_bytes()),
               "python": sys.version, "platform": platform.platform(),
               "resources": {"process_wall_limit_seconds": args.timeout_seconds,
                             "cpu_ram_hard_limits": False, "fresh_process_per_arm_phase": True},
               "scope": "isolated generator refit plus actual HDS admission/query; no full submission or persistent incremental learner",
               "feedback_after_is_training_fit": True, "unseen_target_worker_access": False,
               "prior_memory": "none; JSON/JSONL content access denied; exact absent NumPy direct_url.json probe receives FileNotFoundError",
               "import_metadata_probe_at_start": sources["import_metadata_probe"],
               "import_metadata_probe_at_end": final_sources["import_metadata_probe"],
               "metrics": summarize(records, args.tasks), "adoption": "UNDECIDED_REQUIRES_REVIEW"}
    output.with_suffix(".summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--tasks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261026)
    parser.add_argument("--timeout-seconds", type=float, default=90)
    parser.add_argument("--expected-module-sha256")
    parser.add_argument("--expected-cohort-sha256")
    parser.add_argument("--output", type=Path, default=HERE / "public_results/study.jsonl")
    args = parser.parse_args()
    if args.worker:
        try:
            return worker()
        except Exception as error:
            frames = [{"file": Path(frame.filename).name, "line": frame.lineno, "function": frame.name}
                      for frame in traceback.extract_tb(error.__traceback__)]
            print(json.dumps({"state": "worker_error", "error_type": type(error).__name__,
                              "frames": frames, "blocked_json": _BLOCKED_JSON}))
            return 0
    if args.tasks <= 0 or args.timeout_seconds <= 0:
        parser.error("tasks and timeout must be positive")
    print(json.dumps(run(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
