"""Check whether pooled-shape context rules beat the current second answer."""
from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")


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


def _pooled(teachers, query, minimum_support):
    shape = _shape(query)
    if shape is None:
        return None
    teachers = [
        pair for pair in teachers
        if _shape(pair.get("input")) is not None
        and _shape(pair.get("output")) == _shape(pair.get("input"))
    ]
    if not teachers:
        return None
    counts = defaultdict(Counter)
    for pair in teachers:
        source, target = pair["input"], pair["output"]
        for row in range(len(source)):
            for column in range(len(source[0])):
                counts[_context(source, row, column)][target[row][column]] += 1
    mapping = {
        key: next(iter(values)) for key, values in counts.items()
        if len(values) == 1 and sum(values.values()) >= minimum_support
    }
    prediction = [row[:] for row in query]
    changed = False
    for row in range(shape[0]):
        for column in range(shape[1]):
            color = mapping.get(_context(query, row, column))
            if color is not None and color != query[row][column]:
                prediction[row][column] = color
                changed = True
    return prediction if changed else None


def _exact(row, target):
    return any(row.get(key) == target for key in ("attempt_1", "attempt_2"))


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2.局所近傍変換候補 import LocalCellContextCandidate

    records = []
    for task_id, task in challenge.items():
        same_shape = LocalCellContextCandidate(task.get("train", []))
        for index, pair in enumerate(task.get("test", [])):
            direct, _ = same_shape.候補(pair["input"], {})
            records.append({
                "task_id": task_id,
                "index": index,
                "direct": direct,
                "pooled_support1": _pooled(task.get("train", []), pair["input"], 1),
                "pooled_support2": _pooled(task.get("train", []), pair["input"], 2),
            })

    # Public targets are opened only after every candidate has been generated.
    targets = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    results = {}
    for variant in ("same_shape_direct", "pooled_support1", "pooled_support2"):
        stats = Counter()
        task_rows = defaultdict(lambda: {"before": [], "after": []})
        for record in records:
            row = baseline[record["task_id"]][record["index"]]
            target = targets[record["task_id"]][record["index"]]
            direct = record["direct"]
            candidate = direct if variant == "same_shape_direct" else record[variant]
            updated = dict(row)
            before = _exact(row, target)
            if candidate is not None:
                stats["candidate_fits"] += 1
                distinct = candidate not in (row.get("attempt_1"), row.get("attempt_2"))
                stats["distinct_candidates"] += distinct
                if direct is not None and row.get("attempt_2") == direct and candidate != direct and distinct:
                    updated["attempt_2"] = candidate
                    stats["replaced_direct"] += 1
                elif row.get("attempt_1") == row.get("attempt_2") and distinct:
                    updated["attempt_2"] = candidate
                    stats["filled_open"] += 1
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
        results[variant] = dict(stats)

    report = {
        "schema": "arc2-local-context-pool-swap-v19-probe-v1",
        "challenge_tasks": len(challenge),
        "challenge_examples": len(records),
        "candidate_priority": "pooled candidates replace the selected same-shape local candidate only when it occupies attempt_2; otherwise only an identical duplicate slot is filled",
        "results_against_v19": results,
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_candidate_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "source_sha256": {"runner": _sha(Path(__file__)), "challenge": _sha(CHALLENGE), "baseline_v19": _sha(BASELINE)},
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
