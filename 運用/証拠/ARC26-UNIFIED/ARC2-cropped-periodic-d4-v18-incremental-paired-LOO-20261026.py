"""Paired LOO for the integrated crop-periodic fallback on top of v18."""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
OUTPUT = Path(__file__).with_suffix(".json")


class _CroppedPeriodicD4Disabled:
    def __init__(self, _teachers):
        pass

    def 候補(self, _grid, _policy=None):
        return None, {"reason": "paired_v18_baseline_disabled_crop_periodic"}

    def 記録(self):
        return {"training_examples": 0, "fitted_programs": 0}


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


def _exact(attempts, target):
    return isinstance(attempts, dict) and any(attempts.get(key) == target for key in ("attempt_1", "attempt_2"))


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    started = time.monotonic()
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import Kaggle提出

    candidate_module = importlib.import_module("接続.ARC2.複合crop周期タイルD4候補")
    original_family = candidate_module.複合crop周期タイルD4候補
    records = []
    eligible = fitting = errors = 0
    files = sorted(SOURCE_ROOT.glob("*.json"))
    try:
        for path in files:
            source = json.loads(path.read_text(encoding="utf-8"))
            pairs = source.get("train", [])
            for held_index, held in enumerate(pairs):
                teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
                if len(teachers) < 2:
                    continue
                eligible += 1
                candidate, _ = original_family(teachers).候補(held["input"])
                if candidate is None:
                    continue
                fitting += 1
                task = {"train": teachers, "test": [{"input": held["input"]}]}
                candidate_module.複合crop周期タイルD4候補 = _CroppedPeriodicD4Disabled
                baseline = _worker(Kaggle提出, task)
                candidate_module.複合crop周期タイルD4候補 = original_family
                current = _worker(Kaggle提出, task)
                if baseline is None or current is None:
                    errors += 1
                    continue
                records.append({"task": path.stem, "fold": held_index, "candidate": candidate, "baseline": baseline, "current": current})
    finally:
        candidate_module.複合crop周期タイルD4候補 = original_family

    baseline_exact = current_exact = candidate_exact = newly_correct = regressed = 0
    changed_first = changed_second = distinct_before = distinct_after = 0
    for row in records:
        source = json.loads((SOURCE_ROOT / f"{row['task']}.json").read_text(encoding="utf-8"))
        target = source["train"][row["fold"]]["output"]
        before, after = _exact(row["baseline"], target), _exact(row["current"], target)
        baseline_exact += before
        current_exact += after
        candidate_exact += row["candidate"] == target
        newly_correct += after and not before
        regressed += before and not after
        changed_first += row["baseline"]["attempt_1"] != row["current"]["attempt_1"]
        changed_second += row["baseline"]["attempt_2"] != row["current"]["attempt_2"]
        distinct_before += row["baseline"]["attempt_1"] != row["baseline"]["attempt_2"]
        distinct_after += row["current"]["attempt_1"] != row["current"]["attempt_2"]

    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = {
        "schema": "arc2-cropped-periodic-d4-v18-incremental-paired-loo-v1",
        "source_split": "official ARC-AGI-2 training",
        "training_tasks": len(files),
        "eligible_loo_folds": eligible,
        "candidate_fit_and_predicted_folds": fitting,
        "candidate_exact_folds": candidate_exact,
        "worker_errors": errors,
        "baseline_v18_exact_folds": baseline_exact,
        "current_exact_folds": current_exact,
        "delta_exact_folds": current_exact - baseline_exact,
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
            "runner": sha(Path(__file__)),
            "candidate_module": sha(ROOT / "接続/ARC2/複合crop周期タイルD4候補.py"),
            "hds_connector": sha(ROOT / "接続/ARC2/HDS接続.py"),
            "kaggle_adapter": sha(ROOT / "接続/ARC2/Kaggle提出.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
