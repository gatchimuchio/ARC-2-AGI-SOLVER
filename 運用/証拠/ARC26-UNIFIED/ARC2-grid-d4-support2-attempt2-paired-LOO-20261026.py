"""Paired LOO for a strict two-teacher D4/palette candidate as attempt 2."""
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
sys.path.insert(0, str(ROOT))

from 接続.ARC2.格子D4教材 import (  # noqa: E402
    格子D4教材,
    _変換群,
    _有効格子,
    _色写像を学ぶ,
)


class 格子D4二例教材(格子D4教材):
    """Same strict D4 and bijective-palette fit, with support lowered to two."""

    def __init__(self, teachers):
        self.必要支持数 = 2
        self.変換候補 = ()
        self.色写像候補 = ()
        if not isinstance(teachers, (list, tuple)) or len(teachers) < self.必要支持数:
            return
        if any(
            not isinstance(pair, dict)
            or not _有効格子(pair.get("input"))
            or not _有効格子(pair.get("output"))
            for pair in teachers
        ):
            return
        inputs = [tuple(map(tuple, pair["input"])) for pair in teachers]
        if len(set(inputs)) != len(inputs):
            return
        operation_names = tuple(_変換群(teachers[0]["input"]))
        exact = []
        palette = []
        for name in operation_names:
            forward, reverse = {}, {}
            palette_possible = True
            exact_possible = True
            for pair in teachers:
                transformed = _変換群(pair["input"])[name]
                exact_possible = exact_possible and transformed == pair["output"]
                if not _色写像を学ぶ(transformed, pair["output"], forward, reverse):
                    palette_possible = False
                    break
            if exact_possible:
                exact.append(name)
            if palette_possible and any(source != target for source, target in forward.items()):
                palette.append((name, tuple(sorted(forward.items()))))
        self.変換候補 = tuple(exact)
        self.色写像候補 = tuple(palette)


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
    row = rows[0]
    first = row.get("answer")
    if not adapter.格子か(first):
        first = task["test"][0]["input"]
    second = row.get("second_answer")
    if not adapter.格子か(second) or second == first:
        second = first
    return {"attempt_1": first, "attempt_2": second}


def _exact(attempts, target):
    return isinstance(attempts, dict) and target in (attempts["attempt_1"], attempts["attempt_2"])


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    started = time.monotonic()
    os.environ["ARC2_PAYLOAD_ROOT"] = str(ROOT)
    sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
    from 接続.ARC2 import Kaggle提出

    records = []
    eligible = fitting = distinct = worker_errors = 0
    files = sorted(SOURCE_ROOT.glob("*.json"))
    for path in files:
        task_source = json.loads(path.read_text(encoding="utf-8"))
        pairs = task_source.get("train", [])
        for held_index, held in enumerate(pairs):
            teachers = [pair for index, pair in enumerate(pairs) if index != held_index]
            if len(teachers) < 2:
                continue
            eligible += 1
            model = 格子D4二例教材(teachers)
            candidate, _ = model.候補(held["input"], {})
            if candidate is None:
                continue
            fitting += 1
            task = {"train": teachers, "test": [{"input": held["input"]}]}
            baseline = _worker(Kaggle提出, task)
            if baseline is None:
                worker_errors += 1
                continue
            if candidate == baseline["attempt_1"]:
                continue
            distinct += 1
            current = dict(baseline)
            if baseline["attempt_2"] == baseline["attempt_1"]:
                current["attempt_2"] = candidate
            records.append({"task": path.stem, "fold": held_index, "candidate": candidate, "baseline": baseline, "current": current})

    baseline_exact = current_exact = candidate_exact = newly_correct = regressed = 0
    changed_first = changed_second = distinct_before = distinct_after = 0
    for row in records:
        task_source = json.loads((SOURCE_ROOT / f"{row['task']}.json").read_text(encoding="utf-8"))
        target = task_source["train"][row["fold"]]["output"]
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

    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    report = {
        "schema": "arc2-grid-d4-support2-attempt2-paired-loo-v1",
        "source_split": "official ARC-AGI-2 training",
        "training_tasks": len(files),
        "eligible_loo_folds": eligible,
        "candidate_fit_folds": fitting,
        "candidate_distinct_from_primary_folds": distinct,
        "worker_errors": worker_errors,
        "baseline_exact_folds": baseline_exact,
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
        "candidate_policy": "two distinct teacher inputs must agree on one D4 transform or bijective palette map; fills attempt_2 only when distinct and both existing attempts are identical",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_sha256": {
            "runner": sha(Path(__file__)),
            "d4_module": sha(ROOT / "接続/ARC2/格子D4教材.py"),
            "hds_connector": sha(ROOT / "接続/ARC2/HDS接続.py"),
            "kaggle_adapter": sha(ROOT / "接続/ARC2/Kaggle提出.py"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
