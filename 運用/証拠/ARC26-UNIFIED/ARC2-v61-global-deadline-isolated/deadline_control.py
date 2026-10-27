"""Isolated execution control for the unchanged frozen v61 solver protocol.

This bounds ordinary child execution, queueing and output capture. It cannot
preempt an OS process-creation/filesystem stall; an outer Notebook watchdog is
still required before claiming a whole-Notebook runtime guarantee.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid


@dataclass(frozen=True)
class Budget:
    started: float
    deadline: float
    reserve: float

    @property
    def solve_cutoff(self):
        return self.deadline - self.reserve

    def remaining(self):
        return max(0.0, self.solve_cutoff - time.monotonic())


@dataclass
class ProcessResult:
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    cleanup_complete: bool = True
    direct_child_reaped: bool = False
    tree_termination_acknowledged: bool = False


class _WindowsJob:
    """Own assigned child descendants; assignment-after-Popen race is explicit."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", w.DWORD), ("min_working", ctypes.c_size_t),
                        ("max_working", ctypes.c_size_t), ("active", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD), ("scheduling", w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", IO), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t), ("peak_job", ctypes.c_size_t)]
        self.ctypes, self.w = ctypes, w
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        self.assigned = False
        if not self.handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObject failed")
        info = Extended()
        info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, self.w.HANDLE(process._handle)):
            raise OSError(self.ctypes.get_last_error(), "AssignProcessToJobObject failed")
        self.assigned = True

    def terminate(self):
        if self.handle:
            return bool(self.api.TerminateJobObject(self.handle, 1))
        return False

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _linux_session_groups(session_id):
    groups = set()
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[3]) == session_id and fields[0] != "Z":
                groups.add(int(fields[2]))
        except (OSError, ValueError, IndexError):
            continue
    return groups


