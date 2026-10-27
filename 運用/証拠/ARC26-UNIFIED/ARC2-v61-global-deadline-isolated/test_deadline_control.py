import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pytest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
FROZEN = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-full-runtime-reproduction-20261026T1800Z/payload/接続/ARC2/Kaggle提出.py"
RUNNER = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v61-kaggle-staging-20261026/solve.py"
sys.path.insert(0, str(HERE))
import deadline_control as dc


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


legacy = load(FROZEN, "frozen_v61_orchestration_reference")
variant = load(HERE / "Kaggle提出.py", "isolated_v61_deadline_adapter")


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    launcher = tmp_path / "synthetic_worker.py"
    launcher.write_text('''import json,os,sys,time
if '--preflight' in sys.argv:
    time.sleep(float(os.environ.get('SYNTH_PREFLIGHT_SLEEP','0')))
    raise SystemExit(int(os.environ.get('SYNTH_PREFLIGHT_EXIT','0')))
task=json.load(sys.stdin)
time.sleep(float(os.environ.get('SYNTH_SLEEP','0')))
rows=[]
for pair in task['test']:
    answer=[[(value+1)%10 for value in row] for row in pair['input']]
    rows.append({'answer':answer,'second_answer':pair['input'],'status':'synthetic_output','reasons':[]})
print(json.dumps({'results':rows,'aggregate_diagnostics':{'candidate_prediction_count':len(rows),'candidate_family_counts':{'synthetic':len(rows)}}}))
raise SystemExit(int(os.environ.get('SYNTH_WORKER_EXIT','0')))
''', encoding="utf-8")
    monkeypatch.setenv("ARC2_WORKER_LAUNCHER", str(launcher))
    monkeypatch.setenv("ARC2_PAYLOAD_ROOT", str(tmp_path))
    for key in ("ARC2_RUN_STARTED_MONOTONIC", "ARC2_RUN_DEADLINE_MONOTONIC", "SYNTH_SLEEP", "SYNTH_PREFLIGHT_EXIT", "SYNTH_PREFLIGHT_SLEEP", "SYNTH_WORKER_EXIT"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("ARC2_DEADLINE_RUN_TOKEN", raising=False)
    monkeypatch.delenv("ARC2_OUTER_WATCHDOG_ACTIVE", raising=False)
    def challenge(count):
        # Reverse lexical order verifies preserved input order, not sorted IDs.
        data = {f"synthetic-{count-index}": {"train": [{"input": [[1]], "output": [[2]]}],
                                             "test": [{"input": [[index % 9]]}, {"input": [[1, 2], [3, 4]]}]}
                for index in range(count)}
        path = tmp_path / f"challenges-{count}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path, data
    return tmp_path, challenge


def run_variant(input_path, output, *extra):
    return variant.run_cli(["--challenges", str(input_path), "--output-dir", str(output),
                            "--run-budget-seconds", "12", "--finalization-reserve-seconds", "2", "--cleanup-grace-seconds", "0.6", *extra])


def test_frozen_solver_formatter_and_payload_are_unchanged():
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == "c20102c4e9a01e833ca8f9e2778b5306333c50c065d9aebe7cbeaf574e74418d"
    assert hashlib.sha256(RUNNER.read_bytes()).hexdigest() == "d47dac81dbcb9cd9a151fa7461145b5ac708291dbb52af8a4099e20efbc4a791"
    def tree(path, omitted):
        parsed = ast.parse(path.read_text(encoding="utf-8"))
        parsed.body = [node for node in parsed.body if not isinstance(node, ast.FunctionDef) or node.name not in omitted]
        return ast.dump(parsed, include_attributes=False)
    assert tree(FROZEN, {"_run_one", "run_cli"}) == tree(HERE / "Kaggle提出.py", {"_run_one", "run_cli"})
    assert tree(RUNNER, {"main"}) == tree(HERE / "solve.py", {"main"})
    assert variant.課題時間上限秒 == 300 and variant.並列数 == 3
    main = next(node for node in ast.parse((HERE / "solve.py").read_text(encoding="utf-8")).body if isinstance(node, ast.FunctionDef) and node.name == "main")
    assert next(node.lineno for node in ast.walk(main) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "setdefault") < next(node.lineno for node in ast.walk(main) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "payload_root")


@pytest.mark.parametrize("exit_code", [0, 7])
def test_generous_budget_submission_bytes_equal_frozen_even_nonzero_json_exit(synthetic, monkeypatch, exit_code):
    tmp, challenge = synthetic
    path, _data = challenge(4)
    monkeypatch.setenv("SYNTH_WORKER_EXIT", str(exit_code))
    old_output, new_output = tmp / "old", tmp / "new"
    assert legacy.run_cli(["--challenges", str(path), "--output-dir", str(old_output), "--aggregate-diagnostics"]) == 0
    assert run_variant(path, new_output, "--aggregate-diagnostics") == 0
    assert (old_output / "submission.json").read_bytes() == (new_output / "submission.json").read_bytes()
    old_audit = json.loads((old_output / "submission_audit.json").read_text(encoding="utf-8"))
    new_audit = json.loads((new_output / "submission_audit.json").read_text(encoding="utf-8"))
    assert old_audit["aggregate_diagnostics"] == new_audit["aggregate_diagnostics"]
    assert new_audit["deadline_control"]["run_state"] == "COMPLETE"
    assert new_audit["deadline_control"]["scientific_correctness_evaluated"] is False
    assert new_audit["deadline_control"]["solved_count"] is None


def test_cutoff_preserves_all_ordered_ids_and_bounds_queued_and_active(synthetic, monkeypatch):
    tmp, challenge = synthetic
    path, data = challenge(12)
    monkeypatch.setenv("SYNTH_SLEEP", "5")
    output = tmp / "cutoff"
    started = time.monotonic()
    assert run_variant(path, output, "--run-budget-seconds", "2.8", "--finalization-reserve-seconds", "0.8", "--cleanup-grace-seconds", "0.6") == 0
    elapsed = time.monotonic() - started
    submission = json.loads((output / "submission.json").read_text(encoding="utf-8"))
    audit = json.loads((output / "submission_audit.json").read_text(encoding="utf-8"))
    assert list(submission) == list(data)
    assert all(len(submission[key]) == len(data[key]["test"]) for key in data)
    assert all(row["attempt_1"] == row["attempt_2"] == pair["input"] for key in data for row, pair in zip(submission[key], data[key]["test"], strict=True))
    assert elapsed < 4.5
    assert audit["deadline_control"]["run_state"] == "GLOBAL_DEADLINE_EXHAUSTED"
    assert audit["deadline_control"]["max_inflight"] <= 3
    assert audit["deadline_control"]["max_active_subprocesses"] <= 3
    assert audit["deadline_control"]["unprocessed_task_count"] >= 9
    assert audit["fallback_count"] == 24
    assert {row["reason"] for row in audit["fallbacks"]} == {"global_deadline"}
    assert audit["submission_sha256"] == hashlib.sha256((output / "submission.json").read_bytes()).hexdigest()


def test_parent_error_terminates_active_children_and_retains_explicit_snapshot(synthetic, monkeypatch):
    tmp, challenge = synthetic
    path, _data = challenge(8)
    monkeypatch.setenv("SYNTH_SLEEP", "5")
    original = variant._run_one
    controls = []
    def failure(task_id, *args, **kwargs):
        controls.append(kwargs["control"])
        if task_id == "synthetic-8":
            time.sleep(0.3)
            raise ValueError("synthetic parent-facing failure")
        return original(task_id, *args, **kwargs)
    monkeypatch.setattr(variant, "_run_one", failure)
    output = tmp / "parent-error"
    started = time.monotonic()
    with pytest.raises(RuntimeError):
        run_variant(path, output, "--cleanup-grace-seconds", "0.6")
    assert time.monotonic() - started < 3.5
    assert all(not control.active for control in controls)
    audit = json.loads((output / "submission_audit.json").read_text(encoding="utf-8"))
    assert audit["deadline_control"]["run_state"] == "PARENT_ERROR"
    assert audit["deadline_control"]["parent_error_type"] == "ValueError"
    assert audit["deadline_control"]["scientific_correctness_evaluated"] is False


def test_preflight_failure_does_not_seed_submission(synthetic, monkeypatch):
    tmp, challenge = synthetic
    path, _ = challenge(2)
    monkeypatch.setenv("SYNTH_PREFLIGHT_EXIT", "7")
    output = tmp / "preflight-fail"
    with pytest.raises(RuntimeError):
        run_variant(path, output)
    assert not (output / "submission.json").exists()
    assert not (output / "submission_audit.json").exists()


def test_original_absolute_clock_is_not_reset_after_setup(synthetic, monkeypatch):
    tmp, challenge = synthetic
    path, _ = challenge(2)
    monkeypatch.setenv("ARC2_RUN_STARTED_MONOTONIC", str(time.monotonic() - 30))
    with pytest.raises(RuntimeError, match="before preflight"):
        run_variant(path, tmp / "expired")
    assert not (tmp / "expired/submission.json").exists()
    monkeypatch.setenv("ARC2_RUN_STARTED_MONOTONIC", str(time.monotonic() + 30))
    with pytest.raises(ValueError, match="future"):
        run_variant(path, tmp / "future")


def test_preexisting_outputs_and_changed_own_file_are_never_overwritten(synthetic):
    tmp, challenge = synthetic
    path, _ = challenge(1)
    output = tmp / "protected"
    output.mkdir()
    (output / "submission.json").write_bytes(b"protected bytes")
    with pytest.raises(FileExistsError):
        run_variant(path, output)
    assert (output / "submission.json").read_bytes() == b"protected bytes"
    owned = dc.OwnedArtifact(tmp / "owned.json")
    owned.write({"first": True})
    owned.path.write_bytes(b"external change")
    with pytest.raises(FileExistsError):
        owned.write({"second": True})
    assert owned.path.read_bytes() == b"external change"
    assert not list(tmp.glob(".*.tmp"))


def test_output_limit_is_explicit_operational_failure_and_memory_read_is_bounded():
    control = dc.ProcessControl(cleanup_grace=0.6, max_output_bytes=4096)
    result = control.invoke([sys.executable, "-B", "-c", "import sys,time;sys.stdout.write('x'*200000);sys.stdout.flush();time.sleep(5)"], timeout=2)
    assert result.error == "worker_output_limit"
    assert len(result.stdout.encode()) <= 4096
    assert result.cleanup_complete and not control.active


def test_inherited_descendant_output_does_not_hold_parent_and_tree_is_terminated():
    grandchild = "import time;time.sleep(5)"
    child = "import subprocess,sys,time,json;p=subprocess.Popen([sys.executable,'-B','-c'," + repr(grandchild) + "],stdout=sys.stdout,stderr=sys.stderr);print(json.dumps({'descendant_pid':p.pid}),flush=True);time.sleep(5)"
    control = dc.ProcessControl(cleanup_grace=0.6)
    started = time.monotonic()
    result = control.invoke([sys.executable, "-B", "-c", child], timeout=1.8)
    assert time.monotonic() - started < 3.5
    assert result.error == "task_wall_timeout" and result.cleanup_complete
    pid = json.loads(result.stdout)["descendant_pid"]
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x100000, False, pid)
        if handle:
            try:
                assert kernel.WaitForSingleObject(handle, 0) == 0
            finally:
                kernel.CloseHandle(handle)
    else:
        stat = Path(f"/proc/{pid}/stat")
        assert not stat.exists() or stat.read_text().split()[2] == "Z"
    assert not control.active


