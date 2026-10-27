"""Screen a train-consistent, shape-preserving global color remap."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _valid_grid(grid):
    return (isinstance(grid, list) and 1 <= len(grid) <= 30
            and all(isinstance(row, list) and 1 <= len(row) <= 30
                    and len(row) == len(grid[0])
                    and all(type(c) is int and 0 <= c <= 9 for c in row)
                    for row in grid))


def _candidate(_module, teachers, query):
    if len(teachers) < 1 or not _valid_grid(query):
        return None
    mapping = {}
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if not _valid_grid(source) or not _valid_grid(target):
            return None
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return None
        for source_row, target_row in zip(source, target, strict=True):
            for source_color, target_color in zip(source_row, target_row, strict=True):
                previous = mapping.get(source_color)
                if previous is not None and previous != target_color:
                    return None
                mapping[source_color] = target_color
    query_colors = {color for row in query for color in row}
    if not mapping or not query_colors <= mapping.keys():
        return None
    result = [[mapping[color] for color in row] for row in query]
    if result == query or not _valid_grid(result):
        return None
    return result


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    eligible = proposals = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 2:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            eligible += 1
            proposals += _candidate(None, teachers, held["input"]) is not None
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    challenge_proposals = challenge_tasks_with_candidate = 0
    for task in challenge.values():
        task_has_candidate = False
        for pair in task.get("test", []):
            has_candidate = _candidate(None, task.get("train", []), pair["input"]) is not None
            task_has_candidate |= has_candidate
            challenge_proposals += has_candidate
        challenge_tasks_with_candidate += task_has_candidate
    report = {
        "schema": "arc2-global-color-remap-v48-probe-v1",
        "candidate_rule": "one conflict-free cellwise color map fits every teacher; at least one teacher; query colors all observed; output differs from query",
        "loo_eligible_folds": eligible,
        "loo_candidate_proposal_folds": proposals,
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_tasks_with_candidate": challenge_tasks_with_candidate,
        "challenge_examples_with_candidate": challenge_proposals,
        "heldout_outputs_read": False,
        "challenge_targets_read": False,
        "per_task_ids_grids_or_candidates_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge_inputs": _sha(CHALLENGE),
            "v28_build_manifest": _sha(ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026/build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
