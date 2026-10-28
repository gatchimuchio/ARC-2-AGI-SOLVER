from datetime import datetime, timedelta, timezone
import ctypes
import importlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


monitor = importlib.import_module("運用.ARC2_Kaggleスコア監視")


def _write_repo_cli_fixture(root, *, kaggle_version="2.2.5", sdk_version="0.1.38", locked_kaggle="2.2.5", project_name="arc-2-agi-solver"):
    python = root / ".venv/Scripts/python.exe"
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_bytes(b"python placeholder")
    site = root / ".venv/Lib/site-packages"
    module = site / "kaggle/__main__.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    for name, version in (("kaggle", kaggle_version), ("kagglesdk", sdk_version)):
        metadata = site / f"{name}-{version}.dist-info/METADATA"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "{project_name}"\n[dependency-groups]\ndev = ["kaggle==2.2.5", "kagglesdk==0.1.38"]\n', encoding="utf-8"
    )
    (root / "uv.lock").write_text(
        f'[[package]]\nname = "kaggle"\nversion = "{locked_kaggle}"\n[[package]]\nname = "kagglesdk"\nversion = "0.1.38"\n', encoding="utf-8"
    )
    return python


def test_zero_is_numeric_but_blank_and_pending_are_not():
    assert monitor._status_state("COMPLETE", "0.00") == "NUMERIC"
    assert monitor._status_state("COMPLETE", "") == "SCORE_UNOBSERVED"
    assert monitor._status_state("COMPLETE", None) == "SCORE_UNOBSERVED"
    assert monitor._status_state("PENDING", "") == "PENDING"


def test_pending_poll_cadence_caps_at_one_hour():
    assert [monitor._next_interval_minutes("PENDING", n) for n in range(1, 6)] == [5, 15, 30, 60, 60]


def test_kaggle_cli_prefix_finds_uvx_with_scheduler_reduced_path(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor.shutil, "which", lambda _name: None)
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    monkeypatch.setattr(monitor.Path, "home", lambda: tmp_path)
    user_scripts = (
        tmp_path
        / "AppData"
        / "Roaming"
        / "Python"
        / f"Python{monitor.sys.version_info.major}{monitor.sys.version_info.minor}"
        / "Scripts"
    )
    user_scripts.mkdir(parents=True)
    uvx = user_scripts / "uvx.exe"
    uvx.write_bytes(b"test executable placeholder")

    assert monitor._kaggle_cli_prefix() == [
        str(uvx), "--from", "kaggle==2.2.5", "kaggle"
    ]


