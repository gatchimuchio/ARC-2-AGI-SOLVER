"""Evaluate same-shape teacher filtering for the local-context second answer."""
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _worker(adapter, task):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture):
        status = adapter._worker(task)
    lines = [line for line in capture.getvalue().splitlines() if line.strip()]
    if status or not lines:
        return None
    payload = json.loads(lines[-1])
    rows = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return None
    return {"attempt_1": rows[0].get("answer"), "attempt_2": rows[0].get("second_answer")}


def _dims(grid):
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return None
    width = len(grid[0])
    return (len(grid), width) if all(isinstance(row, list) and len(row) == width for row in grid) else None


def _context(grid, row, column):
    height, width = len(grid), len(grid[0])
    return tuple(
        grid[rr][cc] if 0 <= rr < height and 0 <= cc < width else -1
        for dr in (-1, 0, 1)
        for dc in (-1, 0, 1)
        for rr, cc in ((row + dr, column + dc),)
    )


def _candidate(teachers, query):
    shape = _dims(query)
    if shape is None:
        return None, 0
    compatible = []
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if _dims(source) == shape and _dims(target) == shape:
            compatible.append((source, target))
    if not compatible:
        return None, 0
    outputs = defaultdict(Counter)
    for source, target in compatible:
        for r in range(shape[0]):
            for c in range(shape[1]):
                outputs[_context(source, r, c)][target[r][c]] += 1
    mapping = {}
    for pattern, counts in outputs.items():
        if len(counts) == 1:
            mapping[pattern] = next(iter(counts))
    predicted = [row[:] for row in query]
    changes = 0
    for r in range(shape[0]):
        for c in range(shape[1]):
            color = mapping.get(_context(query, r, c))
            if color is not None and color != query[r][c]:
                predicted[r][c] = color
                changes += 1
    return (predicted if changes else None), len(compatible)


def _combine(baseline, candidate):
    first, second = baseline["attempt_1"], baseline["attempt_2"]
    if candidate is not None and second == first and candidate != first:
        second = candidate
    return {"attempt_1": first, "attempt_2": second}


