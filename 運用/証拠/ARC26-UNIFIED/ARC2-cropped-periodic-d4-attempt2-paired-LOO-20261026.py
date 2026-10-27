"""Paired public-training LOO for crop-then-position-specific-D4 tiling."""
from __future__ import annotations

from collections import Counter
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
sys.path.insert(0, str(ROOT))

from 接続.ARC2.格子D4教材 import _変換群  # noqa: E402
from 接続.ARC2.単純変換候補 import valid_grid  # noqa: E402


def _crop(grid):
    counts = Counter(color for row in grid for color in row)
    if not counts:
        return None
    background = min(counts, key=lambda color: (-counts[color], color))
    points = [(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value != background]
    if not points:
        return None
    r0, r1 = min(r for r, _ in points), max(r for r, _ in points) + 1
    c0, c1 = min(c for _, c in points), max(c for _, c in points) + 1
    return [row[c0:c1] for row in grid[r0:r1]]


class CroppedPeriodicD4:
    def __init__(self, teachers):
        self.programs = []
        if not isinstance(teachers, (list, tuple)) or len(teachers) < 2:
            return
        sources = [_crop(pair["input"]) for pair in teachers]
        if any(source is None for source in sources):
            return
        if len({tuple(map(tuple, source)) for source in sources}) < 2:
            return

        common_ratios = None
        for pair, source in zip(teachers, sources, strict=True):
            out_h, out_w = len(pair["output"]), len(pair["output"][0])
            src_h, src_w = len(source), len(source[0])
            ratios = set()
            for tile_h, tile_w in {(src_h, src_w), (src_w, src_h)}:
                if out_h % tile_h or out_w % tile_w:
                    continue
                rows, columns = out_h // tile_h, out_w // tile_w
                if rows * columns >= 2:
                    ratios.add((rows, columns, tile_h, tile_w))
            common_ratios = ratios if common_ratios is None else common_ratios & ratios
        if not common_ratios:
            return

        transforms = tuple(_変換群([[0]]))
        for rows, columns, tile_h, tile_w in sorted(common_ratios):
            placements = []
            for tile_row in range(rows):
                placement_row = []
                for tile_column in range(columns):
                    shared = None
                    for pair, source in zip(teachers, sources, strict=True):
                        tile = [
                            row[tile_column * tile_w:(tile_column + 1) * tile_w]
                            for row in pair["output"][tile_row * tile_h:(tile_row + 1) * tile_h]
                        ]
                        matches = {
                            name for name, grid in _変換群(source).items()
                            if len(grid) == tile_h and len(grid[0]) == tile_w and grid == tile
                        }
                        shared = matches if shared is None else shared & matches
                        if not shared:
                            break
                    if not shared:
                        break
                    placement_row.append(tuple(name for name in transforms if name in shared))
                if len(placement_row) != columns:
                    break
                placements.append(tuple(placement_row))
            if len(placements) == rows:
                self.programs.append((rows, columns, tile_h, tile_w, tuple(placements)))

    def 候補(self, grid, _policy=None):
        if not valid_grid(grid):
            return None, {"reason": "invalid_grid"}
        source = _crop(grid)
        if source is None:
            return None, {"reason": "empty_foreground"}
        outputs = set()
        for rows, columns, tile_h, tile_w, placements in self.programs:
            if len(source) not in (tile_h, tile_w) or len(source[0]) not in (tile_w, tile_h):
                continue
            out_h, out_w = rows * tile_h, columns * tile_w
            if out_h > 30 or out_w > 30:
                continue
            transforms = _変換群(source)
            output = [[None] * out_w for _ in range(out_h)]
            possible = True
            for tile_row, placement_row in enumerate(placements):
                for tile_column, operation_names in enumerate(placement_row):
                    tile_options = {
                        tuple(tuple(row) for row in transforms[name])
                        for name in operation_names
                        if len(transforms[name]) == tile_h and len(transforms[name][0]) == tile_w
                    }
                    if len(tile_options) != 1:
                        possible = False
                        break
                    tile = next(iter(tile_options))
                    for r, row in enumerate(tile):
                        output[tile_row * tile_h + r][tile_column * tile_w:(tile_column + 1) * tile_w] = row
                if not possible:
                    break
            if possible and valid_grid(output):
                outputs.add(tuple(tuple(row) for row in output))
        if len(outputs) != 1:
            return None, {"reason": "no_or_ambiguous_fitted_tiling", "fitted_programs": len(self.programs)}
        return [list(row) for row in next(iter(outputs))], {"fitted_programs": len(self.programs)}


class _CompositeGeometryDisabled:
    def __init__(self, _teachers):
        pass

    def 候補(self, _grid, _policy):
        return None, {"reason": "paired_baseline_disabled_composite_geometry"}

    def 記録(self):
        return {"training_examples": 0, "program_descriptors": 0, "fitted_programs": 0, "selected_programs": 0}


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
    from 接続.ARC2 import Kaggle提出
    candidate_module = importlib.import_module("接続.ARC2.複合幾何変換候補")
    original_family = candidate_module.CompositeGeometryCandidate
    records = []
    eligible = fit_folds = worker_errors = 0
    files = sorted(SOURCE_ROOT.glob("*.json"))
    try:
        candidate_module.CompositeGeometryCandidate = _CompositeGeometryDisabled
        for path in files:
            source = json.loads(path.read_text(encoding="utf-8"))
            training = source.get("train", [])
            for held_index, held in enumerate(training):
                teachers = [pair for i, pair in enumerate(training) if i != held_index]
                if len(teachers) < 2:
                    continue
                eligible += 1
                learner = CroppedPeriodicD4(teachers)
                candidate, _ = learner.候補(held["input"])
                if candidate is None:
                    continue
                fit_folds += 1
                baseline = _worker(Kaggle提出, {"train": teachers, "test": [{"input": held["input"]}]})
                if baseline is None:
                    worker_errors += 1
                    continue
                current = dict(baseline)
                if candidate != baseline["attempt_1"] and baseline["attempt_2"] == baseline["attempt_1"]:
                    current["attempt_2"] = candidate
                records.append({"task": path.stem, "fold": held_index, "candidate": candidate, "baseline": baseline, "current": current})
    finally:
        candidate_module.CompositeGeometryCandidate = original_family

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

    report = {
        "schema": "arc2-cropped-periodic-d4-attempt2-paired-loo-v1",
        "source_split": "official ARC-AGI-2 training",
        "training_tasks": len(files),
        "eligible_loo_folds": eligible,
        "candidate_fit_and_predicted_folds": fit_folds,
        "candidate_exact_folds": candidate_exact,
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
        "candidate_policy": "crop each input by its modal background; tile by a shared ratio; each tile uses a D4 transform position learned from every training pair; fill attempt_2 only when the baseline pair is duplicate",
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "source_sha256": {
            "runner": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "hds_connector": hashlib.sha256((ROOT / "接続/ARC2/HDS接続.py").read_bytes()).hexdigest(),
            "kaggle_adapter": hashlib.sha256((ROOT / "接続/ARC2/Kaggle提出.py").read_bytes()).hexdigest(),
            "periodic_d4_module": hashlib.sha256((ROOT / "接続/ARC2/周期タイルD4教材.py").read_bytes()).hexdigest(),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
