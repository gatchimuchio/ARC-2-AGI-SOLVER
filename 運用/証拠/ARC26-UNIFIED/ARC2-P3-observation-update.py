"""A -> A+F batch-refit study using the current submission worker and policy.

For one fixed U/F pair per public-training task, predict [F.input, U.input]
from A, observe F.output, then refit from A+[F] and query the same two inputs.
U.output never enters either solver worker. Actual attempt_1/attempt_2 are
scored in the parent; prediction grids are not saved. This measures batch
refitting from a new observation, not persistent incremental learning.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT, ROOT / "HDS/学習系統/v0.4.2"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from 検証.全HDS第二候補LOO import _prior_examples  # noqa: E402

TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _encoded(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str,
                      separators=(",", ":")).encode("utf-8")


def _enum(value):
    return str(getattr(value, "value", value))


def _count_diagnostics(value: dict) -> dict:
    result = {}
    for key, item in value.items():
        if key == "repeated_panel_candidate_fit":
            if isinstance(item, dict):
                result[key] = {name: item[name] for name in
                               ("status", "failure", "teacher_count", "exact_teacher_count")
                               if name in item and isinstance(item[name], (str, int, float, bool))}
                if isinstance(item.get("candidate_models"), list):
                    result[key]["candidate_model_count"] = len(item["candidate_models"])
            continue
        if isinstance(item, (int, float, bool)):
            result[key] = item
        elif isinstance(item, dict) and all(isinstance(v, (int, float, bool)) for v in item.values()):
            result[key] = item
    return result


def _tree_fingerprint(folder: Path) -> dict:
    paths = sorted(folder.rglob("*.py"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(ROOT).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {"files": len(paths), "sha256": digest.hexdigest()}


def _semantic_state(machine) -> dict:
    rules = []
    for rule in machine._現行原理群():
        rules.append({
            "boundary": rule.対象系境界,
            "relation": rule.関係型,
            "conditions": rule.条件経路群,
            "result": rule.結果経路,
            "state": _enum(rule.状態),
            "adoption": _enum(rule.採用状態),
            "support_count": len(rule.根拠参照群),
            "counterexample_count": len(rule.反証参照群),
            "excluded_counterexample_count": len(rule.除外反証参照群),
            "mapping_sha256": _sha(_encoded([rule.対応表, rule.対応値表])),
        })
    rules.sort(key=lambda r: _encoded(r))
    return {
        "version": machine.状態.現在版,
        "experience_count": machine.台帳.件数("観測台帳"),
        "update_count": machine.台帳.件数("更新台帳"),
        "active_principle_count": len(machine._有効原理群()),
        "quarantined_principle_count": len(machine._係争中原理群()),
        "semantic_rule_sha256": _sha(_encoded(rules)),
        "semantic_rules": rules,
    }


def _worker() -> int:
    payload = json.load(sys.stdin)
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    os.environ["ARC2_AGGREGATE_DIAGNOSTICS"] = "1"
    from 接続.ARC2 import HDS接続 as hds
    from 接続.ARC2 import Kaggle提出 as submission

    hds.事前教材を読む = lambda: payload["prior"]
    base_type = hds.HDS学習実行系
    instances = []
    initial_states = []
    families = []

    class ObservedHDS(base_type):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)
            initial_states.append(_semantic_state(self))

    hds.HDS学習実行系 = ObservedHDS
    solve = hds.課題を解く

    def observed_solve(*args, **kwargs):
        result = solve(*args, **kwargs)
        for item in result.get("families", []):
            if isinstance(item, dict):
                families.append({
                    "boundary": item.get("境界"),
                    "prior_observations": item.get("事前観測数", 0),
                    "current_observations": item.get("現在観測数", 0),
                    "training_all_reproduced": bool(item.get("採用可")),
                    "equality_admitted": bool(item.get("同値採用")),
                    "status": item.get("状態"),
                })
        return result

    hds.課題を解く = observed_solve
    task = payload["task"]
    started = time.perf_counter()
    output = io.StringIO()
    with redirect_stdout(output):
        code = submission._worker(task)
    elapsed = time.perf_counter() - started
    try:
        raw = json.loads(output.getvalue())
    except json.JSONDecodeError:
        print(json.dumps({"state": "invalid_solver_output"}))
        return 0
    if code != 0 or raw.get("error"):
        print(json.dumps({"state": "solver_error", "error_type": raw.get("error")}))
        return 0
    predictions, audit = submission.結果を候補へ("analysis", task, raw)
    rows = raw.get("results", [])
    fallback = [not submission.格子か(row.get("answer")) for row in rows]
    response = {
        "state": "complete",
        "predictions": predictions,
        "primary_fallback": fallback,
        "fallback_reasons": [item.get("reason") for item in audit],
        "hds_initial_states": initial_states,
        "hds_final_states": [_semantic_state(machine) for machine in instances],
        "families": families,
        "aggregate_diagnostics": _count_diagnostics(raw.get("aggregate_diagnostics", {})),
        "solver_seconds": round(elapsed, 4),
    }
    print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def _call(task: dict, prior: list, timeout: float) -> dict:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    started = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            input=json.dumps({"task": task, "prior": prior}, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=ROOT, env=env, timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"state": "timeout", "timeout_seconds": timeout,
                "wall_seconds": round(time.perf_counter() - started, 4)}
    if result.returncode:
        return {"state": "worker_exit", "return_code": result.returncode}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"state": "invalid_worker_output"}
    value["wall_seconds"] = round(time.perf_counter() - started, 4)
    return value


def _score_pair(prediction: dict, expected: list, query: list,
                primary_fallback: bool) -> dict:
    a, b = prediction["attempt_1"], prediction["attempt_2"]
    pass1_raw = a == expected
    pass2_raw = pass1_raw or b == expected
    a_fallback = primary_fallback and a == query
    b_fallback = primary_fallback and b == query
    pass1 = pass1_raw and not a_fallback
    second_exact = b == expected and not b_fallback
    return {
        "pass1": pass1,
        "pass2": pass1 or second_exact,
        "second_incremental_exact": second_exact and not pass1,
        "raw_pass1": pass1_raw,
        "raw_pass2": pass2_raw,
        "input_copy_exact_excluded": (a_fallback and pass1_raw) or (b_fallback and b == expected),
        "primary_fallback": primary_fallback,
        "distinct_attempts": a != b,
        "prediction_sha256": _sha(_encoded(prediction)),
    }


def _summarize_result(raw: dict, feedback: dict, unseen: dict) -> dict:
    if raw.get("state") != "complete":
        return raw
    predictions = raw.pop("predictions")
    fallback = raw.pop("primary_fallback")
    if len(predictions) != 2 or len(fallback) != 2:
        return {"state": "result_count_mismatch"}
    # Targets are consulted only after the worker has returned.
    raw["feedback"] = _score_pair(predictions[0], feedback["output"], feedback["input"], fallback[0])
    raw["unseen"] = _score_pair(predictions[1], unseen["output"], unseen["input"], fallback[1])
    return raw


def run(task_count: int, seed: int, timeout: float, output: Path) -> dict:
    started_at_utc = datetime.now(timezone.utc).isoformat()
    if not output.is_absolute():
        output = (ROOT / output).resolve()
    training_raw = TRAINING.read_bytes()
    tasks = json.loads(training_raw.decode("utf-8"))
    eligible_ids = sorted(key for key, value in tasks.items() if len(value.get("train", [])) >= 5)
    rng = random.Random(seed)
    rng.shuffle(eligible_ids)
    selected = eligible_ids[:min(task_count, len(eligible_ids))]
    cohort = []
    for task_id in selected:
        n = len(tasks[task_id]["train"])
        unseen_index = rng.randrange(n)
        feedback_index = (unseen_index + 1) % n
        cohort.append({"task_id": task_id, "unseen_index": unseen_index,
                       "feedback_index": feedback_index, "training_pairs": n})
    prior, prior_ids = _prior_examples()
    source_paths = [
        Path(__file__).resolve(), ROOT / "接続/ARC2/HDS接続.py",
        ROOT / "接続/ARC2/Kaggle提出.py", ROOT / "検証/全HDS第二候補LOO.py",
        ROOT / "接続/ARC2/テンプレート充填教材.json",
    ]
    source_hashes = {path.relative_to(ROOT).as_posix(): _sha(path.read_bytes()) for path in source_paths}
    source_trees = {"arc2": _tree_fingerprint(ROOT / "接続/ARC2"),
                    "hds": _tree_fingerprint(ROOT / "HDS/学習系統/v0.4.2")}
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output.with_suffix(".summary.json")
    cohort_path = output.with_suffix(".cohort.json")
    if any(path.exists() for path in (output, summary_path, cohort_path)):
        raise FileExistsError(output)
    manifest = {
        "schema": "arc2-p3-observation-update-cohort-v1", "seed": seed,
        "training_sha256": _sha(training_raw), "eligible_tasks": len(eligible_ids),
        "selection": "shuffle sorted eligible IDs with fixed seed; one U per task; F=(U+1)%n",
        "task_id_role": "parent-only provenance and prior leakage exclusion; never solver input",
        "source_sha256": source_hashes,
        "source_trees": source_trees,
        "cohort": cohort,
    }
    # Cohort is frozen before any predictions are produced.
    cohort_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    rows = []
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({
            "record_type": "header", "schema": "arc2-p3-observation-update-v1",
            "started_at_utc": started_at_utc,
            "training_sha256": _sha(training_raw), "requested_tasks": len(cohort),
            "seed": seed, "timeout_seconds_per_worker": timeout,
            "cohort_manifest": cohort_path.relative_to(ROOT).as_posix(),
            "cohort_manifest_sha256": _sha(cohort_path.read_bytes()),
            "task_id_passed_to_worker": False, "unseen_target_passed_to_worker": False,
            "feedback_target_passed_before_observation": False,
            "same_test_inputs_and_order": True, "minimum_support_both_phases": 3,
            "selection_policy": "current Kaggle提出._worker then 結果を候補へ; actual two attempts",
            "learning_scope": "batch refit A -> A+F; no persistent incremental-state claim",
            "source_sha256": source_hashes,
            "source_trees": source_trees,
            "public_prior_examples_sha256": _sha(_encoded(prior)),
            "public_prior_examples": len(prior),
            "environment": {"python": sys.version, "numpy": importlib.metadata.version("numpy"),
                            "scipy": importlib.metadata.version("scipy")},
            "resource_limits": "per-worker wall timeout only; Windows CPU/RAM are not isolated",
        }, ensure_ascii=False) + "\n")
        stream.flush()
        for index, item in enumerate(cohort, start=1):
            task_id = item["task_id"]
            train = tasks[task_id]["train"]
            u, f = item["unseen_index"], item["feedback_index"]
            unseen, feedback = train[u], train[f]
            a = [pair for i, pair in enumerate(train) if i not in (u, f)]
            b = a + [feedback]
            tests = [{"input": feedback["input"]}, {"input": unseen["input"]}]
            task_prior = [] if task_id in prior_ids else prior
            before = _call({"train": a, "test": tests}, task_prior, timeout)
            # F.output is first sent to a solver only after the before call returns.
            after = _call({"train": b, "test": tests}, task_prior, timeout)
            before = _summarize_result(before, feedback, unseen)
            after = _summarize_result(after, feedback, unseen)
            complete = before.get("state") == after.get("state") == "complete"
            row = {
                "record_type": "task", "task_index": index,
                "support_before": len(a), "support_after": len(b),
                "prior_excluded_for_leakage": task_id in prior_ids,
                "before": before, "after": after,
                "paired_complete": complete,
                "unseen_pass2_recovery": complete and after["unseen"]["pass2"] and not before["unseen"]["pass2"],
                "unseen_pass2_regression": complete and before["unseen"]["pass2"] and not after["unseen"]["pass2"],
            }
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"task {index}/{len(cohort)}: before={before.get('state')}, after={after.get('state')}", flush=True)
    paired = [row for row in rows if row["paired_complete"]]
    def metric(phase: str, name: str, population: list) -> int:
        return sum(bool(row[phase].get("unseen", {}).get(name)) for row in population)
    summary = {
        "schema": "arc2-p3-observation-update-summary-v1",
        "started_at_utc": started_at_utc,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "records_path": output.relative_to(ROOT).as_posix(),
        "cohort_manifest": cohort_path.relative_to(ROOT).as_posix(),
        "training_sha256": _sha(training_raw), "seed": seed,
        "eligible_tasks": len(eligible_ids), "requested_tasks": len(cohort),
        "processed_tasks": len(rows), "completed_paired_tasks": len(paired),
        "incomplete_pairs": len(rows) - len(paired),
        "states_before": dict(Counter(row["before"].get("state") for row in rows)),
        "states_after": dict(Counter(row["after"].get("state") for row in rows)),
        "before_unseen_pass1": metric("before", "pass1", rows),
        "after_unseen_pass1": metric("after", "pass1", rows),
        "before_unseen_pass2": metric("before", "pass2", rows),
        "after_unseen_pass2": metric("after", "pass2", rows),
        "paired_before_unseen_pass2": metric("before", "pass2", paired),
        "paired_after_unseen_pass2": metric("after", "pass2", paired),
        "paired_recoveries": sum(row["unseen_pass2_recovery"] for row in paired),
        "paired_regressions": sum(row["unseen_pass2_regression"] for row in paired),
        "feedback_after_training_fit_pass2": sum(bool(row["after"].get("feedback", {}).get("pass2")) for row in rows),
        "unseen_target_passed_to_worker": False, "task_id_passed_to_worker": False,
        "fallback_counted_correct": False, "hidden_or_evaluation_solutions_read": False,
        "official_submission": False,
        "learning_scope": "same current solver and actual two-attempt policy, batch refit from one additional observed pair",
        "source_version_scope": "current local checkout; not automatically the frozen v61 Kaggle runner",
        "source_sha256": source_hashes,
        "source_trees": source_trees,
        "source_unchanged_at_end": (
            source_hashes == {path.relative_to(ROOT).as_posix(): _sha(path.read_bytes()) for path in source_paths}
            and source_trees == {"arc2": _tree_fingerprint(ROOT / "接続/ARC2"),
                                 "hds": _tree_fingerprint(ROOT / "HDS/学習系統/v0.4.2")}
        ),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--tasks", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20261026)
    parser.add_argument("--timeout-seconds", type=float, default=90)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.worker:
        return _worker()
    if args.tasks < 1:
        parser.error("--tasks must be positive")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "出力/検証" / f"ARC2-P3-observation-update-{stamp}.jsonl"
    run(args.tasks, args.seed, args.timeout_seconds, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