def _exact(row, target):
    return any(row.get(key) == target for key in ("attempt_1", "attempt_2"))


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

    files = sorted(SOURCE_ROOT.glob("*.json"))
    loo_records = []
    eligible_folds = worker_errors = compatible_folds = 0
    for path in files:
        task_data = json.loads(path.read_text(encoding="utf-8"))
        training = task_data.get("train", [])
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            if not teachers:
                continue
            eligible_folds += 1
            candidate, count = _candidate(teachers, held["input"])
            compatible_folds += count > 0
            if candidate is None:
                continue
            baseline = _worker(Kaggle提出, {"train": teachers, "test": [{"input": held["input"]}]})
            if baseline is None:
                worker_errors += 1
                continue
            loo_records.append({"path": path, "fold": held_index, "baseline": baseline, "candidate": candidate, "compatible_teachers": count})

    loo = {"candidate_fit_folds": len(loo_records), "baseline_exact": 0, "combined_exact": 0,
           "newly_correct": 0, "regressions": 0, "distinct_candidate_folds": 0,
           "fit_with_one_compatible_teacher": 0, "fit_with_two_or_more_compatible_teachers": 0}
    for record in loo_records:
        target = json.loads(record["path"].read_text(encoding="utf-8"))["train"][record["fold"]]["output"]
        before = _exact(record["baseline"], target)
        after = _exact(_combine(record["baseline"], record["candidate"]), target)
        loo["baseline_exact"] += before
        loo["combined_exact"] += after
        loo["newly_correct"] += after and not before
        loo["regressions"] += before and not after
        loo["distinct_candidate_folds"] += record["candidate"] not in (record["baseline"]["attempt_1"], record["baseline"]["attempt_2"])
        loo["fit_with_one_compatible_teacher"] += record["compatible_teachers"] == 1
        loo["fit_with_two_or_more_compatible_teachers"] += record["compatible_teachers"] >= 2

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline_submission = json.loads(BASELINE.read_text(encoding="utf-8"))
    challenge_records = []
    compatible_challenge_examples = 0
    for task_id, task in challenge.items():
        geometry = CompositeGeometryCandidate(task["train"])
        for index, pair in enumerate(task.get("test", [])):
            base = baseline_submission[task_id][index]
            first, second = base["attempt_1"], base["attempt_2"]
            geometry_candidate, _ = geometry.候補(pair["input"], {})
            if valid_grid(geometry_candidate) and geometry_candidate != first:
                second = geometry_candidate
            candidate, compatible_count = _candidate(task["train"], pair["input"])
            compatible_challenge_examples += compatible_count > 0
            challenge_records.append({"task_id": task_id, "index": index, "input": pair["input"],
                                      "baseline": {"attempt_1": first, "attempt_2": second},
                                      "candidate": candidate, "compatible_teachers": compatible_count})

    # Read public targets only after predictions for every fold and challenge example are frozen.
    challenge_stats = {"baseline_exact_examples": 0, "combined_exact_examples": 0,
                       "newly_correct_examples": 0, "regressed_examples": 0,
                       "fit_examples": 0, "distinct_candidates": 0,
                       "large_fit_examples": 0, "large_distinct_candidates": 0,
                       "fit_with_one_compatible_teacher": 0, "fit_with_two_or_more_compatible_teachers": 0}
    task_rows = {}
    for record in challenge_records:
        label_data = json.loads((SOURCE_ROOT / f"{record['task_id']}.json").read_text(encoding="utf-8"))
        target = label_data["test"][record["index"]]["output"]
        before = _exact(record["baseline"], target)
        after = _exact(_combine(record["baseline"], record["candidate"]), target)
        stats = challenge_stats
        stats["baseline_exact_examples"] += before
        stats["combined_exact_examples"] += after
        stats["newly_correct_examples"] += after and not before
        stats["regressed_examples"] += before and not after
        distinct = record["candidate"] is not None and record["candidate"] not in (record["baseline"]["attempt_1"], record["baseline"]["attempt_2"])
        large = len(record["input"]) * len(record["input"][0]) > 100
        stats["fit_examples"] += record["candidate"] is not None
        stats["distinct_candidates"] += distinct
        stats["large_fit_examples"] += record["candidate"] is not None and large
        stats["large_distinct_candidates"] += distinct and large
        stats["fit_with_one_compatible_teacher"] += record["candidate"] is not None and record["compatible_teachers"] == 1
        stats["fit_with_two_or_more_compatible_teachers"] += record["candidate"] is not None and record["compatible_teachers"] >= 2
        task = task_rows.setdefault(record["task_id"], {"before": [], "after": []})
        task["before"].append(before)
        task["after"].append(after)
    challenge_stats["baseline_exact_tasks"] = sum(all(row["before"]) for row in task_rows.values())
    challenge_stats["combined_exact_tasks"] = sum(all(row["after"]) for row in task_rows.values())
    challenge_stats["newly_correct_tasks"] = sum(all(row["after"]) and not all(row["before"]) for row in task_rows.values())
    challenge_stats["regressed_tasks"] = sum(all(row["before"]) and not all(row["after"]) for row in task_rows.values())

    report = {
        "schema": "arc2-shape-filtered-local-context-v18-loo-v1",
        "candidate": {"radius": 1, "minimum_context_support": 1,
                      "uses_only_teacher_pairs_matching_query_input_and_output_shape": True,
                      "unknown_or_conflicting_contexts_keep_input_color": True},
        "source_split": "official ARC-AGI-2 training",
        "loo_eligible_folds_with_at_least_one_teacher": eligible_folds,
        "loo_folds_with_compatible_teacher": compatible_folds,
        "loo_candidate_fit_and_worker_folds": len(loo_records),
        "loo_worker_errors": worker_errors,
        "loo": loo,
        "challenge_tasks": len(challenge),
        "challenge_examples": len(challenge_records),
        "challenge_examples_with_compatible_teacher": compatible_challenge_examples,
        "challenge_vs_v18": challenge_stats,
        "runtime_received_heldout_outputs": False,
        "heldout_outputs_read_only_after_candidate_predictions": True,
        "runtime_received_challenge_targets": False,
        "challenge_targets_read_only_after_candidate_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "data_use": "public labels used only for offline paired evaluation; no task-identifier rules",
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
    print(json.dumps({"loo": report["loo"], "loo_candidate_fit_and_worker_folds": report["loo_candidate_fit_and_worker_folds"],
                      "challenge_vs_v18": report["challenge_vs_v18"], "elapsed_seconds": report["elapsed_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
