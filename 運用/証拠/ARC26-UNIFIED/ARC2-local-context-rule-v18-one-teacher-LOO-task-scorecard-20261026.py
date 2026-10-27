"""One-teacher paired LOO and task-level scorecard for the local-context candidate."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
BASELINE = ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v16-periodic-tiling-20261026/full-runtime-output-20261026/submission.json"
OUTPUT = Path(__file__).with_suffix(".json")
CONTEXT_SOURCE = Path(__file__).with_name("ARC2-local-context-rule-v18-paired-LOO-20261026.py")


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

    spec = importlib.util.spec_from_file_location("local_context_evidence", CONTEXT_SOURCE)
    local_context = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local_context)
    variant = (1, 1)

    loo_records = []
    eligible_folds = worker_errors = 0
    files = sorted(SOURCE_ROOT.glob("*.json"))
    for path in files:
        source = json.loads(path.read_text(encoding="utf-8"))
        training = source.get("train", [])
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            if not teachers:
                continue
            eligible_folds += 1
            candidate = local_context._candidate(teachers, held["input"], *variant)
            if candidate is None:
                continue
            baseline = _worker(Kaggle提出, {"train": teachers, "test": [{"input": held["input"]}]})
            if baseline is None:
                worker_errors += 1
                continue
            loo_records.append({"path": path, "fold": held_index, "baseline": baseline, "candidate": candidate})

    loo = {"fit_folds": len(loo_records), "baseline_exact": 0, "combined_exact": 0,
           "newly_correct": 0, "regressions": 0, "distinct_candidate_folds": 0}
    for record in loo_records:
        target = json.loads(record["path"].read_text(encoding="utf-8"))["train"][record["fold"]]["output"]
        before = _exact(record["baseline"], target)
        combined = _combine(record["baseline"], record["candidate"])
        after = _exact(combined, target)
        loo["baseline_exact"] += before
        loo["combined_exact"] += after
        loo["newly_correct"] += after and not before
        loo["regressions"] += before and not after
        loo["distinct_candidate_folds"] += record["candidate"] not in (record["baseline"]["attempt_1"], record["baseline"]["attempt_2"])

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    baseline_submission = json.loads(BASELINE.read_text(encoding="utf-8"))
    challenge_records = []
    for task_id, task in challenge.items():
        geometry = CompositeGeometryCandidate(task["train"])
        for index, test in enumerate(task.get("test", [])):
            base = baseline_submission[task_id][index]
            first, second = base["attempt_1"], base["attempt_2"]
            geometry_candidate, _ = geometry.候補(test["input"], {})
            if valid_grid(geometry_candidate) and geometry_candidate != first:
                second = geometry_candidate
            v18 = {"attempt_1": first, "attempt_2": second}
            candidate = local_context._candidate(task["train"], test["input"], *variant)
            challenge_records.append({
                "task_id": task_id,
                "index": index,
                "input": test["input"],
                "baseline": v18,
                "candidate": candidate,
            })

    # Labels are only read for scoring after all local-context and v18 predictions exist.
    challenge_stats = {"baseline_exact_examples": 0, "combined_exact_examples": 0,
                       "newly_correct_examples": 0, "regressed_examples": 0,
                       "fit_examples": 0, "distinct_candidates": 0,
                       "large_fit_examples": 0, "large_distinct_candidates": 0}
    task_rows = {}
    for record in challenge_records:
        label_source = json.loads((SOURCE_ROOT / f"{record['task_id']}.json").read_text(encoding="utf-8"))
        target = label_source["test"][record["index"]]["output"]
        before = _exact(record["baseline"], target)
        combined = _combine(record["baseline"], record["candidate"])
        after = _exact(combined, target)
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
        task = task_rows.setdefault(record["task_id"], {"baseline": [], "combined": []})
        task["baseline"].append(before)
        task["combined"].append(after)
    challenge_stats["baseline_exact_tasks"] = sum(all(row["baseline"]) for row in task_rows.values())
    challenge_stats["combined_exact_tasks"] = sum(all(row["combined"]) for row in task_rows.values())
    challenge_stats["newly_correct_tasks"] = sum(all(row["combined"]) and not all(row["baseline"]) for row in task_rows.values())
    challenge_stats["regressed_tasks"] = sum(all(row["baseline"]) and not all(row["combined"]) for row in task_rows.values())

    report = {
        "schema": "arc2-local-context-rule-v18-one-teacher-LOO-task-scorecard-v1",
        "candidate": {"radius": 1, "minimum_context_support": 1, "uses_input_fallback_for_unknown_or_conflicting_contexts": True},
        "source_split": "official ARC-AGI-2 training",
        "loo_eligible_folds_with_at_least_one_teacher": eligible_folds,
        "loo_candidate_fit_and_worker_folds": loo["fit_folds"],
        "loo_worker_errors": worker_errors,
        "loo": loo,
        "challenge_tasks": len(challenge),
        "challenge_examples": len(challenge_records),
        "challenge_vs_v18": challenge_stats,
        "runtime_received_heldout_outputs": False,
        "heldout_outputs_read_only_after_candidate_predictions": True,
        "runtime_received_challenge_targets": False,
        "challenge_targets_read_only_after_candidate_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "data_use": "public labels used only for offline evaluation; no task-identifier rules",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "local_context_candidate_source": _sha(CONTEXT_SOURCE),
            "challenge": _sha(CHALLENGE),
            "baseline_submission": _sha(BASELINE),
            "adapter": _sha(ROOT / "接続/ARC2/Kaggle提出.py"),
            "composite_geometry_module": _sha(ROOT / "接続/ARC2/複合幾何変換候補.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"loo": report["loo"], "challenge_vs_v18": report["challenge_vs_v18"], "elapsed_seconds": report["elapsed_seconds"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
