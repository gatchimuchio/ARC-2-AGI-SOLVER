"""Paired public-training LOO for crop-only and composite geometry HDS candidates."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
OUTPUT = Path(__file__).with_suffix(".json")


class _CompositeGeometryDisabled:
    def __init__(self, _teachers):
        self._record = {
            "training_examples": 0,
            "program_descriptors": 0,
            "fitted_programs": 0,
            "selected_programs": 0,
        }

    def 候補(self, _grid, _policy):
        return None, {"reason": "paired_baseline_disabled_composite_geometry"}

    def 記録(self):
        return dict(self._record)


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
    return {
        "attempt_1": rows[0].get("answer"),
        "attempt_2": rows[0].get("second_answer"),
    }


def _exact(attempts, target):
    return isinstance(attempts, dict) and any(
        attempts.get(key) == target for key in ("attempt_1", "attempt_2")
    )


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    started = time.monotonic()
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    sys.path.insert(0, str(ROOT))

    from 接続.ARC2 import HDS接続, Kaggle提出
    from 接続.ARC2.複合幾何変換候補 import CompositeGeometryCandidate

    original_family = HDS接続.CompositeGeometryCandidate
    records = []
    eligible_folds = fitting_folds = worker_errors = 0
    files = sorted(SOURCE_ROOT.glob("*.json"))
    try:
        for path in files:
            source = json.loads(path.read_text(encoding="utf-8"))
            training = source.get("train", [])
            for held_index, held in enumerate(training):
                teachers = [pair for i, pair in enumerate(training) if i != held_index]
                if len(teachers) < 2:
                    continue
                eligible_folds += 1
                learner = CompositeGeometryCandidate(teachers)
                candidate, _ = learner.候補(held["input"], {})
                if candidate is None:
                    continue
                fitting_folds += 1
                task = {"train": teachers, "test": [{"input": held["input"]}]}

                HDS接続.CompositeGeometryCandidate = _CompositeGeometryDisabled
                baseline = _worker(Kaggle提出, task)
                HDS接続.CompositeGeometryCandidate = original_family
                current = _worker(Kaggle提出, task)
                worker_errors += baseline is None or current is None
                records.append({
                    "task": path.stem,
                    "fold": held_index,
                    "candidate": candidate,
                    "baseline": baseline,
                    "current": current,
                })
    finally:
        HDS接続.CompositeGeometryCandidate = original_family

    # Held-out outputs are first read after all baseline/current predictions exist.
    exact_counts = {"baseline": 0, "current": 0, "candidate": 0}
    newly_correct = regressed = changed_first = changed_second = 0
    distinct_before = distinct_after = 0
    for row in records:
        source = json.loads((SOURCE_ROOT / f"{row['task']}.json").read_text(encoding="utf-8"))
        target = source["train"][row["fold"]]["output"]
        baseline_exact = _exact(row["baseline"], target)
        current_exact = _exact(row["current"], target)
        exact_counts["baseline"] += baseline_exact
        exact_counts["current"] += current_exact
        exact_counts["candidate"] += row["candidate"] == target
        newly_correct += current_exact and not baseline_exact
        regressed += baseline_exact and not current_exact
        changed_first += row["baseline"]["attempt_1"] != row["current"]["attempt_1"]
        changed_second += row["baseline"]["attempt_2"] != row["current"]["attempt_2"]
        distinct_before += row["baseline"]["attempt_1"] != row["baseline"]["attempt_2"]
        distinct_after += row["current"]["attempt_1"] != row["current"]["attempt_2"]

    module_path = ROOT / "接続/ARC2/複合幾何変換候補.py"
    hds_path = ROOT / "接続/ARC2/HDS接続.py"
    adapter_path = ROOT / "接続/ARC2/Kaggle提出.py"
    report = {
        "schema": "arc2-composite-geometry-crop-only-paired-loo-v1",
        "source_split": "official ARC-AGI-2 training",
        "training_tasks": len(files),
        "eligible_loo_folds": eligible_folds,
        "candidate_fit_and_predicted_folds": fitting_folds,
        "worker_errors": worker_errors,
        "baseline_exact_folds": exact_counts["baseline"],
        "current_exact_folds": exact_counts["current"],
        "candidate_exact_folds": exact_counts["candidate"],
        "delta_exact_folds": exact_counts["current"] - exact_counts["baseline"],
        "newly_correct_folds": newly_correct,
        "regressed_folds": regressed,
        "changed_attempt_1_folds": changed_first,
        "changed_attempt_2_folds": changed_second,
        "distinct_attempt_pairs_baseline": distinct_before,
        "distinct_attempt_pairs_current": distinct_after,
        "runtime_received_heldout_outputs": False,
        "heldout_outputs_read_only_after_all_runtime_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_sha256": {
            "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "composite_geometry_module": hashlib.sha256(module_path.read_bytes()).hexdigest(),
            "hds_connector": hashlib.sha256(hds_path.read_bytes()).hexdigest(),
            "kaggle_adapter": hashlib.sha256(adapter_path.read_bytes()).hexdigest(),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
