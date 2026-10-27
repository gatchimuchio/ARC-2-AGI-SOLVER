"""Probe alternative local neighborhoods over the completed v19 challenge run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections import Counter, defaultdict


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v19-local-context-second-20261026/full-runtime/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")
VARIANTS = {
    "ring8": tuple((dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)),
    "orthogonal4": ((-1, 0), (1, 0), (0, -1), (0, 1)),
    "diagonal4": ((-1, -1), (-1, 1), (1, -1), (1, 1)),
    "cross_radius2": ((-2, 0), (-1, 0), (1, 0), (2, 0), (0, -2), (0, -1), (0, 1), (0, 2)),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _context(grid, row, column, offsets):
    height, width = len(grid), len(grid[0])
    return tuple(
        grid[row + dr][column + dc]
        if 0 <= row + dr < height and 0 <= column + dc < width
        else -1
        for dr, dc in offsets
    )


def _candidate(teachers, query, offsets):
    if not query or not query[0] or any(len(row) != len(query[0]) for row in query):
        return None
    shape = (len(query), len(query[0]))
    compatible = [
        (pair["input"], pair["output"])
        for pair in teachers
        if len(pair.get("input", [])) == shape[0]
        and len(pair.get("output", [])) == shape[0]
        and all(len(row) == shape[1] for row in pair["input"])
        and all(len(row) == shape[1] for row in pair["output"])
    ]
    if not compatible:
        return None
    output_counts = defaultdict(Counter)
    for source, target in compatible:
        for row in range(shape[0]):
            for column in range(shape[1]):
                output_counts[_context(source, row, column, offsets)][target[row][column]] += 1
    mapping = {
        pattern: next(iter(counts))
        for pattern, counts in output_counts.items()
        if len(counts) == 1
    }
    prediction = [row[:] for row in query]
    changed = 0
    for row in range(shape[0]):
        for column in range(shape[1]):
            color = mapping.get(_context(query, row, column, offsets))
            if color is not None and color != query[row][column]:
                prediction[row][column] = color
                changed += 1
    return prediction if changed else None


def _exact(row, target):
    return any(row.get(key) == target for key in ("attempt_1", "attempt_2"))


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    predictions = []
    for task_id, task in challenge.items():
        for index, pair in enumerate(task["test"]):
            predictions.append({
                "task_id": task_id,
                "index": index,
                "baseline": baseline[task_id][index],
                "candidates": {
                    name: _candidate(task["train"], pair["input"], offsets)
                    for name, offsets in VARIANTS.items()
                },
            })

    labels = {
        path.stem: [pair["output"] for pair in json.loads(path.read_text(encoding="utf-8")).get("test", [])]
        for path in SOURCE_ROOT.glob("*.json")
    }
    summary = {}
    for name in VARIANTS:
        stats = {"fits": 0, "distinct_candidates": 0, "selected_into_open_attempt2": 0,
                 "baseline_exact": 0, "combined_exact": 0, "newly_correct": 0,
                 "regressions": 0}
        task_rows = defaultdict(lambda: {"before": [], "after": []})
        for record in predictions:
            baseline_row = record["baseline"]
            candidate = record["candidates"][name]
            target = labels[record["task_id"]][record["index"]]
            before = _exact(baseline_row, target)
            current = dict(baseline_row)
            stats["fits"] += candidate is not None
            distinct = candidate is not None and candidate not in (current.get("attempt_1"), current.get("attempt_2"))
            stats["distinct_candidates"] += distinct
            if candidate is not None and current.get("attempt_2") == current.get("attempt_1") and candidate != current.get("attempt_1"):
                current["attempt_2"] = candidate
                stats["selected_into_open_attempt2"] += 1
            after = _exact(current, target)
            stats["baseline_exact"] += before
            stats["combined_exact"] += after
            stats["newly_correct"] += after and not before
            stats["regressions"] += before and not after
            task_rows[record["task_id"]]["before"].append(before)
            task_rows[record["task_id"]]["after"].append(after)
        stats["baseline_exact_tasks"] = sum(all(row["before"]) for row in task_rows.values())
        stats["combined_exact_tasks"] = sum(all(row["after"]) for row in task_rows.values())
        stats["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_rows.values())
        stats["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_rows.values())
        summary[name] = stats

    report = {
        "schema": "arc2-neighbor-context-variants-v19-probe-v1",
        "baseline": "completed v19 full runtime",
        "tasks": len(challenge),
        "examples": len(predictions),
        "variants": {name: [list(offset) for offset in offsets] for name, offsets in VARIANTS.items()},
        "results": summary,
        "runtime_received_challenge_targets": False,
        "targets_read_only_after_all_candidate_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "data_use": "public ARC-AGI-2 training outputs for offline scoring only",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_submission": _sha(BASELINE),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
