"""Verify the local full-challenge bundle output against the v5 baseline."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
BASELINE_DIR = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v5/retrieved"
CANDIDATE_DIR = ROOT / "出力/Kaggle/arc2-global-translation-20261024"
RUN_DIR = CANDIDATE_DIR / "full-local-validation"
CHALLENGE_PATH = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def grid_is_valid(grid: object) -> bool:
    return (
        isinstance(grid, list)
        and 1 <= len(grid) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(grid[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in grid
        )
    )


def verify_submission(challenges: dict, submission: dict) -> int:
    if set(submission) != set(challenges):
        raise AssertionError("submission task set differs from official challenge")
    tests = 0
    for task_id, task in challenges.items():
        attempts = submission[task_id]
        if not isinstance(attempts, list) or len(attempts) != len(task["test"]):
            raise AssertionError("submission test count differs from official challenge")
        for pair in attempts:
            if not isinstance(pair, dict) or set(pair) != {"attempt_1", "attempt_2"}:
                raise AssertionError("submission attempt structure is invalid")
            if not all(grid_is_valid(pair[key]) for key in pair):
                raise AssertionError("submission contains an invalid grid")
            tests += 1
    return tests


def fallback_summary(audit: dict, submission_path: Path) -> tuple[int, dict[str, int]]:
    if audit["submission_sha256"] != sha256(submission_path):
        raise AssertionError("audit submission SHA does not match output file")
    fallbacks = audit["fallbacks"]
    if len(fallbacks) != audit["fallback_count"]:
        raise AssertionError("audit fallback count differs from rows")
    return len(fallbacks), dict(
        sorted(Counter(row.get("reason", "unknown") for row in fallbacks).items())
    )


def main() -> None:
    challenge = read_json(CHALLENGE_PATH)
    baseline_path = BASELINE_DIR / "submission.json"
    candidate_path = RUN_DIR / "submission.json"
    baseline_audit = read_json(BASELINE_DIR / "submission_audit.json")
    candidate_audit = read_json(RUN_DIR / "submission_audit.json")
    baseline = read_json(baseline_path)
    candidate = read_json(candidate_path)

    tests = verify_submission(challenge, baseline)
    if verify_submission(challenge, candidate) != tests:
        raise AssertionError("baseline/candidate test counts differ")
    changed_rows = sum(
        old != new
        for task_id in challenge
        for old, new in zip(baseline[task_id], candidate[task_id], strict=True)
    )
    baseline_fallbacks, baseline_reasons = fallback_summary(
        baseline_audit, baseline_path
    )
    candidate_fallbacks, candidate_reasons = fallback_summary(
        candidate_audit, candidate_path
    )
    challenge_sha = sha256(CHALLENGE_PATH)
    if baseline_audit["challenge_sha256"] != challenge_sha:
        raise AssertionError("baseline was generated from another challenge input")
    if candidate_audit["challenge_sha256"] != challenge_sha:
        raise AssertionError("candidate was generated from another challenge input")
    for audit in (baseline_audit, candidate_audit):
        if audit["tasks"] != len(challenge) or audit["test_examples"] != tests:
            raise AssertionError("audit dimensions differ from official challenge")

    manifest = read_json(CANDIDATE_DIR / "build-manifest.json")
    translation_path = ROOT / "接続/ARC2/全前景平行移動教材.py"
    translation_sha = sha256(translation_path)
    bundle_row = next(
        (row for row in manifest["files"] if row["path"] == "接続/ARC2/全前景平行移動教材.py"),
        None,
    )
    if bundle_row is None or bundle_row["sha256"] != translation_sha:
        raise AssertionError("candidate module is missing or differs in the bundle")
    result = {
        "schema": "arc2-p5-global-translation-full-challenge-check.v1",
        "instruction_id": "ARC2-SCORE-GATE-20261024",
        "data_source": "official public arc-agi_test_challenges.json only",
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "tasks": len(challenge),
        "test_inputs": tests,
        "challenge_sha256": challenge_sha,
        "baseline_source_commit": baseline_audit["source_commit"],
        "baseline_submission_sha256": sha256(baseline_path),
        "baseline_fallback_count": baseline_fallbacks,
        "baseline_fallback_reasons": baseline_reasons,
        "candidate_source_commit": candidate_audit["source_commit"],
        "candidate_translation_source_sha256": translation_sha,
        "candidate_hds_source_sha256": sha256(ROOT / "接続/ARC2/HDS接続.py"),
        "candidate_bundle_sha256": manifest["payload_sha256"],
        "candidate_submission_sha256": sha256(candidate_path),
        "baseline_audit_sha256": sha256(BASELINE_DIR / "submission_audit.json"),
        "candidate_audit_sha256": sha256(RUN_DIR / "submission_audit.json"),
        "candidate_fallback_count": candidate_fallbacks,
        "candidate_fallback_reasons": candidate_reasons,
        "candidate_answer_count_delta": baseline_fallbacks - candidate_fallbacks,
        "changed_test_output_rows": changed_rows,
        "candidate_runtime_seconds": candidate_audit["seconds"],
        "official_correctness": "unknown; no solution file was read",
        "official_submission_created": False,
    }
    (EVIDENCE / "P5_global_translation_full_challenge_check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