def test_kaggle_cli_prefix_prefers_manifest_pinned_project_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    manifest = tmp_path / "運用" / "ARC26-UNIFIED" / "kaggle-cli-environment.json"
    manifest.parent.mkdir(parents=True)
    venv = tmp_path / "project-kaggle-env"
    cli = venv / "Scripts" / "kaggle.exe"
    cli.parent.mkdir(parents=True)
    cli.write_bytes(b"pinned project cli")
    manifest.write_text(
        json.dumps({
            "track": "ARC2",
            "kaggle_cli": "Kaggle CLI 2.2.5",
            "venv_path": str(venv),
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(monitor.shutil, "which", lambda _name: r"C:\tools\uvx.exe")

    assert monitor._kaggle_cli_prefix() == [str(cli)]
    assert monitor.LAST_CLI_DISCOVERY["selected_source"] == "manifest"


def test_cli_discovery_failure_records_local_path_and_manifest_read_checks(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    monkeypatch.setattr(monitor.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(monitor.shutil, "which", lambda _name: None)

    with pytest.raises(FileNotFoundError) as raised:
        monitor._kaggle_cli_prefix()
    details = monitor._observation_error_details(raised.value, "history_query")
    discovery = details["cli_discovery"]

    assert discovery["root"] == str(tmp_path)
    assert discovery["root_exists"] is True
    assert discovery["manifest_path"] == str(tmp_path / "運用/ARC26-UNIFIED/kaggle-cli-environment.json")
    assert discovery["manifest_read_status"] == "FileNotFoundError"
    assert discovery["manifest_read_errno"] == 2
    assert discovery["manifest_track_matches"] is False
    assert discovery["manifest_cli_version_matches"] is False
    assert discovery["uvx_resolved_path"] is None
    assert discovery["uv_resolved_path"] is None
    assert discovery["user_uvx.exe_exists"] is False
    assert discovery["user_uv.exe_exists"] is False


@pytest.mark.parametrize("track, version", [("ARC3", "Kaggle CLI 2.2.5"), ("ARC2", "Kaggle CLI 2.2.4")])
def test_cli_discovery_does_not_select_wrong_track_or_version(tmp_path, monkeypatch, track, version):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    monkeypatch.setattr(monitor.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(monitor.shutil, "which", lambda _name: None)
    _write_repo_cli_fixture(tmp_path)
    manifest = tmp_path / "運用/ARC26-UNIFIED/kaggle-cli-environment.json"
    manifest.parent.mkdir(parents=True)
    venv = tmp_path / "cli-env"
    cli = venv / "Scripts/kaggle.exe"
    cli.parent.mkdir(parents=True)
    cli.write_bytes(b"placeholder")
    manifest.write_text(json.dumps({"track": track, "kaggle_cli": version, "venv_path": str(venv)}), encoding="utf-8")

    with pytest.raises(FileNotFoundError) as raised:
        monitor._kaggle_cli_prefix()

    discovery = monitor._observation_error_details(raised.value, "history_query")["cli_discovery"]
    assert discovery["manifest_read_status"] == "ok"
    assert discovery["manifest_cli_path"] == str(cli)
    assert discovery["manifest_cli_exists"] is True
    assert not (discovery["manifest_track_matches"] and discovery["manifest_cli_version_matches"])


def test_cli_discovery_uses_exact_repo_venv_when_external_manifest_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    monkeypatch.setattr(monitor.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(monitor.shutil, "which", lambda _name: None)
    python = _write_repo_cli_fixture(tmp_path)
    calls = []
    def successful_probe(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr(monitor.subprocess, "run", successful_probe)

    assert monitor._kaggle_cli_prefix() == [str(python), "-m", "kaggle"]
    assert calls and calls[0][0] == str(python)
    assert monitor.LAST_CLI_DISCOVERY["selected_source"] == "repo_venv"


@pytest.mark.parametrize("changes", [
    {"kaggle_version": "2.2.4"}, {"sdk_version": "0.1.37"},
    {"locked_kaggle": "2.2.4"}, {"project_name": "arc-3-agi-agent"},
])
def test_cli_discovery_rejects_repo_venv_version_lock_or_track_mismatch(tmp_path, monkeypatch, changes):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    monkeypatch.setattr(monitor.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(monitor.shutil, "which", lambda _name: None)
    _write_repo_cli_fixture(tmp_path, **changes)

    with pytest.raises(FileNotFoundError):
        monitor._kaggle_cli_prefix()


def test_cli_discovery_rejects_incomplete_old_dist_info_shadow(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    monkeypatch.setattr(monitor.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(monitor.shutil, "which", lambda _name: None)
    _write_repo_cli_fixture(tmp_path)
    (tmp_path / ".venv/Lib/site-packages/kaggle-2.2.4.dist-info/licenses").mkdir(parents=True)

    with pytest.raises(FileNotFoundError) as raised:
        monitor._kaggle_cli_prefix()

    discovery = monitor._observation_error_details(raised.value, "history_query")["cli_discovery"]
    assert discovery["repo_cli_kaggle_dist_info_count"] == 2
    assert discovery["repo_cli_kaggle_version_matches"] is False


def test_read_only_kaggle_cli_history_parses_submission_rows(monkeypatch):
    captured = {}
    payload = [{
        "date": "2026/10/25 0:13:10",
        "description": "ARC2 candidate",
        "fileName": "submission.json",
        "privateScore": "",
        "publicScore": "0.00",
        "ref": 57611018,
        "status": "SubmissionStatus.COMPLETE",
    }]

    def fake_run(command, **kwargs):
        if "submission" in command:
            return subprocess.CompletedProcess(command, 0, "Submission Ref: 57611018\nStatus: COMPLETE\nPublic Score: 0.00\n", "")
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")

    monkeypatch.setattr(monitor, "_kaggle_cli_prefix", lambda: ["uvx", "--from", "kaggle==2.2.5", "kaggle"])
    monkeypatch.setattr(monitor.subprocess, "run", fake_run)

    rows = monitor._safe_kaggle_history()

    assert len(rows) == 1
    assert rows[0].ref == 57611018
    assert rows[0].public_score == "0.00"
    assert rows[0].file_name == "submission.json"
    assert monitor._status_name(rows[0].status) == "COMPLETE"
    canonical = monitor._history_rows(rows)[0]
    assert canonical["publicScore"] == "0.00"
    assert canonical["status"] == "SubmissionStatus.COMPLETE"
    assert captured["command"][-7:] == [
        "submissions", monitor.大会, "--format", "json", "--page-size", "100", "-q"
    ]
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["timeout"] == 120


def test_score_checkpoint_preserves_active_loo_worker_and_separate_due_time():
    now = monitor.datetime(2026, 10, 25, 12, 0, tzinfo=monitor.timezone.utc)
    previous = {
        "instruction_id": "ARC26-SOLVE-SCORE-20261025",
        "last_submission_ref": 57611018,
        "source_sha": "source-sha",
        "notebook_id": "owner/kernel",
        "notebook_version": 9,
        "notebook_sha256": "notebook-sha",
        "submission_sha256": "submission-sha",
        "test_dataset_sha256": "input-sha",
        "score_evidence_path": "previous-score.json",
        "submission_evidence_path": "submission.json",
        "process_status": "ACTIVE",
        "experiment_id": "ARC2-C2-062-D4_SPARSE_SUPPORT_TWO_FULL",
        "worker_pid": 16192,
        "worker_cpu_seconds": 13911.9,
        "wall_elapsed_seconds": 14082.5,
        "eligible_tasks_done": 404,
        "eligible_tasks_total": 575,
        "paired_loo_folds_done": 1212,
        "paired_loo_folds_total": 1725,
        "candidate_version": 10,
        "candidate_kernel_status": "COMPLETE",
        "candidate_adapter_sha256": "adapter-sha",
        "candidate_submission_sha256": "candidate-output-sha",
        "candidate_loo_delta_exact": 29,
        "candidate_next_action": "Submit once after the gate opens.",
        "candidate_next_due_utc": "2026-10-26T00:20:00Z",
        "candidate_submission_performed": False,
        "candidate_quota_gate_allowed": False,
        "next_check_at_utc": "2026-10-25T11:58:39.024Z",
        "next_action": "Track the same in-flight fit; do not duplicate or terminate.",
    }
    history = [SimpleNamespace(
        ref=57611018,
        date="2026-10-25T00:13:10.933Z",
        status="SubmissionStatus.COMPLETE",
        public_score="0.00",
    )]

    record = monitor._build_record(history, now, previous)

    assert record["score_state"] == "NUMERIC"
    assert record["instruction_id"] == "ARC26-SOLVE-SCORE-20261025"
    assert record["official_history_next_due_utc"] == record["next_check_at_utc"]
    assert record["experiment_next_check_at_utc"] == previous["next_check_at_utc"]
    assert record["worker_pid"] == 16192
    assert record["process_status"] == "ACTIVE"
    assert record["eligible_tasks_done"] == 404
    assert record["paired_loo_folds_done"] == 1212
    assert record["experiment_next_action"] == previous["next_action"]
    assert record["candidate_version"] == 10
    assert record["candidate_kernel_status"] == "COMPLETE"
    assert record["candidate_adapter_sha256"] == "adapter-sha"
    assert record["candidate_submission_sha256"] == "candidate-output-sha"
    assert record["candidate_loo_delta_exact"] == 29
    assert record["candidate_next_action"] == previous["candidate_next_action"]
    assert record["candidate_next_due_utc"] == "2026-10-26T00:20:00Z"
    assert record["candidate_submission_performed"] is False
    assert record["candidate_quota_gate_allowed"] is False


def test_resume_detection_covers_first_start_restart_and_long_disconnect():
    now = datetime(2026, 10, 24, 0, 0, tzinfo=timezone.utc)
    same_boot = now.replace(minute=0, second=0).isoformat()
    runtime = {"last_monitor_tick_at_utc": (now - timedelta(minutes=5)).isoformat(), "boot_time_utc": same_boot}

    assert monitor._should_resume(now, {}, same_boot) is True
    assert monitor._should_resume(now, runtime, "different-boot") is True
    assert monitor._should_resume(now, {**runtime, "last_monitor_tick_at_utc": (now - timedelta(minutes=16)).isoformat()}, same_boot) is True
    assert monitor._should_resume(now, runtime, same_boot) is False


def test_system_boot_time_preserves_uptime_above_32_bit_milliseconds(monkeypatch):
    now = datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc)
    uptime_ms = 2**32 + 120_000
    # A real ctypes call boundary returns 64 bits, while an unspecified ctypes
    # signature defaults to c_int and truncates this value.
    callback = ctypes.CFUNCTYPE(ctypes.c_ulonglong)(lambda: uptime_ms)
    tick_function = ctypes.CFUNCTYPE(ctypes.c_int)(ctypes.cast(callback, ctypes.c_void_p).value)
    monkeypatch.setattr(monitor.os, "name", "nt")
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(
        kernel32=SimpleNamespace(GetTickCount64=tick_function),
    ), raising=False)

    observed_boot = monitor._system_boot_time(now)

    assert observed_boot == (now - timedelta(milliseconds=uptime_ms)).replace(microsecond=0).isoformat()
    assert tick_function.restype is ctypes.c_ulonglong
    assert tick_function.argtypes == []


@pytest.mark.parametrize("jitter_seconds", [-5, -1, 1, 5])
def test_resume_detection_tolerates_boot_estimate_rounding_jitter(jitter_seconds):
    now = datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc)
    boot = now - timedelta(days=1)
    runtime = {
        "last_monitor_tick_at_utc": (now - timedelta(minutes=5)).isoformat(),
        "boot_time_utc": boot.isoformat(),
    }

    assert monitor._should_resume(
        now, runtime, (boot + timedelta(seconds=jitter_seconds)).isoformat()
    ) is False


def test_resume_detection_preserves_actual_reboot_resume():
    now = datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc)
    runtime = {
        "last_monitor_tick_at_utc": (now - timedelta(minutes=5)).isoformat(),
        "boot_time_utc": (now - timedelta(days=1)).isoformat(),
    }

    assert monitor._should_resume(
        now, runtime, (now - timedelta(minutes=2)).isoformat()
    ) is True


def test_tick_respects_due_time_despite_one_second_boot_jitter(monkeypatch):
    now = datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc)
    boot = now - timedelta(days=1)
    next_due = (now + timedelta(minutes=10)).isoformat()
    monkeypatch.setattr(monitor, "_now", lambda: now)
    monkeypatch.setattr(monitor, "_load_checkpoints", lambda: [{"next_check_at_utc": next_due}])
    monkeypatch.setattr(monitor, "_system_boot_time", lambda _now: (boot + timedelta(seconds=1)).isoformat())
    monkeypatch.setattr(monitor, "_load_runtime_state", lambda: {
        "last_monitor_tick_at_utc": (now - timedelta(minutes=5)).isoformat(),
        "boot_time_utc": boot.isoformat(),
    })
    monkeypatch.setattr(monitor, "_save_runtime_state", lambda _value: None)
    monkeypatch.setattr(monitor, "_safe_kaggle_history", lambda: pytest.fail("history must not be queried before due"))

    assert monitor.tick() == (0, {"state": "not_due", "next_check_at_utc": next_due})


@pytest.mark.parametrize("status,score,previous_pending,expected_state,minutes", [
    ("PENDING", None, 0, "PENDING", 5),
    ("PENDING", None, 1, "PENDING", 15),
    ("PENDING", None, 2, "PENDING", 30),
    ("PENDING", None, 3, "PENDING", 60),
    ("COMPLETE", "0.00", 0, "NUMERIC", 60),
    ("COMPLETE", "", 0, "SCORE_UNOBSERVED", 60),
    ("FAILED", None, 0, "FAILED", 60),
])
def test_post_deadline_tick_keeps_tracking_existing_submission(monkeypatch, status, score, previous_pending, expected_state, minutes):
    now = monitor.COMPETITION_DEADLINE_UTC + timedelta(minutes=1)
    previous = {
        "last_submission_ref": 57646990,
        "source_sha": "a" * 40,
        "notebook_id": "owner/kernel",
        "notebook_version": 11,
        "notebook_sha256": "b" * 64,
        "submission_sha256": "c" * 64,
        "test_dataset_sha256": "d" * 64,
        "submission_evidence_path": "existing-submission-evidence.json",
        "score_evidence_path": "existing-history.json",
        "consecutive_pending_observations": previous_pending,
    }
    history = [SimpleNamespace(
        ref=57646990,
        date=monitor.COMPETITION_DEADLINE_UTC - timedelta(hours=1),
        status=f"SubmissionStatus.{status}",
        public_score=score,
    )]
    observed, checkpoints = [], []
    monkeypatch.setattr(monitor, "_now", lambda: now)
    monkeypatch.setattr(monitor, "_load_checkpoints", lambda: [previous])
    monkeypatch.setattr(monitor, "_system_boot_time", lambda _now: "2026-10-25T02:21:53Z")
    monkeypatch.setattr(monitor, "_load_runtime_state", lambda: {})
    monkeypatch.setattr(monitor, "_save_runtime_state", lambda _value: None)
    monkeypatch.setattr(monitor, "_safe_kaggle_history", lambda: history)
    monkeypatch.setattr(monitor, "_record_official_observation", lambda _history, record: observed.append(dict(record)))
    monkeypatch.setattr(monitor, "_append_checkpoint", checkpoints.append)
    monkeypatch.setattr(monitor, "_append_jsonl", lambda *_args: pytest.fail("unexpected operational ledger write"))

    code, result = monitor.tick(force=True)

    next_check = (now + timedelta(minutes=minutes)).isoformat()
    assert code == 0
    assert result["state"] == "observed"
    assert result["submission_id"] == 57646990
    assert result["score_state"] == expected_state
    assert result["next_check_at_utc"] == next_check
    assert len(observed) == 1
    assert checkpoints[-1]["official_history_next_due_utc"] == next_check
    assert monitor._日時UTC(next_check) > now
    assert "history_frozen" not in checkpoints[-1]


def test_post_deadline_observation_error_retries_in_future(monkeypatch):
    now = monitor.COMPETITION_DEADLINE_UTC + timedelta(hours=1)
    checkpoints, work_rows = [], []
    monkeypatch.setattr(monitor, "_now", lambda: now)
    monkeypatch.setattr(monitor, "_load_checkpoints", lambda: [{"last_submission_ref": 57646990}])
    monkeypatch.setattr(monitor, "_system_boot_time", lambda _now: "2026-10-25T02:21:53Z")
    monkeypatch.setattr(monitor, "_load_runtime_state", lambda: {})
    monkeypatch.setattr(monitor, "_save_runtime_state", lambda _value: None)
    monkeypatch.setattr(monitor, "_append_checkpoint", checkpoints.append)
    monkeypatch.setattr(monitor, "_append_jsonl", lambda _path, value: work_rows.append(value))

    def fail():
        raise FileNotFoundError(2, "missing local executable", "kaggle.exe")

    monkeypatch.setattr(monitor, "_safe_kaggle_history", fail)

    code, result = monitor.tick(force=True)

    next_check = (now + timedelta(minutes=15)).isoformat()
    assert code == 1
    assert result["state"] == "observation_error"
    assert result["next_check_at_utc"] == next_check
    assert checkpoints[-1]["official_history_next_due_utc"] == next_check
    assert work_rows[-1]["next_due_utc"] == next_check
    assert monitor._日時UTC(next_check) > now


def test_error_diagnostics_include_local_oserror_metadata_without_error_message():
    error = FileNotFoundError(2, "secret-api-body", r"C:\pinned-env\Scripts\kaggle.exe")
    error.winerror = 2

    details = monitor._observation_error_details(error, "history_query")

    assert details == {
        "error_type": "FileNotFoundError",
        "observation_stage": "history_query",
        "error_errno": 2,
        "error_winerror": 2,
        "error_filename": r"C:\pinned-env\Scripts\kaggle.exe",
    }
    assert "secret-api-body" not in json.dumps(details)
    assert monitor._observation_error_details(
        RuntimeError("secret-api-body"), "history_query"
    ) == {"error_type": "RuntimeError", "observation_stage": "history_query"}


def test_error_diagnostics_redact_url_filename():
    error = FileNotFoundError(2, "not found", "https://user:secret@example.test/path")

    details = monitor._observation_error_details(error, "history_query")

    assert "error_filename" not in details
    assert details["error_filename_redacted"] is True
    assert "secret" not in json.dumps(details)


@pytest.mark.parametrize("failing_stage", [
    "history_query", "build_submission_record", "record_official_observation",
])
def test_tick_localizes_oserror_stage_without_operational_writes(monkeypatch, failing_stage):
    now = datetime(2026, 10, 26, 22, 0, tzinfo=timezone.utc)
    previous = {"last_submission_ref": 57646990, "last_status": "COMPLETE", "official_score": None}
    checkpoint_rows, work_rows = [], []
    monkeypatch.setattr(monitor, "_now", lambda: now)
    monkeypatch.setattr(monitor, "_load_checkpoints", lambda: [previous])
    monkeypatch.setattr(monitor, "_system_boot_time", lambda _now: "2026-10-25T02:21:53Z")
    monkeypatch.setattr(monitor, "_load_runtime_state", lambda: {})
    monkeypatch.setattr(monitor, "_save_runtime_state", lambda _value: None)
    monkeypatch.setattr(monitor, "_append_checkpoint", checkpoint_rows.append)
    monkeypatch.setattr(monitor, "_append_jsonl", lambda _path, value: work_rows.append(value))
    monkeypatch.setattr(monitor, "_safe_kaggle_history", lambda: [])
    monkeypatch.setattr(monitor, "_build_record", lambda *_args: {})
    monkeypatch.setattr(monitor, "_record_official_observation", lambda *_args: {})

    def fail(*_args):
        raise FileNotFoundError(2, "secret-api-body", r"C:\pinned-env\Scripts\kaggle.exe")

    function = {
        "history_query": "_safe_kaggle_history",
        "build_submission_record": "_build_record",
        "record_official_observation": "_record_official_observation",
    }[failing_stage]
    monkeypatch.setattr(monitor, function, fail)

    code, result = monitor.tick(force=True)

    assert code == 1
    assert result["state"] == "observation_error"
    assert result["observation_stage"] == failing_stage
    assert result["error_errno"] == 2
    assert result["error_filename"] == r"C:\pinned-env\Scripts\kaggle.exe"
    assert result["error_location"]["function"] == "fail"
    assert checkpoint_rows[-1]["observation_error_details"]["observation_stage"] == failing_stage
    assert checkpoint_rows[-1]["blockers"] == ["kaggle_observation_error", failing_stage, "FileNotFoundError"]
    action_fragment = {
        "history_query": "履歴取得段階",
        "build_submission_record": "提出・実行記録",
        "record_official_observation": "保存先と書込状態",
    }[failing_stage]
    assert action_fragment in checkpoint_rows[-1]["next_action"]
    assert work_rows[-1]["observation_stage"] == failing_stage
    assert "secret-api-body" not in json.dumps([result, checkpoint_rows, work_rows])


def test_source_link_requires_ref_notebook_output_and_challenge_hash_match():
    ref = 57576155
    evidence = {
        "submission_ref": ref,
        "kernel": "owner/kernel",
        "kernel_version": 5,
        "candidate_evidence": {
            "source_commit": "a" * 40,
            "code_sha256": "b" * 64,
            "submission_sha256": "c" * 64,
            "challenge_sha256": "d" * 64,
        },
    }
    submission = {"kernel": "owner/kernel", "version": 5}
    run = {"code_sha256": "b" * 64}

    link = monitor._verified_source_evidence(
        ref, evidence, submission, run, "c" * 64, "d" * 64
    )
    assert link == {
        "source_sha": "a" * 40,
        "test_dataset_sha256": "d" * 64,
        "submission_evidence_path": "運用/証拠/ARC2_公式スコア起点_20261024/公式提出-57576155.json",
    }
    assert monitor._verified_source_evidence(
        ref, evidence, submission, run, "wrong-output", "d" * 64
    ) is None
    assert monitor._verified_source_evidence(
        ref + 1, evidence, submission, run, "c" * 64, "d" * 64
    ) is None


def test_submission_sha_follows_recorded_output_path_and_checks_expected_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    record_dir = tmp_path / "出力" / "Kaggle" / "kernel" / "v7"
    output_dir = record_dir / "remote-output-v9"
    output_dir.mkdir(parents=True)
    submission_path = output_dir / "submission.json"
    submission_path.write_bytes(b'{"candidate":9}')
    digest = __import__("hashlib").sha256(submission_path.read_bytes()).hexdigest()
    submission = {"kernel": "owner/kernel", "version": 9}
    run = {
        "_source_record_dir": str(record_dir),
        "output_validation_evidence": "remote-output-v9/output-validation.json",
        "submission_sha256": digest,
    }

    assert monitor._submission_sha(submission, run) == digest
    assert monitor._submission_sha(submission, {**run, "submission_sha256": "0" * 64}) is None


def test_official_observation_writes_evidence_and_both_ledgers(tmp_path, monkeypatch):
    monkeypatch.setattr(monitor, "ROOT", tmp_path)
    monkeypatch.setattr(monitor, "UNIFIED_EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(monitor, "SCORE_LEDGER", tmp_path / "score-ledger.jsonl")
    monkeypatch.setattr(monitor, "WORK_LEDGER", tmp_path / "work-ledger.jsonl")
    prior_path = tmp_path / "evidence" / "previous.json"
    prior_path.parent.mkdir(parents=True)
    prior_row = {
        "date": "2026-10-24T00:12:39.127000",
        "description": "ARC2 candidate",
        "fileName": "submission.json",
        "privateScore": "",
        "publicScore": "0.00",
        "ref": 57576155,
        "status": "SubmissionStatus.COMPLETE",
    }
    prior_path.write_text(json.dumps({"rows": [prior_row]}), encoding="utf-8")
    monitor.SCORE_LEDGER.write_text(json.dumps({
        "submission_id": "57576155",
        "official_score": 0.0,
        "arc2_solved_hold_fallback": {"fallback_count": 256},
    }) + "\n", encoding="utf-8")

    class SubmissionStatus:
        name = "COMPLETE"

        def __str__(self):
            return "SubmissionStatus.COMPLETE"

    history = [SimpleNamespace(
        date=datetime(2026, 10, 24, 0, 12, 39, 127000),
        description="ARC2 candidate",
        file_name="submission.json",
        public_score="0.00",
        ref=57576155,
        status=SubmissionStatus(),
    )]
    record = {
        "last_submission_ref": 57576155,
        "last_status": "COMPLETE",
        "official_score": "0.00",
        "observed_at_utc": "2026-10-24T17:43:51+00:00",
        "next_check_at_utc": "2026-10-24T18:43:51+00:00",
        "score_evidence_path": "evidence/previous.json",
        "submission_evidence_path": None,
        "notebook_id": "owner/kernel",
        "notebook_version": 5,
        "source_sha": "a" * 40,
        "test_dataset_sha256": "b" * 64,
        "submission_sha256": "c" * 64,
        "blockers": [],
        "kaggle_cli_discovery": {"selected_source": "repo_venv", "repo_cli_lock_versions_match": True},
    }

    evidence = monitor._record_official_observation(history, record)
    score_rows = [json.loads(line) for line in monitor.SCORE_LEDGER.read_text(encoding="utf-8").splitlines()]
    work_rows = [json.loads(line) for line in monitor.WORK_LEDGER.read_text(encoding="utf-8").splitlines()]

    assert evidence["history_unchanged"] is True
    assert evidence["kaggle_cli_discovery"] == record["kaggle_cli_discovery"]
    assert record["score_evidence_path"].startswith("evidence/official-history-")
    assert score_rows[-1]["official_score"] == 0.0
    assert score_rows[-1]["score_delta"] == 0.0
    assert score_rows[-1]["history_unchanged"] is True
    assert score_rows[-1]["arc2_solved_hold_fallback"] == {"fallback_count": 256}
    assert work_rows[-1]["submission_or_rerun_performed"] is False
    assert work_rows[-1]["kaggle_cli_source"] == "repo_venv"


def test_complete_timeout_detail_is_failed_and_not_scored(monkeypatch):
    payload = [{"date": "2026-10-27T00:17:10Z", "ref": 57682971,
                "status": "SubmissionStatus.COMPLETE", "publicScore": ""}]

    def fake_run(command, **kwargs):
        out = ("Submission Ref: 57682971\nStatus: COMPLETE\n"
               "Error: Notebook Timeout\nPublic Score: \n") if "submission" in command else json.dumps(payload)
        return subprocess.CompletedProcess(command, 0, out, "")

    monkeypatch.setattr(monitor, "_kaggle_cli_prefix", lambda: ["kaggle"])
    monkeypatch.setattr(monitor.subprocess, "run", fake_run)
    row = monitor._safe_kaggle_history()[0]
    assert monitor._status_state("COMPLETE", row.public_score, row.error_description) == "FAILED"
    assert monitor._status_state("COMPLETE", "0.00", row.error_description) == "SCORE_UNOBSERVED"


def test_detail_identity_mismatch_is_not_accepted(monkeypatch):
    payload = [{"date": "2026-10-27T00:17:10Z", "ref": 57682971,
                "status": "SubmissionStatus.COMPLETE", "publicScore": ""}]

    def fake_run(command, **kwargs):
        out = ("Submission Ref: 123\nStatus: COMPLETE\nPublic Score: \n"
               if "submission" in command else json.dumps(payload))
        return subprocess.CompletedProcess(command, 0, out, "")

    monkeypatch.setattr(monitor, "_kaggle_cli_prefix", lambda: ["kaggle"])
    monkeypatch.setattr(monitor.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="differs"):
        monitor._safe_kaggle_history()


def test_submission_error_record_does_not_persist_untrusted_details():
    now = datetime(2026, 10, 28, 18, tzinfo=timezone.utc)
    row = SimpleNamespace(ref=42, date=now, status="COMPLETE", public_score="",
                          error_description="Notebook failed with secret-like-value")
    previous = {"last_submission_ref": 42, "source_sha": "a", "test_dataset_sha256": "b",
                "submission_evidence_path": "c", "notebook_id": "owner/kernel",
                "notebook_version": 1, "submission_sha256": "d"}
    record = monitor._build_record([row], now, previous)
    assert record["score_state"] == "FAILED"
    assert record["error_category"] == "OTHER_ERROR"
    assert record["error_details_present"] is True
    assert "secret-like-value" not in json.dumps(record)

