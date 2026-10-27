"""Verify Kaggle kernel v6 output against the local candidate run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
KERNEL = "tecchannn/arc2-codex-main-baseline-v1"
COMPETITION = "arc-prize-2026-arc-agi-2"
VERSION = 6
EXPECTED_CHALLENGE_SHA = "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83"
EXPECTED_KERNEL_STATUS_OBSERVED_AT = "2026-10-24T01:58:22+00:00"
EXPECTED_HISTORY_OBSERVED_AT = "2026-10-24T01:58:26+00:00"
LATEST_COMPETITION_SUBMISSION_REF = 57576155

LOCAL_DIR = ROOT / "出力/Kaggle/arc2-global-translation-20261024/full-local-validation"
REMOTE_DIR = ROOT / "出力/Kaggle/arc2-global-translation-20261024/kaggle-v6-output"
UPLOAD_DIR = ROOT / "出力/Kaggle/arc2-global-translation-20261024/upload-v6"
RUN_RECORD = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v6/実行記録.json"
LOCAL_SUBMISSION = LOCAL_DIR / "submission.json"
REMOTE_SUBMISSION = REMOTE_DIR / "submission.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    record = read_json(RUN_RECORD)
    metadata = read_json(UPLOAD_DIR / "kernel-metadata.json")
    local_audit = read_json(LOCAL_DIR / "submission_audit.json")
    remote_audit = read_json(REMOTE_DIR / "submission_audit.json")
    notebook = UPLOAD_DIR / "main.ipynb"

    if record["kernel"] != KERNEL or record["version"] != VERSION:
        raise AssertionError("Kaggle execution record does not identify v6")
    if record["code_sha256"] != sha256(notebook):
        raise AssertionError("Kaggle execution code SHA differs from uploaded notebook")
    if metadata["id"] != KERNEL or metadata["competition_sources"] != [COMPETITION]:
        raise AssertionError("Kaggle metadata targets the wrong kernel or competition")
    if sha256(LOCAL_SUBMISSION) != sha256(REMOTE_SUBMISSION):
        raise AssertionError("Kaggle output differs from local full-challenge output")
    if remote_audit["submission_sha256"] != sha256(REMOTE_SUBMISSION):
        raise AssertionError("Kaggle audit SHA differs from retrieved submission")
    for audit in (local_audit, remote_audit):
        if audit["challenge_sha256"] != EXPECTED_CHALLENGE_SHA:
            raise AssertionError("run used an unexpected challenge input")
        if (audit["tasks"], audit["test_examples"], audit["fallback_count"]) != (
            240,
            259,
            254,
        ):
            raise AssertionError("run dimensions or fallback count changed")
    if local_audit["source_commit"] != remote_audit["source_commit"]:
        raise AssertionError("local and Kaggle source commit markers differ")

    submission_sha = sha256(REMOTE_SUBMISSION)
    result = {
        "schema": "arc2-p5-global-translation-kaggle-v6-check.v1",
        "instruction_id": "ARC2-SCORE-GATE-20261024",
        "kernel": KERNEL,
        "kernel_version": VERSION,
        "kernel_status": "COMPLETE",
        "kernel_status_observed_at_utc": EXPECTED_KERNEL_STATUS_OBSERVED_AT,
        "notebook_sha256": record["code_sha256"],
        "metadata_sha256": record["metadata_sha256"],
        "challenge_sha256": remote_audit["challenge_sha256"],
        "local_submission_sha256": sha256(LOCAL_SUBMISSION),
        "kaggle_submission_sha256": submission_sha,
        "local_and_kaggle_output_byte_equal": True,
        "tasks": remote_audit["tasks"],
        "test_inputs": remote_audit["test_examples"],
        "fallback_count": remote_audit["fallback_count"],
        "candidate_outputs": remote_audit["test_examples"] - remote_audit["fallback_count"],
        "kaggle_runtime_seconds": remote_audit["seconds"],
        "source_commit": remote_audit["source_commit"],
        "latest_competition_history_observed_at_utc": EXPECTED_HISTORY_OBSERVED_AT,
        "latest_competition_submission_ref": LATEST_COMPETITION_SUBMISSION_REF,
        "latest_competition_status": "COMPLETE",
        "latest_competition_public_score": "0.00",
        "candidate_competition_submission_created": False,
        "evaluation_solutions_read": False,
        "candidate_correctness": "unknown; public challenge solutions were not read",
        "next_action": "Continue P5 analysis; recheck rules, history, and quota before a later UTC-day competition submission.",
    }
    (EVIDENCE / "P5_global_translation_kaggle_v6_check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
