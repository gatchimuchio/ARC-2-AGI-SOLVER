"""Aggregate failure-shape profile for the fixed, already-submitted v11 output.

Predictions are hash-pinned before reading public training labels. Only aggregate
counts are written; task identifiers, grids, and targets remain in memory.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
LABELS = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
SUBMISSION = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v11-20261025T2341Z/submission.json"
AUDIT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC2-v11-20261025T2341Z/submission_audit.json"
OUTPUT = Path(__file__).with_suffix(".json")
EXPECTED_CHALLENGE_SHA256 = "232264c58f825ee77327dcfc9f4e5cb2f83b8d997eb69032be1bf2205bbe1a83"
EXPECTED_SUBMISSION_SHA256 = "08d0dc111f97c9f3a909955296fc58d46ea0c4514fe66e75169526723359f017"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shape(grid: list[list[int]]) -> tuple[int, int]:
    return len(grid), len(grid[0])


def _relation(source: list[list[int]], target: list[list[int]]) -> str:
    source_shape, target_shape = _shape(source), _shape(target)
    if source == target:
        return "identity"
    same_palette = set(cell for row in source for cell in row) == set(
        cell for row in target for cell in row
    )
    if source_shape == target_shape:
        return "same_shape_same_palette_rearrangement" if same_palette else "same_shape_palette_change"
    if source_shape != target_shape and source_shape == target_shape[::-1]:
        return "transposed_shape"
    return "other_shape_change"


def main() -> None:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    challenge_bytes = CHALLENGE.read_bytes()
    submission_bytes = SUBMISSION.read_bytes()
    challenge_sha = hashlib.sha256(challenge_bytes).hexdigest()
    submission_sha = hashlib.sha256(submission_bytes).hexdigest()
    if challenge_sha != EXPECTED_CHALLENGE_SHA256 or submission_sha != EXPECTED_SUBMISSION_SHA256:
        raise ValueError("pinned challenge or v11 output hash changed")

    challenge = json.loads(challenge_bytes)
    submission = json.loads(submission_bytes)
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    if audit.get("submission_sha256") != submission_sha:
        raise ValueError("submission audit does not match v11 output")
    fallback_keys = {
        (row["task_id"], row["test_index"])
        for row in audit.get("fallbacks", [])
        if isinstance(row, dict) and isinstance(row.get("task_id"), str)
    }

    relation_counts: dict[str, Counter] = defaultdict(Counter)
    palette_counts: dict[str, Counter] = defaultdict(Counter)
    groups = Counter()
    exact_tasks = 0
    examples = 0
    for task_id, task in challenge.items():
        labels = json.loads((LABELS / f"{task_id}.json").read_text(encoding="utf-8"))
        rows = submission[task_id]
        task_exact = True
        for index, query_record in enumerate(task["test"]):
            query = query_record["input"]
            target = labels["test"][index]["output"]
            row = rows[index]
            exact = row["attempt_1"] == target or row["attempt_2"] == target
            fallback = (task_id, index) in fallback_keys
            group = "fallback" if fallback else "nonfallback"
            relation = _relation(query, target)
            input_colors = set(cell for line in query for cell in line)
            target_colors = set(cell for line in target for cell in line)
            palette_relation = (
                "same" if input_colors == target_colors
                else "adds_colors" if input_colors < target_colors
                else "removes_colors" if target_colors < input_colors
                else "replaces_colors"
            )
            relation_counts[group][relation] += 1
            relation_counts["all"][relation] += 1
            palette_counts[group][palette_relation] += 1
            palette_counts["all"][palette_relation] += 1
            outcome = "exact" if exact else "wrong"
            relation_counts[f"{group}_{outcome}"][relation] += 1
            palette_counts[f"{group}_{outcome}"][palette_relation] += 1
            groups[group] += 1
            groups[f"{group}_exact"] += exact
            groups[f"{group}_wrong"] += not exact
            examples += 1
            task_exact = task_exact and exact
        exact_tasks += task_exact

    report = {
        "schema": "arc2-v11-error-profile-v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "offline aggregate analysis of an already-fixed submitted output; not an official score",
        "submission_ref": 57646990,
        "challenge_sha256": challenge_sha,
        "submission_sha256": submission_sha,
        "targets_passed_to_runtime": False,
        "per_task_ids_grids_or_targets_saved": False,
        "tasks": len(challenge),
        "examples": examples,
        "v11_exact_tasks": exact_tasks,
        "v11_exact_examples": groups["fallback_exact"] + groups["nonfallback_exact"],
        "fallback_examples": groups["fallback"],
        "fallback_exact_examples": groups["fallback_exact"],
        "fallback_wrong_examples": groups["fallback_wrong"],
        "target_shape_relation_by_group": {
            name: dict(sorted(counts.items())) for name, counts in relation_counts.items()
        },
        "target_palette_relation_by_group": {
            name: dict(sorted(counts.items())) for name, counts in palette_counts.items()
        },
        "v51_comparison_context": {
            "exact_tasks": 14,
            "exact_examples": 15,
            "source_report": "運用/証拠/ARC26-UNIFIED/ARC2-v51-largest-component-full-runtime-evaluation-20261026.json",
        },
        "official_kaggle_score": None,
        "official_score_state": "COMPLETE with blank public/private score in the last observed history",
        "source_sha256": {
            "auditor": _sha(Path(__file__)),
            "submission_audit": _sha(AUDIT),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
