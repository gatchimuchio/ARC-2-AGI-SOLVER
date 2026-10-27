"""Evaluate local cell-context rules as an incremental second answer over v18."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time
from collections import Counter, defaultdict


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")
VARIANTS = ((0, 1), (1, 1), (1, 2), (2, 1))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _worker(adapter, task):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        status = adapter._worker(task)
    lines = [line for line in capture.getvalue().splitlines() if line.strip()]
    if status or not lines:
        return None
    result = json.loads(lines[-1])
    rows = result.get("results") if isinstance(result, dict) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return None
    return {"attempt_1": rows[0].get("answer"), "attempt_2": rows[0].get("second_answer")}


def _context(grid, row, column, radius):
    height, width = len(grid), len(grid[0])
    result = []
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            rr, cc = row + dr, column + dc
            result.append(grid[rr][cc] if 0 <= rr < height and 0 <= cc < width else -1)
    return tuple(result)


def _candidate(teachers, query, radius, minimum_support):
    if not query or not query[0] or any(len(row) != len(query[0]) for row in query):
        return None
    height, width = len(query), len(query[0])
    outputs = defaultdict(Counter)
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if not source or not target or len(source) != height or len(target) != height:
            return None
        if any(len(row) != width for row in source) or any(len(row) != width for row in target):
            return None
        for r in range(height):
            for c in range(width):
                outputs[_context(source, r, c, radius)][target[r][c]] += 1

    mapping = {}
    for pattern, counts in outputs.items():
        if len(counts) == 1:
            color, count = next(iter(counts.items()))
            if count >= minimum_support:
                mapping[pattern] = color

    predicted = [row[:] for row in query]
    changed = 0
    for r in range(height):
        for c in range(width):
            color = mapping.get(_context(query, r, c, radius))
            if color is not None and color != query[r][c]:
                predicted[r][c] = color
                changed += 1
    return predicted if changed else None


def _combine(baseline, candidate):
    if not isinstance(baseline, dict):
        return None
    first, second = baseline.get("attempt_1"), baseline.get("attempt_2")
    # Preserve any already-distinct second answer; use the new candidate when
    # the existing pair has a vacant duplicate slot.
    if candidate is not None and second == first and candidate != first:
        second = candidate
    return {"attempt_1": first, "attempt_2": second}


def _exact(prediction, target):
    return isinstance(prediction, dict) and any(prediction.get(key) == target for key in ("attempt_1", "attempt_2"))


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    started = time.monotonic()
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import Kaggle提出
    from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate
    from 接続.ARC2.単純変換候補 import valid_grid

    records = []
    eligible_folds = worker_errors = 0
    files = sorted(SOURCE_ROOT.glob("*.json"))
    for path in files:
        source = json.loads(path.read_text(encoding="utf-8"))
        training = source.get("train", [])
        for held_index, held in enumerate(training):
            teachers = [pair for i, pair in enumerate(training) if i != held_index]
            if len(teachers) < 2:
                continue
            eligible_folds += 1
            predictions = {
                variant: _candidate(teachers, held["input"], *variant)
                for variant in VARIANTS
            }
            if not any(candidate is not None for candidate in predictions.values()):
                continue
            task = {"train": teachers, "test": [{"input": held["input"]}]}
            baseline = _worker(Kaggle提出, task)
            if baseline is None:
                worker_errors += 1
                continue
            records.append({"path": path, "fold": held_index, "baseline": baseline, "predictions": predictions})

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline_submission = json.loads(BASELINE.read_text(encoding="utf-8"))
    challenge_records = []
    for task_id, task in challenge.items():
        teachers = json.loads((SOURCE_ROOT / f"{task_id}.json").read_text(encoding="utf-8"))["train"]
        geometry = CompositeGeometryCandidate(teachers)
        for index, test in enumerate(task.get("test", [])):
            candidates = {variant: _candidate(teachers, test["input"], *variant) for variant in VARIANTS}
            base_rows = baseline_submission.get(task_id, [])
            baseline = base_rows[index] if index < len(base_rows) else None
            baseline_first = baseline.get("attempt_1") if isinstance(baseline, dict) else test["input"]
            baseline_second = baseline.get("attempt_2") if isinstance(baseline, dict) else test["input"]
            geometry_candidate, _ = geometry.候補(test["input"], {})
            if valid_grid(geometry_candidate) and geometry_candidate != baseline_first:
                baseline_second = geometry_candidate
            challenge_records.append({
                "task_id": task_id,
                "index": index,
                "input": test["input"],
                "baseline": {"attempt_1": baseline_first, "attempt_2": baseline_second},
                "candidates": candidates,
            })

    # Only after all held-out/test predictions are frozen do we read targets.
    loo_stats = {variant: {"fit_folds": 0, "distinct_from_v18_folds": 0, "changed_second_folds": 0,
                           "baseline_exact": 0, "combined_exact": 0, "candidate_exact": 0,
                           "newly_correct": 0, "regressions": 0} for variant in VARIANTS}
    for record in records:
        target = json.loads(record["path"].read_text(encoding="utf-8"))["train"][record["fold"]]["output"]
        baseline_exact = _exact(record["baseline"], target)
        for variant in VARIANTS:
            candidate = record["predictions"][variant]
            combined = _combine(record["baseline"], candidate)
            stats = loo_stats[variant]
            stats["fit_folds"] += candidate is not None
            stats["distinct_from_v18_folds"] += candidate is not None and candidate not in (record["baseline"]["attempt_1"], record["baseline"]["attempt_2"])
            stats["changed_second_folds"] += combined["attempt_2"] != record["baseline"]["attempt_2"]
            stats["baseline_exact"] += baseline_exact
            combined_exact = _exact(combined, target)
            stats["combined_exact"] += combined_exact
            stats["candidate_exact"] += candidate == target
            stats["newly_correct"] += combined_exact and not baseline_exact
            stats["regressions"] += baseline_exact and not combined_exact

    challenge_stats = {variant: {"fit_examples": 0, "distinct_from_v16_folds": 0, "changed_second_examples": 0,
                                 "baseline_exact": 0, "combined_exact": 0, "candidate_exact": 0,
                                 "newly_correct": 0, "regressions": 0,
                                 "large_fit_examples": 0, "large_distinct_examples": 0} for variant in VARIANTS}
    for record in challenge_records:
        task_id, index = record["task_id"], record["index"]
        target = json.loads((SOURCE_ROOT / f"{task_id}.json").read_text(encoding="utf-8"))["test"][index]["output"]
        baseline_exact = _exact(record["baseline"], target)
        large = len(record["input"]) * len(record["input"][0]) > 100
        for variant in VARIANTS:
            candidate = record["candidates"][variant]
            combined = _combine(record["baseline"], candidate)
            stats = challenge_stats[variant]
            distinct = candidate is not None and candidate not in (record["baseline"]["attempt_1"], record["baseline"]["attempt_2"])
            stats["fit_examples"] += candidate is not None
            stats["distinct_from_v16_folds"] += distinct
            stats["changed_second_examples"] += combined["attempt_2"] != record["baseline"]["attempt_2"]
            stats["baseline_exact"] += baseline_exact
            combined_exact = _exact(combined, target)
            stats["combined_exact"] += combined_exact
            stats["candidate_exact"] += candidate == target
            stats["newly_correct"] += combined_exact and not baseline_exact
            stats["regressions"] += baseline_exact and not combined_exact
            stats["large_fit_examples"] += candidate is not None and large
            stats["large_distinct_examples"] += distinct and large

    report = {
        "schema": "arc2-local-context-rule-v18-paired-loo-v1",
        "variants": [{"radius": radius, "minimum_context_support": support} for radius, support in VARIANTS],
        "source_split": "official ARC-AGI-2 training",
        "eligible_loo_folds": eligible_folds,
        "predicted_loo_folds": len(records),
        "worker_errors": worker_errors,
        "loo": {f"radius{r}_support{s}": stats for (r, s), stats in loo_stats.items()},
        "challenge_tasks": len(challenge),
        "challenge_examples": len(challenge_records),
        "challenge": {f"radius{r}_support{s}": stats for (r, s), stats in challenge_stats.items()},
        "runtime_received_heldout_outputs": False,
        "heldout_outputs_read_only_after_all_runtime_predictions": True,
        "runtime_received_challenge_targets": False,
        "challenge_targets_read_only_after_all_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "data_use": "public labels used only for offline matched evaluation; no task-specific runtime rules",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge": _sha(CHALLENGE),
            "baseline_submission": _sha(BASELINE),
            "adapter": _sha(ROOT / "接続/ARC2/Kaggle提出.py"),
            "composite_geometry_module": _sha(ROOT / "接続/ARC2/複合幾何変換候補.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"loo": report["loo"], "challenge": report["challenge"], "elapsed_seconds": report["elapsed_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
