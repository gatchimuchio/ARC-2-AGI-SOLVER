"""Probe repeated application of the learned local cell rule."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")
VARIANTS = ("step1", "step2", "step3", "stable")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shape(grid):
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return None
    width = len(grid[0])
    if any(not isinstance(row, list) or len(row) != width for row in grid):
        return None
    return len(grid), width


def _context(grid, row, column):
    height, width = len(grid), len(grid[0])
    return tuple(
        grid[r][c] if 0 <= r < height and 0 <= c < width else -1
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        for r, c in ((row + dr, column + dc),)
    )


def _predictions(teachers, query):
    shape = _shape(query)
    if shape is None:
        return {name: None for name in VARIANTS}
    compatible = [pair for pair in teachers if _shape(pair.get("input")) == shape and _shape(pair.get("output")) == shape]
    if not compatible:
        return {name: None for name in VARIANTS}
    counts = defaultdict(Counter)
    for pair in compatible:
        for row in range(shape[0]):
            for column in range(shape[1]):
                counts[_context(pair["input"], row, column)][pair["output"][row][column]] += 1
    mapping = {key: next(iter(values)) for key, values in counts.items() if len(values) == 1}
    state = [row[:] for row in query]
    result = {name: None for name in VARIANTS}
    for step in range(1, max(shape[0] * shape[1], 3) + 1):
        updated = [row[:] for row in state]
        for row in range(shape[0]):
            for column in range(shape[1]):
                color = mapping.get(_context(state, row, column))
                if color is not None:
                    updated[row][column] = color
        if updated == state:
            break
        state = updated
        if step <= 3:
            result[f"step{step}"] = [row[:] for row in state]
        result["stable"] = [row[:] for row in state]
    return result


def _exact(row, target):
    return any(row.get(key) == target for key in ("attempt_1", "attempt_2"))


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    # Candidate generation sees train pairs and challenge inputs only.
    loo_records = []
    files = sorted(SOURCE_ROOT.glob("*.json"))
    for path in files:
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            if teachers:
                loo_records.append({"task_id": path.stem, "fold": held_index,
                                    "predictions": _predictions(teachers, held["input"])})
    challenge_records = []
    for task_id, task in challenge.items():
        for index, pair in enumerate(task.get("test", [])):
            challenge_records.append({"task_id": task_id, "index": index,
                                      "predictions": _predictions(task.get("train", []), pair["input"])})

    # Load outputs only for offline scoring after all LOO/challenge predictions are frozen.
    labels = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in files}
    loo = {}
    for variant in VARIANTS:
        stats = {"fits": 0, "exact": 0, "direct_exact": 0}
        for record in loo_records:
            candidate = record["predictions"][variant]
            target = labels[record["task_id"]]["train"][record["fold"]]["output"]
            stats["fits"] += candidate is not None
            stats["exact"] += candidate == target
            stats["direct_exact"] += record["predictions"]["step1"] == target
        loo[variant] = stats

    challenge_stats = {}
    for variant in VARIANTS:
        stats = {"fits": 0, "replaced_direct": 0, "filled_open_attempt2": 0,
                 "newly_correct_examples": 0, "regressed_examples": 0,
                 "baseline_exact_examples": 0, "combined_exact_examples": 0}
        task_rows = defaultdict(lambda: {"before": [], "after": []})
        for record in challenge_records:
            row = baseline[record["task_id"]][record["index"]]
            target = labels[record["task_id"]]["test"][record["index"]]["output"]
            candidate = record["predictions"][variant]
            updated = dict(row)
            before = _exact(row, target)
            direct = record["predictions"]["step1"]
            if candidate is not None:
                stats["fits"] += 1
                if direct is not None and row.get("attempt_2") == direct and candidate != direct:
                    updated["attempt_2"] = candidate
                    stats["replaced_direct"] += 1
                elif row.get("attempt_1") == row.get("attempt_2") and candidate not in (row.get("attempt_1"), row.get("attempt_2")):
                    updated["attempt_2"] = candidate
                    stats["filled_open_attempt2"] += 1
            after = _exact(updated, target)
            stats["baseline_exact_examples"] += before
            stats["combined_exact_examples"] += after
            stats["newly_correct_examples"] += after and not before
            stats["regressed_examples"] += before and not after
            task_rows[record["task_id"]]["before"].append(before)
            task_rows[record["task_id"]]["after"].append(after)
        stats["baseline_exact_tasks"] = sum(all(row["before"]) for row in task_rows.values())
        stats["combined_exact_tasks"] = sum(all(row["after"]) for row in task_rows.values())
        stats["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_rows.values())
        stats["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_rows.values())
        challenge_stats[variant] = stats

    report = {
        "schema": "arc2-local-context-iterative-v19-probe-v1",
        "rule": "same-shape teacher pairs; unique full 3x3 context map; simultaneous cell update; stop at fixed point",
        "max_steps": "grid area",
        "loo_folds": len(loo_records),
        "loo": loo,
        "challenge_tasks": len(challenge),
        "challenge_examples": len(challenge_records),
        "challenge_against_v19": challenge_stats,
        "runtime_received_heldout_outputs": False,
        "heldout_outputs_read_only_after_candidate_generation": True,
        "runtime_received_challenge_targets": False,
        "challenge_targets_read_only_after_candidate_generation": True,
        "per_task_predictions_or_targets_saved": False,
        "source_sha256": {"runner": _sha(Path(__file__)), "challenge": _sha(CHALLENGE), "baseline_v19": _sha(BASELINE)},
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"loo": loo, "challenge_against_v19": challenge_stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
