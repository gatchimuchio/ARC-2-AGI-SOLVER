"""Score the already-created v11 output against accessible ARC2 training labels.

The prediction artifact is loaded and SHA-checked before any target labels are
read. Targets are used only for this offline aggregate audit; no per-task output,
grid, or target is written.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
LABELS = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
SUBMISSION = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v11-20261025T2341Z/submission.json"
AUDIT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v11-20261025T2341Z/submission_audit.json"
HISTORY = ROOT / "運用/証拠/ARC26-UNIFIED/official-history-20261026T133200Z.json"
V51_REPORT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v51-largest-component-full-runtime-evaluation-20261026.json"
OUTPUT = Path(__file__).with_suffix(".json")
EXPECTED_CHALLENGE_SHA256 = "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83"
EXPECTED_SUBMISSION_SHA256 = "08d0dc111f97c9f3a909955296fc58d46ea0c4514fe66e75169526723359f017"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    challenge_bytes = CHALLENGE.read_bytes()
    submission_bytes = SUBMISSION.read_bytes()
    challenge_sha = hashlib.sha256(challenge_bytes).hexdigest()
    submission_sha = hashlib.sha256(submission_bytes).hexdigest()
    if challenge_sha != EXPECTED_CHALLENGE_SHA256:
        raise ValueError("challenge input hash changed")
    if submission_sha != EXPECTED_SUBMISSION_SHA256:
        raise ValueError("v11 output hash differs from the official submission")

    # The output already exists and is pinned before target data is opened.
    challenge = json.loads(challenge_bytes)
    submission = json.loads(submission_bytes)
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("submission_sha256") != submission_sha:
        raise ValueError("submission audit does not match v11 output")

    exact_examples = 0
    exact_tasks = 0
    examples = 0
    distinct_pairs = 0
    missing_labels = 0
    invalid_outputs = 0
    for task_id, task in challenge.items():
        label_path = LABELS / f"{task_id}.json"
        if not label_path.is_file():
            missing_labels += 1
            continue
        labels = json.loads(label_path.read_text(encoding="utf-8"))
        rows = submission.get(task_id)
        if (not isinstance(rows, list)
                or len(rows) != len(task["test"])
                or len(labels.get("test", [])) != len(task["test"])):
            invalid_outputs += 1
            continue
        task_correct = True
        for index, _query in enumerate(task["test"]):
            row = rows[index]
            target = labels["test"][index]["output"]
            attempt_1 = row.get("attempt_1")
            attempt_2 = row.get("attempt_2")
            distinct_pairs += attempt_1 != attempt_2
            correct = attempt_1 == target or attempt_2 == target
            exact_examples += correct
            examples += 1
            task_correct = task_correct and correct
        exact_tasks += task_correct

    if missing_labels or invalid_outputs or examples != 259:
        raise ValueError("label coverage or output shape is incomplete")

    previous = json.loads(V51_REPORT.read_text(encoding="utf-8"))
    official = json.loads(HISTORY.read_text(encoding="utf-8"))["latest_submission"]
    report = {
        "schema": "arc2-v11-local-output-score-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "offline reference evaluation; not an official Kaggle score",
        "submission_ref": official["ref"],
        "official_status_at_last_observation": official["status"],
        "official_public_score": None if official["publicScore"] == "" else official["publicScore"],
        "official_private_score": None if official["privateScore"] == "" else official["privateScore"],
        "official_history_observed_at_utc": "2026-10-26T13:32:00.977941Z",
        "challenge_sha256": challenge_sha,
        "submission_sha256": submission_sha,
        "submission_matches_official_ref_file_sha256": True,
        "target_source": "入力/公式ソース/ARC-AGI-2/data/training/<challenge task id>.json",
        "targets_read_after_prediction_artifact_was_fixed": True,
        "targets_passed_to_runtime": False,
        "per_task_ids_grids_or_targets_saved": False,
        "tasks": len(challenge),
        "examples": examples,
        "exact_tasks": exact_tasks,
        "exact_examples": exact_examples,
        "identical_attempt_pairs": examples - distinct_pairs,
        "distinct_attempt_pairs": distinct_pairs,
        "fallback_examples": audit.get("fallback_count"),
        "previous_best_local_v51": {
            "report_sha256": sha(V51_REPORT),
            "exact_tasks": previous["v51_full_challenge_score"]["exact_tasks"],
            "exact_examples": previous["v51_full_challenge_score"]["exact_examples"],
        },
        "delta_v11_minus_v51": {
            "exact_tasks": exact_tasks - previous["v51_full_challenge_score"]["exact_tasks"],
            "exact_examples": exact_examples - previous["v51_full_challenge_score"]["exact_examples"],
        },
        "source_sha256": {
            "auditor": sha(Path(__file__)),
            "submission_audit": sha(AUDIT),
            "official_history": sha(HISTORY),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