class ProcessControl:
    def __init__(self, cleanup_grace=3.0, max_output_bytes=16 * 1024 * 1024, *, hard_deadline=math.inf, session_owner=False):
        self.cleanup_grace = cleanup_grace
        self.max_output_bytes = max_output_bytes
        self.stop_event = threading.Event()
        self.stop_reason = "parent_cancelled"
        self.lock = threading.Lock()
        self.active = {}
        self.launched = self.peak_active = 0
        self.hard_deadline, self.session_owner = hard_deadline, session_owner
        self.termination_failures = 0

    def _terminate(self, process, job):
        if os.name == "posix":
            # Inner workers own groups in the outer runner's session. The outer
            # Linux watchdog owns that entire session, including other groups.
            if self.session_owner:
                until = min(self.hard_deadline, time.monotonic() + self.cleanup_grace)
                while True:
                    groups = _linux_session_groups(process.pid)
                    if not groups:
                        return True
                    for group in groups:
                        try:
                            os.killpg(group, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        except OSError:
                            return False
                    if time.monotonic() >= until:
                        return False
                    time.sleep(min(0.01, max(0, until - time.monotonic())))
            groups = {process.pid}
            acknowledged = True
            for group in groups:
                try:
                    os.killpg(group, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError:
                    acknowledged = False
            return acknowledged
        elif job is not None and job.assigned:
            return job.terminate()
        elif process.poll() is None:
            try:
                process.kill()
            except OSError:
                return False
        return job is None  # An unassigned Windows job is not tree ownership.

    def stop_all(self, reason):
        self.stop_reason = reason
        self.stop_event.set()
        with self.lock:
            for process, job in self.active.values():
                if not self._terminate(process, job):
                    self.termination_failures += 1

    def invoke(self, command, *, input_text="", env=None, timeout=300.0, stop_at=math.inf):
        if self.stop_event.is_set() or time.monotonic() >= stop_at:
            return ProcessResult(error=self.stop_reason if self.stop_event.is_set() else "global_deadline")
        process = job = None
        result = ProcessResult()
        # Regular files never wait for inherited PIPE EOF and cap memory reads.
        with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            source.write(input_text.encode("utf-8"))
            source.seek(0)
            if self.stop_event.is_set() or time.monotonic() >= stop_at:
                return ProcessResult(error=self.stop_reason if self.stop_event.is_set() else "global_deadline")
            end = min(stop_at, time.monotonic() + timeout)
            try:
                if os.name == "nt":
                    job = _WindowsJob()
                platform_options = {}
                if os.name == "posix":
                    platform_options = {"start_new_session": True} if self.session_owner else {"process_group": 0}
                process = subprocess.Popen(command, stdin=source, stdout=output, stderr=errors,
                                           env=env, **platform_options)
                if job is not None:
                    job.assign(process)
                with self.lock:
                    self.active[process.pid] = (process, job)
                    self.launched += 1
                    self.peak_active = max(self.peak_active, len(self.active))
                while process.poll() is None:
                    if self.stop_event.is_set():
                        result.error = self.stop_reason
                        break
                    if time.monotonic() >= end:
                        result.error = "global_deadline" if stop_at <= end else "task_wall_timeout"
                        break
                    if max(os.fstat(output.fileno()).st_size, os.fstat(errors.fileno()).st_size) > self.max_output_bytes:
                        result.error = "worker_output_limit"
                        break
                    try:
                        process.wait(timeout=min(0.05, max(0.001, end - time.monotonic())))
                    except subprocess.TimeoutExpired:
                        pass
            except OSError:
                result.error = "worker_process_ownership_or_spawn_error"
                if process is not None:
                    result.cleanup_complete = False
            finally:
                if process is not None:
                    # Also remove descendants after a normal direct-child exit.
                    result.tree_termination_acknowledged = self._terminate(process, job)
                    if not result.tree_termination_acknowledged:
                        result.cleanup_complete = False
                    try:
                        process.wait(timeout=max(0, min(self.cleanup_grace, self.hard_deadline - time.monotonic())))
                        result.direct_child_reaped = True
                    except subprocess.TimeoutExpired:
                        result.cleanup_complete = False
                        result.error = "worker_cleanup_incomplete"
                    result.returncode = process.poll()
                    if result.cleanup_complete:
                        with self.lock:
                            self.active.pop(process.pid, None)
                            if job is not None:
                                job.close()
                elif job is not None:
                    job.close()
                if job is not None and not job.assigned:
                    job.close()
            output.seek(0)
            errors.seek(0)
            stdout, stderr = output.read(self.max_output_bytes + 1), errors.read(self.max_output_bytes + 1)
            if max(len(stdout), len(stderr)) > self.max_output_bytes:
                result.error = "worker_output_limit"
            result.stdout = stdout[:self.max_output_bytes].decode("utf-8", errors="replace")
            result.stderr = stderr[:self.max_output_bytes].decode("utf-8", errors="replace")
        return result


class OwnedArtifact:
    def __init__(self, path):
        self.path = Path(path)
        self.expected = None

    def write(self, value):
        content = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
            if self.expected is None:
                # Atomic exclusive publication; never replace a preexisting file.
                os.link(temporary, self.path)
            else:
                if not self.path.is_file() or hashlib.sha256(self.path.read_bytes()).hexdigest() != self.expected:
                    raise FileExistsError("own output was removed or changed; refuse overwrite")
                os.replace(temporary, self.path)
            self.expected = hashlib.sha256(content).hexdigest()
        finally:
            temporary.unlink(missing_ok=True)
        return content


SNAPSHOT_NAME = "deadline_owned_snapshot.json"


def artifact_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


class OwnedSnapshot:
    """One atomic complete pair, then derived public files; single writer only."""
    def __init__(self, directory, token):
        self.token = token
        self.snapshot = OwnedArtifact(Path(directory) / SNAPSHOT_NAME)
        self.submission = OwnedArtifact(Path(directory) / "submission.json")
        self.audit = OwnedArtifact(Path(directory) / "submission_audit.json")

    def publish(self, submission, audit):
        digest = hashlib.sha256(artifact_bytes(submission)).hexdigest()
        if audit.get("submission_sha256") != digest or audit.get("deadline_control", {}).get("run_token") != self.token:
            raise ValueError("snapshot audit must match submission")
        body = {"format": "arc2-owned-output-snapshot-v1", "run_token": self.token,
                "previous_publication": {"submission": self.submission.expected, "audit": self.audit.expected},
                "submission": submission, "audit": audit}
        # A killed publication always leaves one complete owned pair here.
        self.snapshot.write(body)
        self.submission.write(submission)
        self.audit.write(audit)

    @classmethod
    def recover(cls, directory, token):
        pair = cls(directory, token)
        content = pair.snapshot.path.read_bytes()
        body = json.loads(content)
        if body.get("format") != "arc2-owned-output-snapshot-v1" or body.get("run_token") != token:
            raise FileExistsError("snapshot belongs to a different run")
        if body["audit"].get("deadline_control", {}).get("run_token") != token:
            raise FileExistsError("snapshot audit ownership not proved")
        if body["audit"].get("submission_sha256") != hashlib.sha256(artifact_bytes(body["submission"])).hexdigest():
            raise ValueError("atomic snapshot pairing is invalid")
        for name, output, value in (("submission", pair.submission, body["submission"]), ("audit", pair.audit, body["audit"])):
            previous = body["previous_publication"][name]
            if output.path.exists():
                actual = hashlib.sha256(output.path.read_bytes()).hexdigest()
                allowed = {previous, hashlib.sha256(artifact_bytes(value)).hexdigest()}
                if actual not in allowed:
                    raise FileExistsError("public file is not an owned old/new publication")
                output.expected = actual
            elif previous is not None:
                raise FileExistsError("previous owned public file was removed")
        pair.snapshot.expected = hashlib.sha256(content).hexdigest()
        return pair, body["submission"], body["audit"]


def run_one(api, task_id, task, launcher, payload_root, *, aggregate_diagnostics, control, budget):
    env = {**os.environ, "ARC2_PAYLOAD_ROOT": str(payload_root), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if aggregate_diagnostics:
        env["ARC2_AGGREGATE_DIAGNOSTICS"] = "1"
    else:
        env.pop("ARC2_AGGREGATE_DIAGNOSTICS", None)
    process = control.invoke([sys.executable, launcher, "--worker"], input_text=json.dumps(task, ensure_ascii=False),
                             env=env, timeout=api["課題時間上限秒"], stop_at=budget.solve_cutoff)
    if not process.cleanup_complete:
        raise RuntimeError("worker cleanup incomplete; outer watchdog required")
    if process.error:
        result = {"error": process.error}
    else:
        try:
            result = json.loads(process.stdout)
        except (json.JSONDecodeError, TypeError):
            result = {"error": "worker_exit" if process.returncode else "worker_invalid_json"}
    diagnostics = result.get("aggregate_diagnostics", {}) if aggregate_diagnostics and isinstance(result, dict) else {}
    return (*api["結果を候補へ"](task_id, task, result), diagnostics)


def run_submission(args, api):
    if os.name == "posix" and sys.version_info < (3, 11):
        raise RuntimeError("isolated POSIX process groups require Python >= 3.11")
    now = time.monotonic()
    started = float(os.environ.get("ARC2_RUN_STARTED_MONOTONIC", now))
    if not all(math.isfinite(value) for value in (started, args.run_budget_seconds, args.finalization_reserve_seconds, args.cleanup_grace_seconds)):
        raise ValueError("deadline parameters must be finite")
    if started < 0 or started > now + 0.01:
        raise ValueError("shared start must not be in the future")
    if not 0 < args.cleanup_grace_seconds + 0.05 <= args.finalization_reserve_seconds < args.run_budget_seconds <= 42600 or args.max_worker_output_bytes < 1:
        raise ValueError("invalid deadline/reserve/capture bounds")
    end = started + args.run_budget_seconds
    if "ARC2_RUN_DEADLINE_MONOTONIC" in os.environ:
        supplied = float(os.environ["ARC2_RUN_DEADLINE_MONOTONIC"])
        if not math.isfinite(supplied):
            raise ValueError("outer deadline must be finite")
        end = min(end, supplied)
    budget = Budget(started, end, args.finalization_reserve_seconds)
    launcher = Path(os.environ.get("ARC2_WORKER_LAUNCHER", sys.argv[0])).resolve()
    payload_root = Path(os.environ.get("ARC2_PAYLOAD_ROOT", Path(api["__file__"]).resolve().parents[2]))
    input_path = args.challenges or api["_discover_challenges"]()
    raw = input_path.read_bytes()
    tasks = api["入力検査"](json.loads(raw.decode("utf-8")))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    submission_path, audit_path = args.output_dir / api["提出名"], args.output_dir / api["監査名"]
    if submission_path.exists() or audit_path.exists() or (args.output_dir / SNAPSHOT_NAME).exists():
        raise FileExistsError("existing submission/audit protected")
    control = ProcessControl(args.cleanup_grace_seconds, args.max_worker_output_bytes, hard_deadline=budget.deadline)
    if budget.remaining() <= 0:
        raise RuntimeError("no solve budget remains before preflight")
    preflight = control.invoke([sys.executable, str(launcher), "--preflight"], timeout=120,
                               stop_at=budget.solve_cutoff,
                               env={**os.environ, "ARC2_PAYLOAD_ROOT": str(payload_root), "PYTHONIOENCODING": "utf-8"})
    if preflight.error or preflight.returncode or not preflight.cleanup_complete:
        raise RuntimeError("preflight failed; no submission artifact seeded")
    completed = set()
    records = {key: (*api["結果を候補へ"](key, task, {"error": "global_deadline_unprocessed"}), {}) for key, task in tasks.items()}
    token = os.environ.get("ARC2_DEADLINE_RUN_TOKEN") or uuid.uuid4().hex
    owned_snapshot = OwnedSnapshot(args.output_dir, token)
    max_inflight = 0

    def snapshot(state, parent_error=None):
        submission = {key: records[key][0] for key in tasks}
        api["提出検査"](tasks, submission)
        holds = [row for key in tasks for row in records[key][1]]
        content = artifact_bytes(submission)
        audit = {"format": "arc2-kaggle-submission-audit-v1", "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                 "source_commit": os.environ.get("ARC2_SOURCE_COMMIT", "unknown"),
                 "challenge_sha256": hashlib.sha256(raw).hexdigest(), "challenge_file": input_path.name,
                 "tasks": len(tasks), "test_examples": sum(len(task["test"]) for task in tasks.values()),
                 "attempts_per_test": 2, "fallback_count": len(holds), "solver_hold_reason_counts": api["_保留理由数"](holds),
                 "fallbacks": holds, "seconds": round(time.monotonic() - started, 3),
                 "submission_sha256": hashlib.sha256(content).hexdigest(),
                 "deadline_control": {"run_state": state, "all_tasks_processed": len(completed) == len(tasks),
                                      "completed_task_count": len(completed), "unprocessed_task_count": len(tasks) - len(completed),
                                      "scientific_correctness_evaluated": False, "solved_count": None,
                                      "absolute_deadline_monotonic": budget.deadline, "finalization_reserve_seconds": budget.reserve,
                                      "max_inflight": max_inflight, "max_active_subprocesses": control.peak_active,
                                      "capture_limit_bytes": control.max_output_bytes, "parent_error_type": parent_error,
                                      "remaining_owned_processes": len(control.active), "termination_signal_failures": control.termination_failures,
                                      "preflight_passed": True, "run_token": token,
                                      "process_tree_backend": "posix_worker_group" if os.name == "posix" else "windows_job_after_creation",
                                      "tree_termination_scope": "OS signal/job acknowledgement plus direct-child reap; not unconditional OS liveness proof",
                                      "whole_notebook_outer_watchdog_wired": os.environ.get("ARC2_OUTER_WATCHDOG_ACTIVE") == "1"}}
        if args.aggregate_diagnostics:
            scalar, families, distinct, requests = Counter(), Counter(), Counter(), Counter()
            for _predictions, _holds, diagnostic in records.values():
                if not isinstance(diagnostic, dict):
                    continue
                for key in ("candidate_prediction_count", "examples_with_candidates", "nonidentity_candidate_prediction_count",
                            "examples_with_nonidentity_candidates", "simple_transform_unique_candidates", "simple_transform_distinct_from_first"):
                    value = diagnostic.get(key)
                    if type(value) is int and value >= 0:
                        scalar[key] += value
                for key, counter in (("candidate_family_counts", families), ("nonidentity_candidate_family_counts", distinct), ("observation_request_counts", requests)):
                    values = diagnostic.get(key)
                    if isinstance(values, dict):
                        for name, value in values.items():
                            if isinstance(name, str) and len(name) <= 160 and type(value) is int and value >= 0:
                                counter[name] += value
            audit["aggregate_diagnostics"] = {**dict(scalar), "candidate_family_counts": dict(sorted(families.items())),
                                               "nonidentity_candidate_family_counts": dict(sorted(distinct.items())),
                                               "observation_request_counts": dict(sorted(requests.items()))}
        owned_snapshot.publish(submission, audit)
        return audit

    snapshot("RUNNING_WITH_UNPROCESSED_FALLBACK")
    executor = ThreadPoolExecutor(max_workers=api["並列数"])
    pending = {}
    iterator = iter(tasks.items())
    exhausted = False
    parent_error = None
    deadline_hit = False
    try:
        while pending or not exhausted:
            while len(pending) < api["並列数"] and not exhausted and budget.remaining() > 0:
                try:
                    task_id, task = next(iterator)
                except StopIteration:
                    exhausted = True
                    break
                future = executor.submit(api["_run_one"], task_id, task, str(launcher), payload_root,
                                         aggregate_diagnostics=args.aggregate_diagnostics, control=control, budget=budget)
                pending[future] = task_id
                max_inflight = max(max_inflight, len(pending))
            if exhausted and not pending:
                break
            if budget.remaining() <= 0:
                deadline_hit = True
                break
            if not pending:
                continue
            done, _ = wait(pending, timeout=budget.remaining(), return_when=FIRST_COMPLETED)
            if not done:
                deadline_hit = True
                break
            for future in done:
                task_id = pending.pop(future)
                records[task_id] = future.result()
                completed.add(task_id)
            snapshot("RUNNING_WITH_UNPROCESSED_FALLBACK")
    except Exception as error:
        parent_error = type(error).__name__
    finally:
        control.stop_all("parent_error" if parent_error else "global_deadline" if deadline_hit else "controller_closed")
        for future in pending:
            future.cancel()
        remaining_cleanup = max(0, min(args.cleanup_grace_seconds + 0.25, budget.deadline - time.monotonic()))
        done, not_done = wait(pending, timeout=remaining_cleanup) if pending else (set(), set())
        # Do not call implicit/unbounded wait=True with live worker threads.
        executor.shutdown(wait=not not_done, cancel_futures=True)
        if not_done:
            parent_error = parent_error or "CleanupIncompleteRequiresOuterWatchdog"
        if control.active or control.termination_failures:
            parent_error = parent_error or "ProcessTreeCleanupUnconfirmed"
        for future in done:
            if future.cancelled():
                continue
            try:
                records[pending[future]] = future.result()
                completed.add(pending[future])
            except Exception as error:
                parent_error = parent_error or type(error).__name__
    if deadline_hit or parent_error:
        reason = "parent_error" if parent_error else "global_deadline"
        for key, task in tasks.items():
            if key not in completed:
                records[key] = (*api["結果を候補へ"](key, task, {"error": reason}), {})
    final = snapshot("PARENT_ERROR" if parent_error else "GLOBAL_DEADLINE_EXHAUSTED" if deadline_hit else "COMPLETE", parent_error)
    if parent_error:
        raise RuntimeError("deadline controller parent/cleanup failure; explicit fallback snapshot retained")
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0
