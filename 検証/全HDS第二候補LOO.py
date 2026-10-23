"""Train-only LOO diagnostic for distinct HDS predictions used as attempt_2.

Task identifiers are retained only for fold provenance and to remove that task's
seeded examples from the analysis prior. They are never passed to the solver.
The held-out output is compared only after the input-only solver call returns.
"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import redirect_stdout
from datetime import datetime, timezone
import faulthandler
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TRAINING = ROOT / "入力/Kaggle/arc-agi_training_challenges.json"
PRIOR_MANIFEST = ROOT / "接続/ARC2/テンプレート充填教材.json"
PRIOR_TRAINING = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"


def _analysis_hds() -> ModuleType:
    """Load an in-memory diagnostic variant; do not edit the production file."""
    base = importlib.import_module("接続.ARC2.HDS接続")
    source_path = Path(base.__file__)
    source = source_path.read_text(encoding="utf-8")
    replacements = (
        (
            "def 課題を解く(課題, 事前教材):",
            "def 課題を解く(課題, 事前教材, *, 代替候補分析=False):",
        ),
        (
            '    if all(結果["answer"] is not None for 結果 in 基底):\n'
            '        return {"results": 基底, "mechanism": "格子値基底", "minimum_support": 必要支持数}',
            '    if all(結果["answer"] is not None for 結果 in 基底):\n'
            '        if 代替候補分析:\n'
            '            基底 = [{**結果, "candidate_answers": [結果["answer"]]} for 結果 in 基底]\n'
            '        return {"results": 基底, "mechanism": "格子値基底", "minimum_support": 必要支持数}',
        ),
        (
            '        if 未解決理由:\n'
            '            結果群.append({"answer": None, "status": "断定保留", "reasons": 未解決理由})\n'
            '        elif not 予測群:\n'
            '            結果群.append(基底結果)\n'
            '        elif all(p["answer"] == 予測群[0]["answer"] for p in 予測群):\n'
            '            結果群.append({**予測群[0], "agreeing_predictions": len(予測群)})\n'
            '        else:\n'
            '            結果群.append({"answer": None, "status": "断定保留",\n'
            '                           "reasons": ["採用済み機構の完全格子予測が競合したため保留"]})',
            '        if 未解決理由:\n'
            '            出力 = {"answer": None, "status": "断定保留", "reasons": 未解決理由}\n'
            '        elif not 予測群:\n'
            '            出力 = 基底結果\n'
            '        elif all(p["answer"] == 予測群[0]["answer"] for p in 予測群):\n'
            '            出力 = {**予測群[0], "agreeing_predictions": len(予測群)}\n'
            '        else:\n'
            '            出力 = {"answer": None, "status": "断定保留",\n'
            '                    "reasons": ["採用済み機構の完全格子予測が競合したため保留"]}\n'
            '        if 代替候補分析:\n'
            '            候補群 = []\n'
            '            for 予測 in 予測群:\n'
            '                if 予測["answer"] not in 候補群:\n'
            '                    候補群.append(予測["answer"])\n'
            '            出力["candidate_answers"] = 候補群\n'
            '        結果群.append(出力)',
        ),
    )
    for original, replacement in replacements:
        if source.count(original) != 1:
            raise RuntimeError("HDS source no longer matches the pinned diagnostic transformation")
        source = source.replace(original, replacement, 1)

    module_name = "接続.ARC2._HDS接続LOO分析"
    spec = importlib.util.spec_from_file_location(module_name, source_path)
    if spec is None:
        raise RuntimeError("cannot create an in-memory HDS diagnostic module")
    module = ModuleType(module_name)
    module.__file__ = str(source_path)
    module.__package__ = "接続.ARC2"
    module.__spec__ = spec
    sys.modules[module_name] = module
    exec(compile(source, str(source_path), "exec"), module.__dict__)
    return module


def _prior_examples() -> tuple[list[dict[str, Any]], set[str]]:
    manifest = json.loads(PRIOR_MANIFEST.read_text(encoding="utf-8"))
    examples: list[dict[str, Any]] = []
    task_ids: set[str] = set()
    if manifest.get("分割") != "training":
        raise ValueError("diagnostic prior must be from the public training split")
    for source in manifest["教材"]:
        task_id = source["課題ID"]
        task_ids.add(task_id)
        task = json.loads((PRIOR_TRAINING / f"{task_id}.json").read_text(encoding="utf-8"))
        for position in source["訓練例位置"]:
            pair = task["train"][position]
            examples.append({"input": pair["input"], "output": pair["output"]})
    return examples, task_ids


def _worker_line(payload: dict[str, Any], hds: ModuleType,
                 include_diagnostics: bool = False) -> dict[str, Any]:
    task = payload["task"]
    expected = payload["expected"]
    query = task["test"][0]["input"]
    started = time.perf_counter()
    noise = io.StringIO()
    with redirect_stdout(noise):
        result_data = hds.課題を解く(task, payload["prior"], 代替候補分析=True)
    elapsed = time.perf_counter() - started
    row = result_data["results"][0]
    answer = row.get("answer")
    primary = answer if answer is not None else query
    candidates = row.get("candidate_answers", [])
    if not isinstance(candidates, list):
        candidates = []
    second = next((candidate for candidate in candidates if candidate != primary), primary)
    result = {
        "state": "complete",
        "seconds": round(elapsed, 4),
        "solver_answer_present": answer is not None,
        "primary_exact": primary == expected,
        "candidate_count": len(candidates),
        "distinct_second_candidate": second != primary,
        "second_exact": second == expected,
        "any_candidate_exact": any(candidate == expected for candidate in candidates),
        "pair_exact": primary == expected or second == expected,
        "status": row.get("status"),
    }
    if include_diagnostics:
        result["mechanism"] = result_data.get("mechanism")
        result["family"] = row.get("family")
        result["reasons"] = row.get("reasons", [])
    return result


def _worker(trace_path: Path | None, trace_interval: float,
            include_diagnostics: bool) -> int:
    trace_file = trace_path.open("wb") if trace_path is not None else None
    if trace_file is not None:
        faulthandler.dump_traceback_later(trace_interval, repeat=True, file=trace_file)
    try:
        hds = _analysis_hds()
    except Exception as error:
        print(json.dumps({"state": "worker_boot_error", "error_type": type(error).__name__,
                          "message": str(error)[:400]}, ensure_ascii=True), flush=True)
        if trace_file is not None:
            faulthandler.cancel_dump_traceback_later()
            trace_file.close()
        return 1
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            result = _worker_line(payload, hds, include_diagnostics)
        except json.JSONDecodeError as error:
            result = {
                "state": "worker_input_error",
                "error_type": type(error).__name__,
                "position": error.pos,
                "snippet": line[max(0, error.pos - 60):error.pos + 60],
            }
        except Exception as error:  # keep the worker protocol alive per fold
            result = {"state": "error", "error_type": type(error).__name__, "message": str(error)[:240]}
        print(json.dumps(result, ensure_ascii=True), flush=True)
    if trace_file is not None:
        faulthandler.cancel_dump_traceback_later()
        trace_file.close()
    return 0


async def _run_worker(payload: dict[str, Any], timeout: float,
                      trace_path: Path | None = None, trace_interval: float = 3.0,
                      include_diagnostics: bool = False):
    """Run a fresh process for each fold so no module state can leak across folds."""
    started = time.perf_counter()
    command = [sys.executable, str(Path(__file__).resolve()), "--worker"]
    if trace_path is not None:
        command.extend(["--trace-path", str(trace_path), "--trace-interval", str(trace_interval)])
    if include_diagnostics:
        command.append("--include-diagnostics")
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=ROOT, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")),
            timeout=timeout,
        )
    except TimeoutError:
        process.kill()
        await process.wait()
        return {"state": "timeout", "timeout_seconds": timeout,
                "wall_seconds": round(time.perf_counter() - started, 4)}
    wall_seconds = time.perf_counter() - started
    try:
        output_lines = stdout.decode("utf-8").splitlines()
        result = json.loads(output_lines[0])
    except (UnicodeDecodeError, json.JSONDecodeError, IndexError):
        result = {"state": "invalid_worker_output", "line_prefix": stdout[:600].decode("utf-8", "replace"),
                  "parse_error": "worker stdout was not one JSON record"}
    if process.returncode:
        # A valid JSON line is not a completed fold if the worker later crashed.
        # Keep its reported state for diagnosis, but exclude it from completed-fold counts.
        result["worker_reported_state"] = result.get("state")
        result["state"] = "worker_exit"
        result["return_code"] = process.returncode
        result["stderr_prefix"] = stderr[:400].decode("utf-8", "replace")
    result["wall_seconds"] = round(wall_seconds, 4)
    return result


def _folds(tasks: dict[str, Any], task_id_filter: str | None = None,
           heldout_filter: int | None = None):
    for task_id in sorted(tasks):
        if task_id_filter is not None and task_id != task_id_filter:
            continue
        train = tasks[task_id].get("train", [])
        if len(train) < 4:
            continue
        for heldout_index, heldout in enumerate(train):
            if heldout_filter is not None and heldout_index != heldout_filter:
                continue
            support = train[:heldout_index] + train[heldout_index + 1:]
            yield task_id, heldout_index, support, heldout


async def _run(args: argparse.Namespace) -> int:
    if not TRAINING.is_file():
        raise FileNotFoundError(f"public training challenge file not found: {TRAINING}")
    raw = TRAINING.read_bytes()
    tasks = json.loads(raw.decode("utf-8"))
    prior, prior_task_ids = _prior_examples()
    eligible = sum(
        len(task.get("train", [])) for task_id, task in tasks.items()
        if len(task.get("train", [])) >= 4
        and (args.task_id is None or task_id == args.task_id)
    )
    if args.heldout_index is not None:
        eligible = sum(
            1 for task_id, task in tasks.items()
            if len(task.get("train", [])) >= 4
            and args.heldout_index < len(task["train"])
            and (args.task_id is None or task_id == args.task_id)
        )
    limit = eligible if args.max_folds == 0 else min(args.max_folds, eligible)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or ROOT / "出力/検証" / f"ARC2-HDS第二候補-LOO-{stamp}.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output.with_suffix(".summary.json")
    counts: dict[str, int] = {}
    seconds: list[float] = []
    fold_index = 0
    with output.open("x", encoding="utf-8", newline="\n") as records:
        header = {
            "record_type": "header",
            "schema": "arc2-hds-second-attempt-loo-run-v1",
            "training_sha256": hashlib.sha256(raw).hexdigest(),
            "training_tasks": len(tasks),
            "eligible_folds": eligible,
            "requested_folds": limit,
            "minimum_support": 3,
            "timeout_seconds_per_fold": args.timeout_seconds,
            "prior_task_leakage_guard": "omit seeded examples when the fold task is their source task",
            "task_id_available_to_solver": False,
            "diagnostics_included": args.include_diagnostics,
            "analysis_filter_task_id": args.task_id,
            "analysis_filter_heldout_index": args.heldout_index,
        }
        records.write(json.dumps(header, ensure_ascii=False) + "\n")
        records.flush()
        for task_id, heldout_index, support, heldout in _folds(
            tasks, args.task_id, args.heldout_index
        ):
            if fold_index >= limit:
                break
            fold_index += 1
            payload = {
                "task": {"train": support, "test": [{"input": heldout["input"]}]},
                "expected": heldout["output"],
                "prior": [] if task_id in prior_task_ids else prior,
            }
            trace_path = None
            if args.trace_timeouts:
                trace_dir = output.with_suffix(".traces")
                trace_dir.mkdir(parents=True, exist_ok=True)
                trace_path = trace_dir / f"fold-{fold_index}-{task_id}-{heldout_index}.txt"
            result = await _run_worker(payload, args.timeout_seconds, trace_path,
                                       args.trace_interval, args.include_diagnostics)
            if trace_path is not None and result.get("state") == "timeout":
                result["trace_path"] = str(trace_path)
            state = result.get("state", "unknown")
            counts[state] = counts.get(state, 0) + 1
            if isinstance(result.get("seconds"), (int, float)):
                seconds.append(float(result["seconds"]))
            record = {
                "record_type": "fold",
                "fold_index": fold_index,
                "task_id": task_id,
                "heldout_index": heldout_index,
                "support_examples": len(support),
                "prior_excluded_for_leakage": task_id in prior_task_ids,
                **result,
            }
            records.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.flush()
            print(f"fold {fold_index}/{limit}: {state}; {result.get('seconds', result.get('timeout_seconds', '-'))}s; "
                  f"pair_gain={bool(result.get('pair_exact') and not result.get('primary_exact'))}", flush=True)
    complete = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()[1:]]
    summary = {
        "schema": "arc2-hds-second-attempt-loo-summary-v1",
        "records_path": str(output),
        "training_sha256": hashlib.sha256(raw).hexdigest(),
        "training_tasks": len(tasks),
        "eligible_folds": eligible,
        "requested_folds": limit,
        "processed_folds": fold_index,
        "states": counts,
        "completed_folds": sum(item.get("state") == "complete" for item in complete),
        "primary_exact": sum(bool(item.get("primary_exact")) for item in complete),
        "selected_second_exact": sum(bool(item.get("second_exact")) and bool(item.get("distinct_second_candidate")) for item in complete),
        "pair_exact": sum(bool(item.get("pair_exact")) for item in complete),
        "incremental_pair_exact": sum(bool(item.get("pair_exact")) and not bool(item.get("primary_exact")) for item in complete),
        "any_candidate_exact_upper_bound": sum(bool(item.get("any_candidate_exact")) for item in complete),
        "distinct_second_candidate_folds": sum(bool(item.get("distinct_second_candidate")) for item in complete),
        "mean_solver_seconds": round(sum(seconds) / len(seconds), 4) if seconds else None,
        "max_solver_seconds": max(seconds) if seconds else None,
        "hidden_or_evaluation_solutions_read": False,
        "diagnostics_included": args.include_diagnostics,
        "official_submission": False,
    }
    with summary_path.open("x", encoding="utf-8", newline="\n") as target:
        json.dump(summary, target, ensure_ascii=False, indent=2)
        target.write("\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--trace-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--max-folds", type=int, default=10,
                        help="maximum deterministic folds; 0 processes all eligible folds")
    parser.add_argument("--timeout-seconds", type=float, default=20.0,
                        help="hard per-fold worker timeout")
    parser.add_argument("--output", type=Path,
                        help="new JSONL path; an existing file is never overwritten")
    parser.add_argument("--task-id", help="select one fold task for diagnosis only")
    parser.add_argument("--heldout-index", type=int,
                        help="select one held-out training example for diagnosis only")
    parser.add_argument("--trace-timeouts", action="store_true",
                        help="write periodic Python stack traces for bounded diagnosis")
    parser.add_argument("--trace-interval", type=float, default=3.0,
                        help="seconds between diagnostic stack traces")
    parser.add_argument("--include-diagnostics", action="store_true",
                        help="include HDS mechanism/reason fields in each fold record")
    args = parser.parse_args()
    if args.trace_timeouts and os.name == "nt":
        parser.error("--trace-timeouts is disabled on Windows after worker access violations")
    if args.worker:
        if args.trace_interval <= 0:
            parser.error("trace-interval must be positive")
        return _worker(args.trace_path, args.trace_interval, args.include_diagnostics)
    if args.max_folds < 0 or args.timeout_seconds <= 0 or args.trace_interval <= 0:
        parser.error("max-folds must be >= 0; timeout-seconds and trace-interval must be positive")
    if args.heldout_index is not None and args.heldout_index < 0:
        parser.error("heldout-index must be >= 0")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
