"""Matched public-training ablation of the HDS candidate certification gate.

Each worker receives train examples and a test input only. The held-out output
stays in the scorer process and is compared after the worker returns. The
ablation disables only the HDS equality-certification predicate; it does not
change candidate generators or use task-specific answer branching.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from contextlib import redirect_stdout


ROOT = Path(__file__).resolve().parents[3]
HDS_ROOT = ROOT / "HDS/学習系統/v0.4.2"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(HDS_ROOT) not in sys.path:
    sys.path.insert(0, str(HDS_ROOT))

from 接続.ARC2 import HDS接続 as hds  # noqa: E402

TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
PRIOR_MANIFEST = ROOT / "接続/ARC2/テンプレート充填教材.json"
PRIOR_TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"


def _state_digest(machine) -> str:
    payload = json.dumps(machine.状態.現在状態, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _worker(disable_hds_gate: bool) -> int:
    payload = json.load(sys.stdin)
    if disable_hds_gate:
        hds.同値原理あり = lambda *_args, **_kwargs: False

    base_type = hds.HDS学習実行系
    instances = []

    class RecordingHDS(base_type):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)

    hds.HDS学習実行系 = RecordingHDS
    try:
        noise = io.StringIO()
        with redirect_stdout(noise):
            result_data = hds.課題を解く(payload["task"], payload["prior"], 候補収集=True)
        result = result_data["results"][0]
        families = [x for x in result_data.get("families", []) if isinstance(x, dict)]
        predictions = result.get("candidate_predictions", [])
        prediction_grids = [
            x["answer"] for x in predictions
            if isinstance(x, dict) and isinstance(x.get("answer"), list)
        ]
        machine = instances[0] if instances else None
        state = None
        if machine is not None:
            state = {
                "version": machine.状態.現在版,
                "experience_count": machine.台帳.件数("観測台帳"),
                "update_count": machine.台帳.件数("更新台帳"),
                "active_principle_count": len(machine._有効原理群()),
                "quarantined_principle_count": len(machine._係争中原理群()),
                "state_sha256": _state_digest(machine),
            }
        family_counts = {
            "total": len(families),
            "training_all_examples_reproduced": sum(bool(x.get("採用可")) for x in families),
            "hds_equality_admitted": sum(bool(x.get("同値採用")) for x in families),
            "both_training_match_and_admitted": sum(bool(x.get("採用可")) and bool(x.get("同値採用")) for x in families),
            "current_observations": sum(int(x.get("現在観測数", 0) or 0) for x in families),
        }
        response = {
            "state": "complete",
            "solver_answer": result.get("answer"),
            "candidate_predictions": prediction_grids,
            "family_counts": family_counts,
            "hds_state_after_training": state,
            "disabled_hds_gate": disable_hds_gate,
        }
    except Exception as error:  # Return only the type; never serialize task data.
        response = {"state": "error", "error_type": type(error).__name__}
    print(json.dumps(response, ensure_ascii=False), flush=True)
    return 0


def _prior_examples() -> tuple[list[dict], set[str]]:
    manifest = json.loads(PRIOR_MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("分割") != "training":
        raise ValueError("prior manifest must use public training only")
    examples, source_ids = [], set()
    for source in manifest.get("教材", []):
        task_id = source["課題ID"]
        source_ids.add(task_id)
        task = json.loads((PRIOR_TRAINING / f"{task_id}.json").read_text(encoding="utf-8"))
        for position in source["訓練例位置"]:
            pair = task["train"][position]
            examples.append({"input": pair["input"], "output": pair["output"]})
    return examples, source_ids


def _call_worker(task: dict, prior: list[dict], disable_gate: bool, timeout: float) -> dict:
    payload = {"task": task, "prior": prior, "disable_hds_gate": disable_gate}
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker",
             "--disable-hds-gate" if disable_gate else "--normal-gate"],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, env=env, cwd=ROOT, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"state": "timeout", "timeout_seconds": timeout}
    if completed.returncode != 0:
        return {"state": "worker_exit", "return_code": completed.returncode}
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"state": "invalid_worker_output"}
    return response


def _prior_score(result: dict, expected: list[list[int]], query: list[list[int]]) -> dict:
    answer = result.get("solver_answer")
    candidate_grids = result.get("candidate_predictions", [])
    primary = answer if answer is not None else query
    primary_exact = primary == expected
    fallback_exact = answer is None and primary_exact
    solver_exact = answer is not None and primary_exact
    nonidentity_candidates = [grid for grid in candidate_grids if grid != query]
    candidate_exact = any(grid == expected for grid in nonidentity_candidates)
    any_exact = solver_exact or candidate_exact
    return {
        "state": result.get("state"),
        "solver_answer_present": answer is not None,
        "solver_primary_exact": solver_exact,
        "input_copy_fallback_exact_excluded": fallback_exact,
        "candidate_prediction_count": len(candidate_grids),
        "nonidentity_candidate_exact": candidate_exact,
        "any_nonidentity_exact": any_exact,
        "family_counts": result.get("family_counts"),
        "hds_state_after_training": result.get("hds_state_after_training"),
    }


def run(max_folds: int, timeout: float, output: Path) -> dict:
    if not output.is_absolute():
        output = (ROOT / output).resolve()
    raw = TRAINING.read_bytes()
    tasks = json.loads(raw.decode("utf-8"))
    prior, prior_task_ids = _prior_examples()
    folds = []
    for task_id in sorted(tasks):
        train = tasks[task_id].get("train", [])
        if len(train) < 4:
            continue
        for heldout_index, heldout in enumerate(train):
            support = train[:heldout_index] + train[heldout_index + 1 :]
            # Task ID is used only in this scorer process for prior leakage exclusion.
            folds.append((task_id, support, heldout))
            if len(folds) >= max_folds:
                break
        if len(folds) >= max_folds:
            break

    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output.with_suffix(".summary.json")
    if output.exists() or summary_path.exists():
        raise FileExistsError(output)
    rows = []
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({
            "record_type": "header",
            "schema": "arc2-p3-hds-candidate-gate-ablation-v1",
            "training_sha256": hashlib.sha256(raw).hexdigest(),
            "training_tasks": len(tasks),
            "requested_folds": len(folds),
            "timeout_seconds_per_worker": timeout,
            "task_id_passed_to_worker": False,
            "heldout_output_passed_to_worker": False,
            "prior_task_leakage_guard": "omit all seeded examples if their source task is held out",
            "intervention": "Disable only HDS equality-certification predicate in the ablation worker.",
        }, ensure_ascii=False) + "\n")
        stream.flush()
        for index, (task_id, support, heldout) in enumerate(folds, start=1):
            prior_for_task = [] if task_id in prior_task_ids else prior
            task = {"train": support, "test": [{"input": heldout["input"]}]}
            query = heldout["input"]
            # Held-out output remains in this scorer process and is never sent to either worker.
            normal_raw = _call_worker(task, prior_for_task, False, timeout)
            normal = _prior_score(normal_raw, heldout["output"], query) if normal_raw.get("state") == "complete" else {"state": normal_raw.get("state")}
            ablated_raw = _call_worker(task, prior_for_task, True, timeout)
            ablated = _prior_score(ablated_raw, heldout["output"], query) if ablated_raw.get("state") == "complete" else {"state": ablated_raw.get("state")}
            row = {
                "record_type": "fold",
                "fold_index": index,
                "support_examples": len(support),
                "hds_gate_enabled": normal,
                "hds_gate_disabled": ablated,
            }
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"fold {index}/{len(folds)}: enabled={normal.get('state')}, disabled={ablated.get('state')}", flush=True)

    complete = [r for r in rows if r["hds_gate_enabled"].get("state") == "complete" and r["hds_gate_disabled"].get("state") == "complete"]
    def total(path: str, key: str) -> int:
        return sum(bool(row[path].get(key)) for row in complete)
    normal_exact = [r["fold_index"] for r in complete if r["hds_gate_enabled"].get("any_nonidentity_exact")]
    ablated_exact = [r["fold_index"] for r in complete if r["hds_gate_disabled"].get("any_nonidentity_exact")]
    summary = {
        "schema": "arc2-p3-hds-candidate-gate-ablation-summary-v1",
        "records_path": output.relative_to(ROOT).as_posix(),
        "training_sha256": hashlib.sha256(raw).hexdigest(),
        "training_tasks": len(tasks),
        "eligible_folds": sum(len(t.get("train", [])) for t in tasks.values() if len(t.get("train", [])) >= 4),
        "requested_folds": len(folds),
        "completed_paired_folds": len(complete),
        "gate_enabled": {
            "solver_primary_exact": total("hds_gate_enabled", "solver_primary_exact"),
            "admitted_candidate_exact_folds": total("hds_gate_enabled", "nonidentity_candidate_exact"),
            "any_nonidentity_exact_folds": len(normal_exact),
            "fallback_exact_excluded": sum(bool(r["hds_gate_enabled"].get("input_copy_fallback_exact_excluded")) for r in complete),
            "hds_state_changed_folds": sum(bool(r["hds_gate_enabled"].get("hds_state_after_training", {}).get("version", 0)) for r in complete),
            "hds_equality_admitted_families": sum(int(r["hds_gate_enabled"].get("family_counts", {}).get("hds_equality_admitted", 0)) for r in complete),
            "exact_fold_indexes": normal_exact,
        },
        "gate_disabled": {
            "solver_primary_exact": total("hds_gate_disabled", "solver_primary_exact"),
            "admitted_candidate_exact_folds": total("hds_gate_disabled", "nonidentity_candidate_exact"),
            "any_nonidentity_exact_folds": len(ablated_exact),
            "fallback_exact_excluded": sum(bool(r["hds_gate_disabled"].get("input_copy_fallback_exact_excluded")) for r in complete),
            "hds_state_changed_folds": sum(bool(r["hds_gate_disabled"].get("hds_state_after_training", {}).get("version", 0)) for r in complete),
            "hds_equality_admitted_families": sum(int(r["hds_gate_disabled"].get("family_counts", {}).get("hds_equality_admitted", 0)) for r in complete),
            "exact_fold_indexes": ablated_exact,
        },
        "paired_recoveries_enabled_over_disabled": len(set(normal_exact) - set(ablated_exact)),
        "paired_regressions_enabled_vs_disabled": len(set(ablated_exact) - set(normal_exact)),
        "heldout_output_passed_to_worker": False,
        "heldout_output_compared_after_workers": True,
        "task_id_passed_to_worker": False,
        "fallback_counted_correct": False,
        "hidden_or_evaluation_solutions_read": False,
        "official_submission": False,
        "learning_effect": "MEASURED_AS_HDS_CERTIFICATION_GATE_ABLATION",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-folds", type=int, default=20)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--disable-hds-gate", action="store_true")
    parser.add_argument("--normal-gate", action="store_true")
    args = parser.parse_args()
    if args.worker:
        return _worker(args.disable_hds_gate)
    if args.max_folds < 1:
        parser.error("--max-folds must be positive")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "出力/検証" / f"ARC2-P3-HDS-candidate-gate-ablation-{stamp}.jsonl"
    run(args.max_folds, args.timeout_seconds, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
