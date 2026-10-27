#!/usr/bin/env python3
"""公式Kaggle提出履歴をread-onlyで追跡し、再開可能なcheckpointを追記する。"""

from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
import hashlib
from importlib import metadata as importlib_metadata
import io
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import tomllib
import traceback
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from 接続.Kaggle操作 import 大会, _日時UTC, _数値スコアか  # noqa: E402

CHECKPOINT = ROOT / "運用/ARC2_公式スコア運用チェックポイント.jsonl"
RUNTIME_STATE = ROOT / "運用/ARC2_Kaggleスコア監視状態.json"
SOURCE_EVIDENCE_DIR = ROOT / "運用/証拠/ARC2_公式スコア起点_20261024"
TEST_CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
UNIFIED_EVIDENCE_DIR = ROOT / "運用/証拠/ARC26-UNIFIED"
SCORE_LEDGER = ROOT / "運用/ARC26-UNIFIED/score-ledger.jsonl"
WORK_LEDGER = ROOT / "運用/ARC26-UNIFIED/work-ledger.jsonl"
PENDING_INTERVALS_MINUTES = (5, 15, 30, 60)
BOOT_TIME_TOLERANCE_SECONDS = 5
LAST_CLI_DISCOVERY: dict = {}
COMPETITION_DEADLINE_UTC = datetime(2026, 11, 2, 23, 59, tzinfo=timezone.utc)
EXPERIMENT_CHECKPOINT_FIELDS = (
    "experiment_id",
    "worker_pid",
    "process_status",
    "worker_cpu_seconds",
    "wall_elapsed_seconds",
    "eligible_tasks_done",
    "eligible_tasks_total",
    "paired_loo_folds_done",
    "paired_loo_folds_total",
    "progress_stall_duration_seconds",
    "runtime_budget_seconds",
    "runtime_budget_exceeded",
    "stack_capture_file",
    "stack_capture_sha256",
    "stack_line",
    "stack_source_text",
    "stack_still_in_generic_candidate_subset_enumeration",
    "runtime_source_sha256",
    "production_source_changed",
    "evidence_file",
    "evidence_sha256",
    "official_submission_or_quota_use",
)
CANDIDATE_CHECKPOINT_FIELDS = (
    "candidate_phase",
    "candidate_kernel",
    "candidate_version",
    "candidate_kernel_status",
    "candidate_code_sha256",
    "candidate_metadata_sha256",
    "candidate_payload_sha256",
    "candidate_source_commit",
    "candidate_adapter_sha256",
    "candidate_hds_connector_sha256",
    "candidate_submission_sha256",
    "candidate_output_summary_file",
    "candidate_output_summary_sha256",
    "candidate_test_tasks",
    "candidate_test_examples",
    "candidate_fallback_examples",
    "candidate_first_attempt_different_from_input",
    "candidate_distinct_second_attempts",
    "candidate_test_correctness",
    "candidate_loo_report",
    "candidate_loo_report_sha256",
    "candidate_loo_previous_exact",
    "candidate_loo_current_exact",
    "candidate_loo_delta_exact",
    "candidate_loo_regressions",
    "candidate_loo_previous_fallback",
    "candidate_loo_current_fallback",
    "candidate_loo_source_hashes_unchanged",
    "candidate_next_action",
    "candidate_next_due_utc",
    "candidate_submission_performed",
    "candidate_quota_gate_allowed",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_checkpoints() -> list[dict]:
    if not CHECKPOINT.exists():
        return []
    rows = []
    for line in CHECKPOINT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def _append_checkpoint(value: dict) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    with CHECKPOINT.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _system_boot_time(now: datetime) -> str | None:
    if os.name != "nt":
        return None
    try:
        import ctypes

        get_tick_count = ctypes.windll.kernel32.GetTickCount64
        get_tick_count.argtypes = []
        get_tick_count.restype = ctypes.c_ulonglong
        uptime_ms = get_tick_count()
        return (now - timedelta(milliseconds=uptime_ms)).replace(microsecond=0).isoformat()
    except Exception:
        return None


def _load_runtime_state() -> dict:
    try:
        value = json.loads(RUNTIME_STATE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_runtime_state(value: dict) -> None:
    RUNTIME_STATE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=RUNTIME_STATE.parent,
        prefix=RUNTIME_STATE.name + ".", suffix=".tmp", delete=False,
    ) as stream:
        temp_path = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.write("\n")
    os.replace(temp_path, RUNTIME_STATE)


def _should_resume(now: datetime, runtime: dict, boot_time: str | None) -> bool:
    if not runtime:
        return True
    prior_boot = runtime.get("boot_time_utc")
    if boot_time and prior_boot and prior_boot != boot_time:
        current_boot = _日時UTC(boot_time)
        previous_boot = _日時UTC(prior_boot)
        # now - GetTickCount64 is an estimate and can cross a one-second
        # rounding boundary between ticks without an actual system reboot.
        if (
            current_boot is None
            or previous_boot is None
            or abs((current_boot - previous_boot).total_seconds()) > BOOT_TIME_TOLERANCE_SECONDS
        ):
            return True
    last_tick = _日時UTC(runtime.get("last_monitor_tick_at_utc"))
    return last_tick is None or now - last_tick > timedelta(minutes=15)


def _observation_error_details(error: Exception, stage: str) -> dict:
    """Localize an observation failure without serializing API bodies or commands."""
    details = {"error_type": type(error).__name__, "observation_stage": stage}
    discovery = getattr(error, "kaggle_cli_discovery", None)
    if isinstance(discovery, dict):
        # This payload is constructed from explicit local-path/version checks
        # below, never from API bodies, credentials, environment or commands.
        details["cli_discovery"] = discovery
    if isinstance(error, OSError):
        for name in ("errno", "winerror"):
            value = getattr(error, name, None)
            if isinstance(value, int):
                details[f"error_{name}"] = value
        filename = getattr(error, "filename", None)
        if isinstance(filename, (str, bytes, os.PathLike)):
            value = os.fsdecode(filename)
            # OSError.filename is useful for local paths; never preserve URLs
            # (which may embed credentials) or multiline command-like values.
            if "://" not in value and not any(character in value for character in "\r\n\0"):
                details["error_filename"] = value
            else:
                details["error_filename_redacted"] = True

    frames = traceback.extract_tb(error.__traceback__)
    for frame in reversed(frames):
        try:
            relative = Path(frame.filename).resolve().relative_to(ROOT.resolve())
        except (OSError, ValueError):
            continue
        details["error_location"] = {
            "file": relative.as_posix(), "function": frame.name, "line": frame.lineno,
        }
        break
    return details


def _status_state(status: str, score: object) -> str:
    if status == "COMPLETE":
        return "NUMERIC" if _数値スコアか(score) else "SCORE_UNOBSERVED"
    if status in {"PENDING", "SUBMITTED", "RUNNING"}:
        return "PENDING"
    if status in {"FAILED", "ERROR", "CANCEL_REQUESTED", "CANCEL_ACKNOWLEDGED"}:
        return "FAILED"
    return "IN_PROGRESS"


def _next_interval_minutes(score_state: str, consecutive_pending_observations: int) -> int:
    if score_state == "PENDING":
        index = max(0, min(consecutive_pending_observations - 1, len(PENDING_INTERVALS_MINUTES) - 1))
        return PENDING_INTERVALS_MINUTES[index]
    if score_state in {"NUMERIC", "SCORE_UNOBSERVED", "FAILED"}:
        return 60
    return 15


def _submission_record(ref: int) -> tuple[dict, dict]:
    base = ROOT / "出力/Kaggle"
    for path in base.rglob(f"提出記録-{ref}.json"):
        try:
            submission = json.loads(path.read_text(encoding="utf-8"))
            run_path = path.parent / "実行記録.json"
            run = json.loads(run_path.read_text(encoding="utf-8")) if run_path.is_file() else {}
            if isinstance(run, dict):
                run["_source_record_dir"] = str(path.parent)
            return submission, run
        except (OSError, ValueError):
            continue
    return {}, {}


def _submission_sha(submission: dict, run_record: dict | None = None) -> str | None:
    kernel = submission.get("kernel")
    version = submission.get("version")
    if not isinstance(kernel, str) or "/" not in kernel or type(version) is not int:
        return None
    owner, slug = kernel.split("/", 1)
    folder = ROOT / "出力/Kaggle" / slug / f"v{version}"
    candidates: list[Path] = []
    if isinstance(run_record, dict):
        record_dir = run_record.get("_source_record_dir")
        output_validation = run_record.get("output_validation_evidence")
        if isinstance(record_dir, str) and isinstance(output_validation, str):
            relative_validation = Path(output_validation)
            if not relative_validation.is_absolute() and ".." not in relative_validation.parts:
                candidates.append(Path(record_dir) / relative_validation.parent / "submission.json")
    candidates.extend((folder / "submission.json", *folder.glob("**/submission.json")))
    expected_sha = run_record.get("submission_sha256") if isinstance(run_record, dict) else None
    for candidate in dict.fromkeys(candidates):
        if candidate.is_file():
            import hashlib

            actual_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
            if expected_sha is None or actual_sha == expected_sha:
                return actual_sha
    return None


def _verified_source_evidence(
    ref: int,
    evidence: dict,
    submission: dict,
    run_record: dict,
    submission_sha: str | None,
    challenge_sha: str | None,
) -> dict | None:
    candidate = evidence.get("candidate_evidence")
    source_sha = candidate.get("source_commit") if isinstance(candidate, dict) else None
    notebook = evidence.get("kernel")
    version = evidence.get("kernel_version")
    if (
        evidence.get("submission_ref") != ref
        or notebook != submission.get("kernel")
        or version != submission.get("version")
        or candidate.get("code_sha256") != run_record.get("code_sha256")
        or candidate.get("submission_sha256") != submission_sha
        or candidate.get("challenge_sha256") != challenge_sha
        or not isinstance(source_sha, str)
        or len(source_sha) != 40
        or any(character not in "0123456789abcdef" for character in source_sha.lower())
    ):
        return None
    return {
        "source_sha": source_sha,
        "test_dataset_sha256": challenge_sha,
        "submission_evidence_path": str(
            (SOURCE_EVIDENCE_DIR / f"公式提出-{ref}.json").relative_to(ROOT)
        ).replace("\\", "/"),
    }


def _current_submission_source_evidence(
    ref: int,
    submission: dict,
    run_record: dict,
    submission_sha: str | None,
) -> dict | None:
    path = SOURCE_EVIDENCE_DIR / f"公式提出-{ref}.json"
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
        challenge_sha = hashlib.sha256(TEST_CHALLENGE.read_bytes()).hexdigest()
    except (OSError, ValueError):
        return None
    return _verified_source_evidence(
        ref, evidence, submission, run_record, submission_sha, challenge_sha
    )


def _repo_venv_cli_prefix(discovery: dict) -> list[str] | None:
    """Use only this ARC2 repo's exact locked CLI installation as a fallback."""
    expected = {"kaggle": "2.2.5", "kagglesdk": "0.1.38"}
    venv = ROOT / ".venv"
    python = venv / "Scripts" / "python.exe"
    site_packages = venv / "Lib" / "site-packages"
    discovery["repo_cli_python_path"] = str(python)
    discovery["repo_cli_python_exists"] = python.is_file()
    discovery["repo_cli_module_exists"] = (site_packages / "kaggle" / "__main__.py").is_file()
    discovery["repo_cli_track_matches"] = 大会 == "arc-prize-2026-arc-agi-2"
    try:
        if not venv.resolve().is_relative_to(ROOT.resolve()):
            discovery["repo_cli_validation_status"] = "venv_outside_repo"
            return None
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
        dev_pins = project.get("dependency-groups", {}).get("dev", [])
        discovery["repo_cli_project_matches"] = project.get("project", {}).get("name") == "arc-2-agi-solver"
        discovery["repo_cli_project_pins_match"] = all(f"{name}=={version}" in dev_pins for name, version in expected.items())
        locked = {name: {item.get("version") for item in lock.get("package", []) if item.get("name") == name} for name in expected}
        discovery["repo_cli_lock_versions_match"] = all(locked[name] == {version} for name, version in expected.items())
        installed_matches = True
        for name, version in expected.items():
            candidates = list(site_packages.glob(f"{name}-*.dist-info"))
            discovery[f"repo_cli_{name}_dist_info_count"] = len(candidates)
            matches = len(candidates) == 1
            for candidate in candidates:
                distribution = importlib_metadata.Distribution.at(candidate)
                matches = matches and distribution.metadata.get("Name", "").lower() == name and distribution.version == version
            discovery[f"repo_cli_{name}_version_matches"] = matches
            installed_matches = installed_matches and matches
        discovery["repo_cli_validation_status"] = "checked"
    except (OSError, ValueError, TypeError) as error:
        discovery["repo_cli_validation_status"] = type(error).__name__
        if isinstance(error, OSError):
            discovery["repo_cli_validation_errno"] = error.errno
        return None
    if all(discovery.get(key) is True for key in (
        "repo_cli_python_exists", "repo_cli_module_exists", "repo_cli_track_matches",
        "repo_cli_project_matches", "repo_cli_project_pins_match", "repo_cli_lock_versions_match",
    )) and installed_matches:
        try:
            runtime_check = subprocess.run(
                [str(python), "-c", "import kaggle; from certifi import where; where()"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            discovery["repo_cli_runtime_validation_status"] = type(error).__name__
            if isinstance(error, OSError):
                discovery["repo_cli_runtime_validation_errno"] = error.errno
            return None
        discovery["repo_cli_runtime_importable"] = runtime_check.returncode == 0
        discovery["repo_cli_runtime_returncode"] = runtime_check.returncode
        if runtime_check.returncode != 0:
            discovery["repo_cli_validation_status"] = "runtime_import_failed"
            return None
        discovery["repo_cli_runtime_validation_status"] = "passed"
        return [str(python), "-m", "kaggle"]
    return None


def _kaggle_cli_prefix() -> list[str]:
    """Prefer this repo's pinned CLI environment, then fall back to uv tooling."""
    global LAST_CLI_DISCOVERY
    manifest_path = ROOT / "運用" / "ARC26-UNIFIED" / "kaggle-cli-environment.json"
    discovery = {
        "root": str(ROOT),
        "root_exists": ROOT.is_dir(),
        "python_executable": sys.executable,
        "manifest_path": str(manifest_path),
    }
    LAST_CLI_DISCOVERY = discovery
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        discovery["manifest_read_status"] = "ok"
    except (OSError, json.JSONDecodeError) as error:
        manifest = None
        discovery["manifest_read_status"] = type(error).__name__
        if isinstance(error, OSError):
            discovery["manifest_read_errno"] = error.errno
            if isinstance(getattr(error, "winerror", None), int):
                discovery["manifest_read_winerror"] = error.winerror
    discovery["manifest_track_matches"] = isinstance(manifest, dict) and manifest.get("track") == "ARC2"
    discovery["manifest_cli_version_matches"] = isinstance(manifest, dict) and manifest.get("kaggle_cli") == "Kaggle CLI 2.2.5"
    if isinstance(manifest, dict):
        venv_path = manifest.get("venv_path")
        if (isinstance(venv_path, str) and venv_path and "://" not in venv_path
                and not any(character in venv_path for character in "\r\n\0")):
            project_cli = Path(venv_path) / "Scripts" / "kaggle.exe"
            discovery["manifest_cli_path"] = str(project_cli)
            discovery["manifest_cli_exists"] = project_cli.is_file()
            if (discovery["manifest_track_matches"] and discovery["manifest_cli_version_matches"]
                    and discovery["manifest_cli_exists"]):
                discovery["selected_source"] = "manifest"
                return [str(project_cli)]

    if manifest is None or (discovery["manifest_track_matches"] and discovery["manifest_cli_version_matches"]):
        repo_prefix = _repo_venv_cli_prefix(discovery)
        if repo_prefix is not None:
            discovery["selected_source"] = "repo_venv"
            return repo_prefix
    else:
        discovery["repo_cli_validation_status"] = "manifest_track_or_version_mismatch"

    uvx = shutil.which("uvx")
    discovery["uvx_resolved_path"] = uvx
    if uvx:
        discovery["selected_source"] = "uvx"
        return [uvx, "--from", "kaggle==2.2.5", "kaggle"]
    uv = shutil.which("uv")
    discovery["uv_resolved_path"] = uv
    if uv:
        discovery["selected_source"] = "uv"
        return [uv, "tool", "run", "--from", "kaggle==2.2.5", "kaggle"]

    user_scripts = (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Python"
        / f"Python{sys.version_info.major}{sys.version_info.minor}"
        / "Scripts"
    )
    discovery["user_scripts_path"] = str(user_scripts)
    for name, prefix in (
        ("uvx.exe", ["--from", "kaggle==2.2.5", "kaggle"]),
        ("uv.exe", ["tool", "run", "--from", "kaggle==2.2.5", "kaggle"]),
    ):
        candidate = user_scripts / name
        exists = candidate.is_file()
        discovery[f"user_{name}_exists"] = exists
        if exists:
            discovery["selected_source"] = f"user_scripts_{name}"
            return [str(candidate), *prefix]
    discovery["selected_source"] = "none"
    error = FileNotFoundError(
        "a manifest-pinned project Kaggle CLI or uvx/uv is required (Kaggle CLI 2.2.5)"
    )
    error.kaggle_cli_discovery = discovery
    raise error


def _parse_kaggle_json_output(stdout: str):
    lines = stdout.lstrip("\ufeff").splitlines()
    warning_prefix = "Warning: Looks like you're using an outdated `kaggle` version "
    while lines and (not lines[0].strip() or lines[0].startswith(warning_prefix)):
        lines.pop(0)
    return json.loads("\n".join(lines))


def _normalize_cli_timestamp(value) -> str:
    parsed = _日時UTC(value)
    if parsed is None and isinstance(value, str):
        try:
            parsed = datetime.strptime(value, "%Y/%m/%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if parsed is None:
        raise ValueError("Kaggle CLI history contains an unparseable timestamp")
    return parsed.isoformat().replace("+00:00", "Z")


def _safe_kaggle_history():
    command = [
        *_kaggle_cli_prefix(),
        "competitions",
        "submissions",
        大会,
        "--format",
        "json",
        "--page-size",
        "100",
        "-q",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"pinned Kaggle CLI exited with code {completed.returncode}")
    parsed = _parse_kaggle_json_output(completed.stdout)
    if not isinstance(parsed, list):
        raise ValueError("Kaggle history response is not a list")
    return [
        SimpleNamespace(
            date=_normalize_cli_timestamp(row.get("date")),
            description=row.get("description"),
            file_name=row.get("fileName", row.get("file_name")),
            public_score=row.get("publicScore", row.get("public_score")),
            private_score=row.get("privateScore", row.get("private_score")),
            ref=row.get("ref"),
            status=row.get("status"),
        )
        for row in parsed
        if isinstance(row, dict)
    ]


def _status_name(status) -> str:
    if status is None:
        return "UNKNOWN"
    name = getattr(status, "name", None)
    value = str(name if name is not None else status).rsplit(".", 1)[-1].upper()
    return value or "UNKNOWN"


def _history_rows(history: list) -> list[dict]:
    rows = []
    for row in history:
        if row is None:
            continue
        submitted_at = _日時UTC(getattr(row, "date", None))
        if submitted_at is None:
            raise ValueError("official history contains an unparseable timestamp")
        status = getattr(row, "status", None)
        public_score = getattr(row, "public_score", None)
        status_name = _status_name(status)
        rows.append({
            "date": submitted_at.isoformat().replace("+00:00", "Z"),
            "description": getattr(row, "description", None),
            "fileName": getattr(row, "file_name", None) or "submission.json",
            "privateScore": "",
            "publicScore": "" if public_score is None else str(public_score),
            "ref": int(row.ref),
            "status": f"SubmissionStatus.{status_name}" if status_name != "UNKNOWN" else "UNKNOWN",
        })
    return _canonical_history_rows(rows)


def _canonical_history_rows(rows: list[dict]) -> list[dict]:
    canonical = []
    for row in rows:
        submitted_at = _日時UTC(row.get("date"))
        if submitted_at is None:
            raise ValueError("official history contains an unparseable timestamp")
        status = row.get("status")
        public_score = row.get("publicScore", row.get("public_score"))
        canonical.append({
            "date": submitted_at.isoformat().replace("+00:00", "Z"),
            "description": row.get("description"),
            "fileName": row.get("fileName", row.get("file_name")) or "submission.json",
            "privateScore": "",
            "publicScore": "" if public_score is None else str(public_score),
            "ref": int(row["ref"]),
            "status": str(status) if status is not None else "UNKNOWN",
        })
    return sorted(canonical, key=lambda row: row["date"], reverse=True)


def _previous_history_rows(record: dict) -> list[dict] | None:
    relative = record.get("score_evidence_path")
    if not isinstance(relative, str):
        return None
    path = ROOT / relative
    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    rows = evidence.get("rows") if isinstance(evidence, dict) else None
    return _canonical_history_rows(rows) if isinstance(rows, list) else None


def _append_jsonl(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def _record_official_observation(history: list, record: dict) -> dict:
    current_rows = _history_rows(history)
    previous_rows = _previous_history_rows(record)
    history_unchanged = previous_rows == current_rows if previous_rows is not None else None
    observed_at = _日時UTC(record.get("observed_at_utc"))
    if observed_at is None:
        raise ValueError("observation timestamp is invalid")
    stamp = observed_at.strftime("%Y%m%dT%H%M%SZ")
    evidence_path = UNIFIED_EVIDENCE_DIR / f"official-history-{stamp}.json"
    suffix = 2
    while evidence_path.exists():
        evidence_path = UNIFIED_EVIDENCE_DIR / f"official-history-{stamp}-{suffix:02d}.json"
        suffix += 1
    refs = [row["ref"] for row in current_rows]
    previous_refs = [row["ref"] for row in previous_rows] if previous_rows is not None else None
    latest = max(current_rows, key=lambda row: row["date"])
    evidence = {
        "command": "KaggleApi.competition_submissions (read-only)",
        "current_refs": refs,
        "history_unchanged": history_unchanged,
        "latest_submission": latest,
        "new_submission_or_rerun_performed": False,
        "observed_at_utc": observed_at.isoformat().replace("+00:00", "Z"),
        "previous_refs": previous_refs,
        "private_score_state": "not provided",
        "quota_rechecked": False,
        "returncode": 0,
        "rows": current_rows,
        "kaggle_cli_discovery": record.get("kaggle_cli_discovery"),
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    evidence_sha = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    evidence_rel = evidence_path.relative_to(ROOT).as_posix()
    record["score_evidence_path"] = evidence_rel
    record["score_evidence_sha256"] = evidence_sha
    record["official_history_refs"] = refs
    record["history_unchanged"] = history_unchanged

    previous_ledger = []
    if SCORE_LEDGER.is_file():
        for line in SCORE_LEDGER.read_text(encoding="utf-8").splitlines():
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    previous_ledger.append(value)
    prior_score = next((
        row.get("official_score") for row in reversed(previous_ledger)
        if _数値スコアか(row.get("official_score"))
    ), None)
    raw_score = record.get("official_score")
    current_score = float(raw_score) if _数値スコアか(raw_score) else None
    prior_numeric = float(prior_score) if _数値スコアか(prior_score) else None
    score_delta = current_score - prior_numeric if current_score is not None and prior_numeric is not None else None
    same_submission = next((
        row for row in reversed(previous_ledger)
        if str(row.get("submission_id")) == str(record["last_submission_ref"])
    ), {})
    submission_evidence = record.get("submission_evidence_path")
    evidence_files = [evidence_rel]
    if isinstance(submission_evidence, str):
        evidence_files.append(submission_evidence.replace("\\", "/"))
    score_row = {
        "track": "ARC2",
        "competition_slug": "arc-prize-2026-arc-agi-2",
        "submission_id": str(record["last_submission_ref"]),
        "submitted_at_utc": latest["date"],
        "observed_at_utc": evidence["observed_at_utc"],
        "official_status": record.get("last_status"),
        "official_score": current_score,
        "score_unit": "public_score",
        "notebook_slug": record.get("notebook_id"),
        "notebook_version": record.get("notebook_version"),
        "source_commit": record.get("source_sha"),
        "source_commit_scope": "Provenance commit; exact runnable bytes are identified by the linked Notebook and payload evidence.",
        "input_sha256": record.get("test_dataset_sha256"),
        "output_sha256": record.get("submission_sha256"),
        "input_output_sha256_scope": "Linked visible/local pre-submission artifacts; this history query does not observe hidden scoring rerun artifacts.",
        "hidden_scoring_input_sha256": None,
        "hidden_scoring_output_sha256": None,
        "local_score_and_dataset": None,
        "arc2_solved_hold_fallback": same_submission.get("arc2_solved_hold_fallback"),
        "arc3_actions_levels_games": None,
        "previous_score": prior_numeric,
        "score_delta": score_delta,
        "experiment_id": f"ARC2 official history read-only observation {stamp}",
        "change_sha": None,
        "failure_signature": "; ".join(record.get("blockers", [])) or None,
        "next_due_utc": record.get("next_check_at_utc"),
        "evidence_files": evidence_files,
        "evidence_sha256": evidence_sha,
        "history_unchanged": history_unchanged,
        "official_history_refs": refs,
        "private_score_state": "not provided",
        "quota_last_observation": None,
        "submission_or_rerun_performed": False,
    }
    if current_score is None:
        score_row["why_unobserved"] = "Official history returned no numeric public score."
    _append_jsonl(SCORE_LEDGER, score_row)
    _append_jsonl(WORK_LEDGER, {
        "event": "ARC2 official Kaggle history read-only observation",
        "track": "ARC2",
        "observed_at_utc": evidence["observed_at_utc"],
        "submission_id": str(record["last_submission_ref"]),
        "official_status": record.get("last_status"),
        "official_score": current_score,
        "history_unchanged": history_unchanged,
        "evidence_files": evidence_files,
        "evidence_sha256": evidence_sha,
        "submission_or_rerun_performed": False,
        "kaggle_cli_source": (record.get("kaggle_cli_discovery") or {}).get("selected_source"),
    })
    return evidence


def _build_record(history: list, now: datetime, previous: dict) -> dict:
    parsed = [(row, _日時UTC(getattr(row, "date", None))) for row in history if row is not None]
    if not parsed:
        raise LookupError("official submission history is empty")
    if any(stamp is None for _, stamp in parsed):
        raise ValueError("official history contains an unparseable timestamp")
    row, submitted_at = max(parsed, key=lambda item: item[1])
    ref = int(row.ref)
    status = _status_name(getattr(row, "status", None))
    raw_score = getattr(row, "public_score", None)
    score_state = _status_state(status, raw_score)
    same_ref = previous.get("last_submission_ref") == ref
    pending_count = int(previous.get("consecutive_pending_observations", 0)) + 1 if same_ref and score_state == "PENDING" else (1 if score_state == "PENDING" else 0)
    interval = _next_interval_minutes(score_state, pending_count)
    next_check = now + timedelta(minutes=interval)
    if same_ref:
        source_sha = previous.get("source_sha")
        notebook_id = previous.get("notebook_id")
        notebook_version = previous.get("notebook_version")
        notebook_sha = previous.get("notebook_sha256")
        submission_sha = previous.get("submission_sha256")
        input_sha = previous.get("test_dataset_sha256")
        evidence_path = previous.get("score_evidence_path")
        submission_evidence_path = previous.get("submission_evidence_path")
        if source_sha is None or input_sha is None or submission_evidence_path is None:
            submission_record, run_record = _submission_record(ref)
            current_submission_sha = _submission_sha(submission_record, run_record) if submission_record else None
            source_link = _current_submission_source_evidence(
                ref, submission_record, run_record,
                current_submission_sha or submission_sha,
            ) if submission_record else None
            if source_link is not None:
                source_sha = source_link["source_sha"]
                input_sha = source_link["test_dataset_sha256"]
                submission_evidence_path = source_link["submission_evidence_path"]
                notebook_id = submission_record.get("kernel")
                notebook_version = submission_record.get("version")
                notebook_sha = run_record.get("code_sha256")
                submission_sha = current_submission_sha or submission_sha
    else:
        submission_record, run_record = _submission_record(ref)
        source_sha = None
        notebook_id = submission_record.get("kernel")
        notebook_version = submission_record.get("version")
        notebook_sha = run_record.get("code_sha256")
        submission_sha = _submission_sha(submission_record, run_record) if submission_record else None
        input_sha = None
        evidence_path = None
        submission_evidence_path = None
        source_link = _current_submission_source_evidence(
            ref, submission_record, run_record, submission_sha
        ) if submission_record else None
        if source_link is not None:
            source_sha = source_link["source_sha"]
            input_sha = source_link["test_dataset_sha256"]
            submission_evidence_path = source_link["submission_evidence_path"]
    blockers = []
    if source_sha is None or notebook_id is None or submission_sha is None:
        blockers.append("submission_to_source_output_SHA_link_needs_Codex_evidence_update")
    next_action = {
        "PENDING": "同一IDの数値スコアを追跡する。新規提出を保留し、v6に従い公開データの原因分析・同条件検証を続ける。",
        "NUMERIC": "数値公式スコアを固定し、P5の原因分析・同条件検証を続ける。",
        "SCORE_UNOBSERVED": "COMPLETEの空スコアを異常として採点経路を診断する。",
        "FAILED": "失敗詳細を確認し、採点経路の最小修復へ戻る。",
        "IN_PROGRESS": "状態を再照会する。",
    }[score_state]
    record = {
        "track": "ARC2",
        "instruction_id": previous.get("instruction_id", "ARC2-SCORE-GATE-20261024"),
        "phase": "P2_MONITORING" if score_state in {"PENDING", "IN_PROGRESS"} else "P5_CAUSE_ANALYSIS_IN_PROGRESS" if score_state == "NUMERIC" else "P3_SCORING_PATH_DIAGNOSIS",
        "score_state": score_state,
        "last_submission_ref": ref,
        "last_status": status,
        "official_score": str(raw_score).strip() if _数値スコアか(raw_score) else None,
        "observed_at_utc": now.isoformat(),
        "last_submitted_utc_day": submitted_at.date().isoformat(),
        "next_check_at_utc": next_check.isoformat(),
        "source_sha": source_sha,
        "notebook_id": notebook_id,
        "notebook_version": notebook_version,
        "notebook_sha256": notebook_sha,
        "submission_sha256": submission_sha,
        "test_dataset_sha256": input_sha,
        "submission_evidence_path": submission_evidence_path,
        "score_evidence_path": evidence_path,
        "blockers": blockers,
        "next_action": next_action,
        "consecutive_pending_observations": pending_count,
        "monitor_interval_minutes": interval,
        "monitor_boot_time_utc": _system_boot_time(now),
        "checkpoint_created_at_utc": now.isoformat(),
    }
    for field in (*EXPERIMENT_CHECKPOINT_FIELDS, *CANDIDATE_CHECKPOINT_FIELDS):
        if field in previous:
            record[field] = previous[field]
    experiment_next_check = previous.get("experiment_next_check_at_utc")
    if experiment_next_check is None and previous.get("process_status") == "ACTIVE":
        experiment_next_check = previous.get("next_check_at_utc")
    if experiment_next_check is not None:
        record["experiment_next_check_at_utc"] = experiment_next_check
    if previous.get("experiment_next_action") is not None:
        record["experiment_next_action"] = previous["experiment_next_action"]
    elif previous.get("process_status") == "ACTIVE" and previous.get("next_action") is not None:
        record["experiment_next_action"] = previous["next_action"]
    record["official_history_next_due_utc"] = record["next_check_at_utc"]
    return record


def tick(*, force: bool = False) -> tuple[int, dict]:
    now = _now()
    rows = _load_checkpoints()
    if not rows:
        return 1, {"state": "checkpoint_missing", "path": str(CHECKPOINT)}
    previous = rows[-1]
    boot_time = _system_boot_time(now)
    runtime = _load_runtime_state()
    resumed = _should_resume(now, runtime, boot_time)
    _save_runtime_state({"last_monitor_tick_at_utc": now.isoformat(), "boot_time_utc": boot_time})
    due_at = _日時UTC(previous.get("next_check_at_utc"))
    if not force and not resumed and due_at is not None and now < due_at:
        return 0, {"state": "not_due", "next_check_at_utc": previous.get("next_check_at_utc")}
    # Submission受付終了 does not end read-only tracking of existing results.
    # Owner/completion audit stops recurring work after score/history review.
    observation_stage = "history_query"
    try:
        history = _safe_kaggle_history()
        observation_stage = "build_submission_record"
        record = _build_record(history, _now(), previous)
        record["kaggle_cli_discovery"] = dict(LAST_CLI_DISCOVERY)
        observation_stage = "record_official_observation"
        _record_official_observation(history, record)
    except Exception as error:
        error_details = _observation_error_details(error, observation_stage)
        retry_at = _now() + timedelta(minutes=15)
        record = {
            **previous,
            "track": "ARC2",
            "phase": previous.get("phase", "P1_OFFICIAL_SCORE_REQUERY"),
            "score_state": previous.get("score_state", "OBSERVATION_ERROR"),
            "observed_at_utc": _now().isoformat(),
            "next_check_at_utc": retry_at.isoformat(),
            "official_history_next_due_utc": retry_at.isoformat(),
            "blockers": ["kaggle_observation_error", observation_stage, type(error).__name__],
            "next_action": {
                "history_query": "履歴取得段階と安全なOS診断情報を確認し、同一IDの公式履歴照会を再試行する。",
                "build_submission_record": "公式履歴と提出・実行記録の対応、必要なローカルファイルを確認し、同一IDの観測記録を再構成する。",
                "record_official_observation": "観測証拠・台帳の保存先と書込状態を確認し、同一IDの読み取り専用照会結果を再記録する。",
            }[observation_stage],
            "checkpoint_created_at_utc": _now().isoformat(),
            "monitor_boot_time_utc": boot_time,
            "observation_error_details": error_details,
        }
        _append_jsonl(WORK_LEDGER, {
            "event": "ARC2 official Kaggle history observation failed",
            "track": "ARC2",
            "observed_at_utc": record["observed_at_utc"],
            **error_details,
            "next_due_utc": record["next_check_at_utc"],
            "submission_or_rerun_performed": False,
        })
        _append_checkpoint(record)
        return 1, {"state": "observation_error", **error_details, "next_check_at_utc": record["next_check_at_utc"]}
    _append_checkpoint(record)
    return 0, {
        "state": "observed",
        "submission_id": record["last_submission_ref"],
        "status": record["last_status"],
        "score_state": record["score_state"],
        "official_score": record["official_score"],
        "observed_at_utc": record["observed_at_utc"],
        "next_check_at_utc": record["next_check_at_utc"],
        "score_evidence_path": record.get("score_evidence_path"),
        "history_unchanged": record.get("history_unchanged"),
        "kaggle_cli_source": (record.get("kaggle_cli_discovery") or {}).get("selected_source"),
    }


def _self_test() -> dict:
    assert _status_state("COMPLETE", "0.00") == "NUMERIC"
    assert _status_state("COMPLETE", "") == "SCORE_UNOBSERVED"
    assert _status_state("COMPLETE", None) == "SCORE_UNOBSERVED"
    assert _status_state("PENDING", "") == "PENDING"
    assert _status_state("FAILED", "") == "FAILED"
    assert [_next_interval_minutes("PENDING", n) for n in range(1, 6)] == [5, 15, 30, 60, 60]
    assert _next_interval_minutes("NUMERIC", 0) == 60
    return {"state_transitions": "PASS", "pending_intervals_minutes": [5, 15, 30, 60], "zero_is_numeric": True, "no_network": True}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tick", action="store_true", help="due時刻または再開時に公式履歴を照会")
    parser.add_argument("--force", action="store_true", help="再開試験などで直ちに読み取り専用照会")
    parser.add_argument("--self-test", action="store_true", help="ネットワークなしの状態遷移試験")
    args = parser.parse_args(argv)
    if args.self_test:
        result = _self_test()
        code = 0
    else:
        if not args.tick and not args.force:
            parser.error("--tick or --force is required")
        code, result = tick(force=args.force)
    if sys.stdout is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
