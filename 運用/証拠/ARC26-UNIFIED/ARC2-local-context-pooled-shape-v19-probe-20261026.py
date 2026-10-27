"""Evaluate whether local context rules transfer across teacher grid sizes."""
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shape(grid: object) -> tuple[int, int] | None:
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return None
    width = len(grid[0])
    if any(not isinstance(row, list) or len(row) != width for row in grid):
        return None
    if any(type(value) is not int or not 0 <= value <= 9 for row in grid for value in row):
        return None
    return len(grid), width


def _context(grid: list[list[int]], row: int, column: int) -> tuple[int, ...]:
    height, width = len(grid), len(grid[0])
    return tuple(
        grid[r][c] if 0 <= r < height and 0 <= c < width else -1
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        for r, c in ((row + dr, column + dc),)
    )


def _candidate(teachers, query, *, same_shape: bool, minimum_support: int):
    query_shape = _shape(query)
    if query_shape is None:
        return None
    compatible = []
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if _shape(source) is None or _shape(target) != _shape(source):
            continue
        if same_shape and _shape(source) != query_shape:
            continue
        compatible.append((source, target))
    if not compatible:
        return None
    counts = defaultdict(Counter)
    for source, target in compatible:
        for row in range(len(source)):
            for column in range(len(source[0])):
                counts[_context(source, row, column)][target[row][column]] += 1
    mapping = {
        context: next(iter(outputs))
        for context, outputs in counts.items()
        if len(outputs) == 1 and sum(outputs.values()) >= minimum_support
    }
    prediction = [row[:] for row in query]
    changes = 0
    for row in range(query_shape[0]):
        for column in range(query_shape[1]):
            color = mapping.get(_context(query, row, column))
            if color is not None and color != query[row][column]:
                prediction[row][column] = color
                changes += 1
    return prediction if changes else None


def _exact(row, target):
    return any(row.get(name) == target for name in ("attempt_1", "attempt_2"))


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    files = sorted(SOURCE_ROOT.glob("*.json"))

    # Freeze every candidate before reading held-out outputs.
    loo_records = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        training = data.get("train", [])
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            if not teachers:
                continue
            loo_records.append({
                "task_id": path.stem,
                "fold": held_index,
                "same_support1": _candidate(teachers, held["input"], same_shape=True, minimum_support=1),
                "pooled_support1": _candidate(teachers, held["input"], same_shape=False, minimum_support=1),
                "pooled_support2": _candidate(teachers, held["input"], same_shape=False, minimum_support=2),
            })
    challenge_records = []
    for task_id, task in challenge.items():
        for index, pair in enumerate(task.get("test", [])):
            teachers = task.get("train", [])
            challenge_records.append({
                "task_id": task_id,
                "index": index,
                "same_support1": _candidate(teachers, pair["input"], same_shape=True, minimum_support=1),
                "pooled_support1": _candidate(teachers, pair["input"], same_shape=False, minimum_support=1),
                "pooled_support2": _candidate(teachers, pair["input"], same_shape=False, minimum_support=2),
            })

    # Only the offline scorer reads held-out outputs, after every prediction is frozen.
    loo_targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("train", [])]
        for path in files
    }
    challenge_targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in files
    }
    loo_stats = {}
    for name in ("same_support1", "pooled_support1", "pooled_support2"):
        result = {"eligible_folds": 0, "candidate_fits": 0, "candidate_exact_folds": 0,
                  "support1_exact_folds": 0}
        result["eligible_folds"] = len(loo_records)
        for record in loo_records:
            candidate = record[name]
            target = loo_targets[record["task_id"]][record["fold"]]
            if candidate is not None:
                result["candidate_fits"] += 1
                result["candidate_exact_folds"] += candidate == target
            if record["same_support1"] == target:
                result["support1_exact_folds"] += 1
        loo_stats[name] = result

    challenge_stats = {}
    for name in ("same_support1", "pooled_support1", "pooled_support2"):
        result = {"candidate_fits": 0, "distinct_from_both_attempts": 0,
                  "selected_into_open_attempt2": 0, "newly_correct_examples": 0,
                  "regressed_examples": 0, "baseline_exact_examples": 0,
                  "combined_exact_examples": 0}
        task_rows = defaultdict(lambda: {"before": [], "after": []})
        for record in challenge_records:
            row = baseline[record["task_id"]][record["index"]]
            target = challenge_targets[record["task_id"]][record["index"]]
            candidate = record[name]
            before = _exact(row, target)
            updated = dict(row)
            if candidate is not None:
                result["candidate_fits"] += 1
                distinct = candidate not in (row.get("attempt_1"), row.get("attempt_2"))
                result["distinct_from_both_attempts"] += distinct
                if row.get("attempt_1") == row.get("attempt_2") and distinct:
                    updated["attempt_2"] = candidate
                    result["selected_into_open_attempt2"] += 1
            after = _exact(updated, target)
            result["baseline_exact_examples"] += before
            result["combined_exact_examples"] += after
            result["newly_correct_examples"] += after and not before
            result["regressed_examples"] += before and not after
            task_rows[record["task_id"]]["before"].append(before)
            task_rows[record["task_id"]]["after"].append(after)
        result["baseline_exact_tasks"] = sum(all(row["before"]) for row in task_rows.values())
        result["combined_exact_tasks"] = sum(all(row["after"]) for row in task_rows.values())
        result["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_rows.values())
        result["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_rows.values())
        challenge_stats[name] = result

    report = {
        "schema": "arc2-local-context-pooled-shape-v19-probe-v1",
        "variants": {
            "same_support1": "same-shape input/output teacher examples; unique 3x3 context; support >= 1",
            "pooled_support1": "any input/output size with same dimensions as each other; unique 3x3 context; support >= 1",
            "pooled_support2": "any input/output size with same dimensions as each other; unique 3x3 context; support >= 2",
        },
        "loo_folds": len(loo_records),
        "loo": loo_stats,
        "challenge_tasks": len(challenge),
        "challenge_examples": len(challenge_records),
        "challenge_against_v19": challenge_stats,
        "runtime_received_heldout_outputs": False,
        "heldout_outputs_read_only_after_candidate_generation": True,
        "runtime_received_challenge_targets": False,
        "challenge_targets_read_only_after_candidate_generation": True,
        "per_task_predictions_or_targets_saved": False,
        "data_use": "public ARC-AGI-2 outputs used only for offline aggregate scoring",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_v19": _sha(BASELINE),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"loo": loo_stats, "challenge_against_v19": challenge_stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
