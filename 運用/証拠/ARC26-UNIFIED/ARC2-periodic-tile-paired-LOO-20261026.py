"""公開training上で周期タイルD4候補の同一fold比較を再現する。"""

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


class _周期候補無効:
    def __init__(self, _teachers):
        self.全教師再現 = False
        self.タイル行数 = 0
        self.タイル列数 = 0
        self.配置 = ()

    def 候補(self, _grid, _policy):
        return None, {"failure": "paired_baseline_disabled_periodic_family"}

    def 記録(self):
        return {
            "all_training_pairs_reproduced": False,
            "tile_rows": 0,
            "tile_columns": 0,
            "operations_per_tile": [],
        }


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
    started = time.monotonic()
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    sys.path.insert(0, str(ROOT))

    from 接続.ARC2 import HDS接続, Kaggle提出
    from 接続.ARC2.周期タイルD4教材 import 周期タイルD4教材

    original_family = HDS接続.周期タイルD4教材
    records = []
    task_fold_counts = {}
    eligible_folds = 0
    fitting_folds = 0
    worker_errors = 0
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
                learner = 周期タイルD4教材(teachers)
                if not learner.全教師再現:
                    continue
                candidate, _ = learner.候補(held["input"], {})
                if candidate is None:
                    continue
                fitting_folds += 1
                task_fold_counts[path.stem] = task_fold_counts.get(path.stem, 0) + 1
                task = {"train": teachers, "test": [{"input": held["input"]}]}

                HDS接続.周期タイルD4教材 = _周期候補無効
                baseline = _worker(Kaggle提出, task)
                HDS接続.周期タイルD4教材 = original_family
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
        HDS接続.周期タイルD4教材 = original_family

    # All paired runtime predictions are complete before this scoring pass reads
    # the held-out outputs. Targets never enter _worker or the solver task object.
    exact_folds = {"baseline": 0, "current": 0, "candidate": 0}
    added = regressions = 0
    task_fold_scores = {}
    for row in records:
        source = json.loads((SOURCE_ROOT / f"{row['task']}.json").read_text(encoding="utf-8"))
        target = source["train"][row["fold"]]["output"]
        baseline_exact = _exact(row["baseline"], target)
        current_exact = _exact(row["current"], target)
        candidate_exact = row["candidate"] == target
        exact_folds["baseline"] += baseline_exact
        exact_folds["current"] += current_exact
        exact_folds["candidate"] += candidate_exact
        added += current_exact and not baseline_exact
        regressions += baseline_exact and not current_exact
        scores = task_fold_scores.setdefault(row["task"], [0, 0, 0])
        scores[0] += 1
        scores[1] += baseline_exact
        scores[2] += current_exact

    module_path = ROOT / "接続/ARC2/周期タイルD4教材.py"
    hds_path = ROOT / "接続/ARC2/HDS接続.py"
    adapter_path = ROOT / "接続/ARC2/Kaggle提出.py"
    report = {
        "schema": "arc2-periodic-tile-paired-loo-v1",
        "source_split": "official training",
        "training_tasks": len(files),
        "eligible_loo_folds": eligible_folds,
        "periodic_fit_and_predicted_folds": fitting_folds,
        "worker_errors": worker_errors,
        "baseline_exact_folds": exact_folds["baseline"],
        "candidate_exact_folds": exact_folds["candidate"],
        "current_exact_folds": exact_folds["current"],
        "delta_exact_folds": exact_folds["current"] - exact_folds["baseline"],
        "newly_correct_folds": added,
        "regressed_folds": regressions,
        "tasks_with_fitting_folds": len(task_fold_scores),
        "tasks_all_folds_exact_baseline": sum(n == b for n, b, _ in task_fold_scores.values()),
        "tasks_all_folds_exact_current": sum(n == c for n, _, c in task_fold_scores.values()),
        "runtime_received_heldout_outputs": False,
        "heldout_outputs_read_only_after_all_runtime_predictions": True,
        "per_task_predictions_or_targets_saved": False,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_sha256": {
            "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "periodic_tile_module": hashlib.sha256(module_path.read_bytes()).hexdigest(),
            "hds_connector": hashlib.sha256(hds_path.read_bytes()).hexdigest(),
            "kaggle_adapter": hashlib.sha256(adapter_path.read_bytes()).hexdigest(),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
