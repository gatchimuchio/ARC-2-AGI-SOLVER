"""NEW isolated outer cell/CLI watchdog. Never patches the real v61 Notebook.

Linux owns a fresh runner session; inner workers create groups in that session.
Windows uses an assigned job with an explicitly unproved creation/assignment
race. Process creation and filesystem stalls remain OS-level limitations.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

from deadline_control import OwnedSnapshot, ProcessControl, SNAPSHOT_NAME, artifact_bytes


HERE = Path(__file__).resolve().parent
DEFAULT_RUNNER = HERE / "solve.py"


def adapter():
    spec = importlib.util.spec_from_file_location("outer_v61_format_validator", HERE / "Kaggle提出.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(args):
    started = time.monotonic()
    if not all(math.isfinite(value) for value in (args.run_budget_seconds, args.finalization_reserve_seconds, args.cleanup_grace_seconds, args.exit_reserve_seconds)):
        raise ValueError("finite watchdog budget required")
    if not 0 < args.cleanup_grace_seconds + 0.05 <= args.exit_reserve_seconds < args.run_budget_seconds <= 42600:
        raise ValueError("invalid outer cleanup/exit reserve")
    if not args.cleanup_grace_seconds + 0.05 <= args.finalization_reserve_seconds < args.run_budget_seconds - args.exit_reserve_seconds:
        raise ValueError("inner finalization reserve must fit outer budget")
    if os.name == "posix" and sys.platform != "linux":
        raise RuntimeError("outer session cleanup currently targets Linux only")
    if os.name == "posix" and sys.version_info < (3, 11):
        raise RuntimeError("Linux watchdog requires Python >= 3.11")
    module = adapter()
    challenge_path = args.challenges or module._discover_challenges()
    raw = challenge_path.read_bytes()
    tasks = module.入力検査(json.loads(raw.decode("utf-8")))
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    submission_path, audit_path = output / module.提出名, output / module.監査名
    if submission_path.exists() or audit_path.exists() or (output / SNAPSHOT_NAME).exists():
        raise FileExistsError("outer watchdog protects preexisting output")
    token = uuid.uuid4().hex
    end = started + args.run_budget_seconds
    inner_end = end - args.exit_reserve_seconds
    env = {**os.environ, "ARC2_RUN_STARTED_MONOTONIC": str(started),
           "ARC2_RUN_DEADLINE_MONOTONIC": str(inner_end), "ARC2_DEADLINE_RUN_TOKEN": token,
           "ARC2_OUTER_WATCHDOG_ACTIVE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    command = [sys.executable, str(args.runner.resolve()), "--challenges", str(challenge_path.resolve()),
               "--output-dir", str(output), "--run-budget-seconds", str(args.run_budget_seconds),
               "--finalization-reserve-seconds", str(args.finalization_reserve_seconds),
               "--cleanup-grace-seconds", str(args.cleanup_grace_seconds),
               "--max-worker-output-bytes", str(args.max_worker_output_bytes)]
    if args.aggregate_diagnostics:
        command.append("--aggregate-diagnostics")
    control = ProcessControl(args.cleanup_grace_seconds, args.max_worker_output_bytes,
                             hard_deadline=end, session_owner=True)
    process = control.invoke(command, env=env, timeout=args.run_budget_seconds, stop_at=inner_end)
    if not process.cleanup_complete or control.active:
        raise RuntimeError("outer process-tree cleanup unconfirmed; no completion claim")
    if process.error not in (None, "global_deadline"):
        raise RuntimeError("outer operational failure")
    if not process.error and process.returncode:
        raise RuntimeError("inner failure remains failure, including preflight failure")
    if not (output / SNAPSHOT_NAME).is_file():
        raise RuntimeError("no complete owned snapshot; cannot complete notebook")
    owned, submission, audit = OwnedSnapshot.recover(output, token)
    submission_bytes = artifact_bytes(submission)
    module.提出検査(tasks, submission)
    if list(submission) != list(tasks):
        raise ValueError("output order differs from input order")
    detail = audit.get("deadline_control", {})
    if detail.get("run_token") != token or detail.get("preflight_passed") is not True:
        raise FileExistsError("output ownership/preflight not proved; refuse update")
    if audit.get("challenge_sha256") != hashlib.sha256(raw).hexdigest() or audit.get("submission_sha256") != hashlib.sha256(submission_bytes).hexdigest():
        raise ValueError("owned output/audit pairing failed validation")
    if detail.get("scientific_correctness_evaluated") is not False or detail.get("solved_count") is not None:
        raise ValueError("watchdog cannot assert solved/correct outputs")
    if process.error == "global_deadline":
        # Update only this run's validated audit, never arbitrary existing output.
        detail["run_state"] = "OUTER_WATCHDOG_DEADLINE_WITH_EXPLICIT_FALLBACK"
        detail["all_tasks_processed"] = False
        for row in audit.get("fallbacks", []):
            if row.get("reason") == "global_deadline_unprocessed":
                row["reason"] = "outer_watchdog_deadline"
    detail["outer_watchdog"] = {"completed": True, "deadline_terminated_runner": bool(process.error),
                                "runner_returncode": process.returncode, "child_reaped": process.direct_child_reaped,
                                "tree_termination_acknowledged": process.tree_termination_acknowledged,
                                "elapsed_seconds": round(time.monotonic() - started, 4),
                                "whole_notebook_host_runtime_proved": False,
                                "windows_assignment_race_unproved": os.name == "nt"}
    detail["whole_notebook_outer_watchdog_wired"] = True
    # Repair interrupted public-file derivation from the one atomic owned pair.
    owned.publish(submission, audit)
    print(json.dumps({"state": detail["run_state"], "valid_owned_submission": True,
                      "scientific_correctness_evaluated": False, "outer_watchdog": detail["outer_watchdog"]}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", type=Path, default=DEFAULT_RUNNER)
    parser.add_argument("--challenges", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("/kaggle/working"))
    parser.add_argument("--run-budget-seconds", type=float, default=42600)
    parser.add_argument("--finalization-reserve-seconds", type=float, default=600)
    parser.add_argument("--exit-reserve-seconds", type=float, default=10)
    parser.add_argument("--cleanup-grace-seconds", type=float, default=3)
    parser.add_argument("--max-worker-output-bytes", type=int, default=16 * 1024 * 1024)
    parser.add_argument("--aggregate-diagnostics", action="store_true")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