@pytest.mark.skipif(os.name != "nt", reason="Windows assignment-failure branch")
def test_job_assignment_failure_is_cleanup_unconfirmed_not_normal_fallback(monkeypatch):
    def deny(self, process):
        raise OSError("synthetic assignment refusal")
    monkeypatch.setattr(dc._WindowsJob, "assign", deny)
    control = dc.ProcessControl(cleanup_grace=0.5)
    result = control.invoke([sys.executable, "-B", "-c", "import time;time.sleep(3)"], timeout=0.5)
    assert result.error == "worker_process_ownership_or_spawn_error"
    assert result.direct_child_reaped is True
    assert result.tree_termination_acknowledged is False
    assert result.cleanup_complete is False


@pytest.mark.skipif(os.name != "nt", reason="Windows job termination acknowledgement")
def test_failed_job_termination_ack_is_not_leader_reap_success(monkeypatch):
    original = dc._WindowsJob.terminate
    def no_ack(self):
        original(self)  # Still clean the disposable process; simulate failed API acknowledgement.
        return False
    control = dc.ProcessControl(cleanup_grace=0.5)
    with monkeypatch.context() as context:
        context.setattr(dc._WindowsJob, "terminate", no_ack)
        result = control.invoke([sys.executable, "-B", "-c", "import time;time.sleep(3)"], timeout=0.15)
    assert result.direct_child_reaped and not result.tree_termination_acknowledged
    assert not result.cleanup_complete
    control.stop_all("test_cleanup")
    for process, job in list(control.active.values()):
        process.wait(timeout=1)
        job.close()
        control.active.pop(process.pid)
