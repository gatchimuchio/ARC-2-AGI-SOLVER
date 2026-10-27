"""Inspect HDS observation-request paths on a public ARC2 solver-HOLD sample.

Only public training pairs and challenge inputs enter the workers. No solutions
are loaded; each subprocess returns aggregate counters without task IDs or grids.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
AUDIT = ROOT / "出力/Kaggle/arc2-current-main-baseline-240-20261027T1348Z/submission_audit.json"
OUTPUT = Path(__file__).with_suffix(".json")
EXPECTED_CHALLENGE_SHA256 = "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83"
EXPECTED_PREDICTION_SHA256 = "54f6a303c4143f15279e2084d5ad798455e565b4d51cd6a2b226e4d4735af46a"
SAMPLE_SIZE = 24
WORKER_TIMEOUT_SECONDS = 90

WORKER = r'''
from collections import Counter
import json
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / "HDS/学習系統/v0.4.2"))
sys.path.insert(0, str(root))
from 接続.ARC2 import HDS接続 as adapter

raw_counters = {
    "request_reason_counts": Counter(),
    "request_result_path_counts": Counter(),
    "missing_condition_path_counts": Counter(),
    "unknown_condition_result_path_counts": Counter(),
    "prediction_result_path_counts": Counter(),
    "status_counts": Counter(),
}
totals = Counter()
query_rows = []

def path_key(path):
    return "/".join(str(part) for part in path) if path else "<root>"

BaseMachine = adapter.HDS学習実行系

class CapturingMachine(BaseMachine):
    def 照会(self, query):
        result = super().照会(query)
        requests = result.追加観測要求群
        output_predictions = []
        output_request_count = 0
        for request in requests:
            result_path = path_key(request.結果経路)
            raw_counters["request_reason_counts"][request.理由] += 1
            raw_counters["request_result_path_counts"][result_path] += 1
            if result_path == "出力":
                output_request_count += 1
            if request.不足経路群:
                for missing_path in request.不足経路群:
                    raw_counters["missing_condition_path_counts"][
                        result_path + " <- " + path_key(missing_path)
                    ] += 1
            if request.未知条件値群:
                raw_counters["unknown_condition_result_path_counts"][result_path] += 1
            totals["additional_observation_requests"] += 1

        valid_output_keys = set()
        output_prediction_count = 0
        invalid_output_prediction_count = 0
        for prediction in result.予測群:
            result_path = path_key(prediction.結果経路)
            raw_counters["prediction_result_path_counts"][result_path] += 1
            if result_path != "出力":
                continue
            output_prediction_count += 1
            grid = prediction.予測値
            if adapter.有効格子(grid):
                valid_output_keys.add(tuple(tuple(row) for row in grid))
                output_predictions.append(grid)
            else:
                invalid_output_prediction_count += 1

        agreeing_output = output_prediction_count > 0 and invalid_output_prediction_count == 0 and len(valid_output_keys) == 1
        conflict_count = len(result.競合群)
        quarantine_count = len(result.係争中原理群)
        unidentified_count = len(result.識別不能群)
        raw_counters["status_counts"]["output_prediction_present"] += int(output_prediction_count > 0)
        raw_counters["status_counts"]["agreeing_valid_output_prediction"] += int(agreeing_output)
        raw_counters["status_counts"]["any_observation_request"] += int(bool(requests))
        raw_counters["status_counts"]["any_output_request"] += int(output_request_count > 0)
        raw_counters["status_counts"]["only_non_output_requests"] += int(bool(requests) and output_request_count == 0)
        raw_counters["status_counts"]["agreeing_output_with_only_non_output_requests"] += int(
            agreeing_output and bool(requests) and output_request_count == 0
            and conflict_count == 0 and quarantine_count == 0 and unidentified_count == 0
        )
        totals["queries"] += 1
        totals["output_prediction_records"] += output_prediction_count
        totals["valid_output_prediction_records"] += output_prediction_count - invalid_output_prediction_count
        totals["queries_with_output_prediction"] += int(output_prediction_count > 0)
        totals["queries_with_agreeing_valid_output_prediction"] += int(agreeing_output)
        totals["conflict_records"] += conflict_count
        totals["quarantined_principles"] += quarantine_count
        totals["unidentified_records"] += unidentified_count
        query_rows.append({
            "request_count": len(requests),
            "output_request_count": output_request_count,
            "output_prediction_count": output_prediction_count,
            "agreeing_valid_output_prediction": agreeing_output,
            "conflict_count": conflict_count,
            "quarantine_count": quarantine_count,
            "unidentified_count": unidentified_count,
        })
        return result

adapter.HDS学習実行系 = CapturingMachine
task = json.load(sys.stdin)
result = adapter.課題を解く(
    task,
    adapter.事前教材を読む(),
    候補収集=True,
    観測診断=True,
)
for row in result.get("results", []):
    status = row.get("status")
    if isinstance(status, str):
        raw_counters["status_counts"]["adapter_status:" + status] += 1
    for reason in row.get("reasons", []):
        if isinstance(reason, str):
            raw_counters["request_reason_counts"]["adapter_reason:" + reason] += 1
print(json.dumps({
    "totals": dict(totals),
    "request_reason_counts": dict(raw_counters["request_reason_counts"]),
    "request_result_path_counts": dict(raw_counters["request_result_path_counts"]),
    "missing_condition_path_counts": dict(raw_counters["missing_condition_path_counts"]),
    "unknown_condition_result_path_counts": dict(raw_counters["unknown_condition_result_path_counts"]),
    "prediction_result_path_counts": dict(raw_counters["prediction_result_path_counts"]),
    "status_counts": dict(raw_counters["status_counts"]),
}, ensure_ascii=False, separators=(",", ":")))
'''


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def increment_nested(target: dict[str, Counter[str]], source: dict[str, Any]) -> None:
    for group, values in source.items():
        if group == "totals" or not isinstance(values, dict):
            continue
        for key, count in values.items():
            if isinstance(key, str) and type(count) is int and count >= 0:
                target.setdefault(group, Counter())[key] += count


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    challenge_bytes = CHALLENGE.read_bytes()
    audit_bytes = AUDIT.read_bytes()
    if sha256(challenge_bytes) != EXPECTED_CHALLENGE_SHA256:
        raise RuntimeError("public challenge hash changed")
    challenge = json.loads(challenge_bytes)
    audit = json.loads(audit_bytes)
    if audit.get("submission_sha256") != EXPECTED_PREDICTION_SHA256:
        raise RuntimeError("the baseline audit no longer matches the frozen prediction")
    fallback_rows = [
        row for row in audit.get("fallbacks", [])
        if isinstance(row, dict) and row.get("reason") == "solver_hold"
    ]
    first_by_task: dict[str, dict[str, Any]] = {}
    for row in fallback_rows:
        task_id = row.get("task_id")
        if isinstance(task_id, str) and task_id in challenge:
            first_by_task.setdefault(task_id, row)
    ordered = list(first_by_task.items())
    if len(ordered) < SAMPLE_SIZE:
        raise RuntimeError("not enough unique solver-HOLD tasks for the fixed sample")
    sample_indices = sorted({
        round(index * (len(ordered) - 1) / (SAMPLE_SIZE - 1))
        for index in range(SAMPLE_SIZE)
    })
    selected = [ordered[index] for index in sample_indices]
    if len(selected) != SAMPLE_SIZE:
        raise RuntimeError("deterministic sample did not yield the requested size")

    aggregate: dict[str, Counter[str]] = {}
    totals = Counter()
    errors = Counter()
    started = time.perf_counter()
    env = {
        **os.environ,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    for task_id, fallback in selected:
        task = challenge[task_id]
        test_index = fallback.get("test_index")
        if type(test_index) is not int or not 0 <= test_index < len(task.get("test", [])):
            errors["invalid_sample_reference"] += 1
            continue
        worker_task = {
            "train": task["train"],
            "test": [{"input": task["test"][test_index]["input"]}],
        }
        try:
            completed = subprocess.run(
                [sys.executable, "-c", WORKER],
                cwd=ROOT,
                env=env,
                input=json.dumps(worker_task, ensure_ascii=False),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=WORKER_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            errors["worker_timeout"] += 1
            continue
        if completed.returncode != 0:
            errors["worker_process_error"] += 1
            continue
        try:
            observation = json.loads(completed.stdout)
        except json.JSONDecodeError:
            errors["invalid_worker_json"] += 1
            continue
        totals["worker_successes"] += 1
        totals["sampled_test_examples"] += 1
        for key, value in observation.get("totals", {}).items():
            if isinstance(key, str) and type(value) is int and value >= 0:
                totals[key] += value
        increment_nested(aggregate, observation)

    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()
    code_hashes = {}
    for relative in (
        "接続/ARC2/HDS接続.py",
        "HDS/学習系統/v0.4.2/hds学習系統/適応.py",
        "HDS/学習系統/v0.4.2/hds学習系統/実行系.py",
        "HDS/学習系統/v0.4.2/hds学習系統/排気系.py",
    ):
        code_hashes[relative] = sha256((ROOT / relative).read_bytes())

    report = {
        "schema": "arc2-current-main-solver-hold-request-path-sample-v1",
        "run_id": "ARC2-current-main-solver-hold-request-path-sample-20261028",
        "track": "ARC2",
        "instruction_id": "ARC26-UNIFIED-v6.0",
        "source_revision": revision,
        "challenge_sha256": sha256(challenge_bytes),
        "baseline_audit_sha256": sha256(audit_bytes),
        "baseline_prediction_sha256": EXPECTED_PREDICTION_SHA256,
        "sample_method": "24 evenly spaced unique task entries selected only from recorded solver_hold fallbacks; one selected public test input per task; task IDs and grids kept in process memory only",
        "eligible_solver_hold_examples": len(fallback_rows),
        "unique_solver_hold_tasks": len(ordered),
        "sampled_tasks": SAMPLE_SIZE,
        "sampled_examples": SAMPLE_SIZE,
        "worker_timeout_seconds": WORKER_TIMEOUT_SECONDS,
        "execution_seconds": round(time.perf_counter() - started, 3),
        "successful_workers": totals.pop("worker_successes", 0),
        "worker_errors": dict(errors),
        "aggregate_hds_observations": dict(sorted(totals.items())),
        "request_and_prediction_path_counts": {
            group: dict(sorted(counter.items()))
            for group, counter in sorted(aggregate.items())
        },
        "hds_source_sha256": code_hashes,
        "public_training_solutions_read": False,
        "hidden_or_evaluation_solutions_read": False,
        "task_ids_or_raw_grids_or_per_example_results_persisted": False,
        "production_source_changed": False,
        "official_submission_performed": False,
        "official_submission_id": 57682971,
        "official_status": "SubmissionStatus.COMPLETE",
        "official_score": None,
        "score_state": "SCORE_UNOBSERVED",
        "decision": "DIAGNOSTIC_SAMPLE_ONLY_NO_PRODUCTION_CHANGE",
        "limitations": [
            "This deterministic sample does not estimate full-cohort accuracy.",
            "Output-prediction presence is not correctness; no solution labels were loaded.",
            "Any gate or candidate change requires matched public-training evaluation before adoption.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
