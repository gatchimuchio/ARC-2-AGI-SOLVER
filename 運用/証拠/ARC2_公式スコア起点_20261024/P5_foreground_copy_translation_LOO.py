"""Probe copying the complete foreground by one fixed translation on LOO."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from types import ModuleType


ROOT = Path(__file__).resolve().parents[3]
REFERENCE_COMMIT = "2759d393a8d79824d36754785ce16f66d0493ebd"
D4_PATH = "接続/ARC2/格子D4教材.py"
D4_SHA256 = "a5d6a2eedb063a876b47cd5d2fdf28cec13af535d89b9fef65df41b81c5ccf18"
WHOLE_TRANSLATION_PATH = "接続/ARC2/全前景平行移動教材.py"
TRAINING_DIR = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
sys.path.insert(0, str(ROOT))
from 接続.ARC2.全前景平行移動教材 import 全前景平行移動教材  # noqa: E402


def background(grid):
    counts = {
        color: sum(value == color for row in grid for value in row)
        for color in {value for row in grid for value in row}
    }
    return min(counts, key=lambda color: (-counts[color], color))


def fit_copy_offsets(teachers):
    if len(teachers) < 3:
        return set()
    inputs = [tuple(tuple(row) for row in pair["input"]) for pair in teachers]
    if len(set(inputs)) != len(inputs):
        return set()
    common = None
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if not valid_grid(source) or not valid_grid(target):
            return set()
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return set()
        bg = background(source)
        source_map = {
            (row, col): color
            for row, values in enumerate(source)
            for col, color in enumerate(values)
            if color != bg
        }
        target_map = {
            (row, col): color
            for row, values in enumerate(target)
            for col, color in enumerate(values)
            if color != bg
        }
        if not source_map or any(target_map.get(cell) != color for cell, color in source_map.items()):
            return set()
        added = {cell: color for cell, color in target_map.items() if cell not in source_map}
        if len(added) != len(source_map):
            return set()
        dr = min(row for row, _ in added) - min(row for row, _ in source_map)
        dc = min(col for _, col in added) - min(col for _, col in source_map)
        if (dr, dc) == (0, 0):
            return set()
        shifted = {
            (row + dr, col + dc): color for (row, col), color in source_map.items()
        }
        if shifted != added or target_map != source_map | shifted:
            return set()
        if common is None:
            common = {(dr, dc)}
        else:
            common.intersection_update({(dr, dc)})
        if not common:
            return set()
    return common or set()


def valid_grid(grid):
    return (
        isinstance(grid, list)
        and 1 <= len(grid) <= 30
        and all(
            isinstance(row, list)
            and 1 <= len(row) <= 30
            and len(row) == len(grid[0])
            and all(type(color) is int and 0 <= color <= 9 for color in row)
            for row in grid
        )
    )


def predict_copy(grid, offsets):
    if not valid_grid(grid):
        return None
    bg = background(grid)
    height, width = len(grid), len(grid[0])
    source = {
        (row, col): color
        for row, values in enumerate(grid)
        for col, color in enumerate(values)
        if color != bg
    }
    if not source:
        return None
    outputs = set()
    for dr, dc in offsets:
        shifted = {}
        for (row, col), color in source.items():
            target = (row + dr, col + dc)
            if not (0 <= target[0] < height and 0 <= target[1] < width):
                break
            if target in source:
                break
            shifted[target] = color
        else:
            if not shifted:
                continue
            out = [row[:] for row in grid]
            for (row, col), color in shifted.items():
                out[row][col] = color
            outputs.add(tuple(tuple(row) for row in out))
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


def self_check():
    teachers = [
        {"input": [[1, 0, 0, 0, 0, 0]], "output": [[1, 0, 1, 0, 0, 0]]},
        {"input": [[0, 1, 0, 0, 0, 0]], "output": [[0, 1, 0, 1, 0, 0]]},
        {"input": [[0, 0, 1, 0, 0, 0]], "output": [[0, 0, 1, 0, 1, 0]]},
    ]
    offsets = fit_copy_offsets(teachers)
    if offsets != {(0, 2)} or predict_copy(teachers[0]["input"], offsets) != teachers[0]["output"]:
        raise SystemExit("foreground copy self-check failed")
    if fit_copy_offsets(teachers + [teachers[0]]):
        raise SystemExit("duplicate-input copy self-check failed")


def main():
    raw_d4 = subprocess.run(
        ["git", "show", f"{REFERENCE_COMMIT}:{D4_PATH}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if hashlib.sha256(raw_d4).hexdigest() != D4_SHA256:
        raise SystemExit("reference D4 source hash mismatch")
    d4_module = ModuleType("arc2_copy_translation_d4_reference")
    exec(compile(raw_d4, f"{REFERENCE_COMMIT}:{D4_PATH}", "exec"), d4_module.__dict__)
    d4_sha = hashlib.sha256(raw_d4).hexdigest()
    whole_sha = hashlib.sha256((ROOT / WHOLE_TRANSLATION_PATH).read_bytes()).hexdigest()
    self_check()

    manifest = hashlib.sha256()
    files = sorted(TRAINING_DIR.glob("*.json"))
    folds = eligible = 0
    baseline_answers = baseline_exact = baseline_wrong = 0
    whole_answers = whole_exact = whole_wrong = 0
    copy_answers = copy_exact = copy_wrong = 0
    incremental = incremental_exact = incremental_wrong = conflicts = agreements = 0
    started = time.perf_counter()
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) < 4:
            continue
        eligible += 1
        for index, heldout in enumerate(examples):
            folds += 1
            teachers = [pair for i, pair in enumerate(examples) if i != index]
            base, _ = d4_module.格子D4教材(teachers).候補(heldout["input"], {})
            if base is not None:
                baseline_answers += 1
                if base == heldout["output"]:
                    baseline_exact += 1
                else:
                    baseline_wrong += 1
            whole, _ = 全前景平行移動教材(teachers).候補(heldout["input"], {})
            if whole is not None:
                whole_answers += 1
                if whole == heldout["output"]:
                    whole_exact += 1
                else:
                    whole_wrong += 1
            copy = predict_copy(heldout["input"], fit_copy_offsets(teachers))
            if copy is None:
                continue
            copy_answers += 1
            if copy == heldout["output"]:
                copy_exact += 1
            else:
                copy_wrong += 1
            existing = [value for value in (base, whole) if value is not None]
            if not existing:
                incremental += 1
                if copy == heldout["output"]:
                    incremental_exact += 1
                else:
                    incremental_wrong += 1
            elif all(value == copy for value in existing):
                agreements += 1
            else:
                conflicts += 1

    result = {
        "schema": "arc2-p5-foreground-copy-translation-loo.v1",
        "instruction_id": "ARC2-SCORE-GATE-20261024",
        "reference_source_commit": REFERENCE_COMMIT,
        "source_sha256": {
            f"{REFERENCE_COMMIT}:{D4_PATH}": d4_sha,
            WHOLE_TRANSLATION_PATH: whole_sha,
            Path(__file__).name: hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "data_source": "public ARC-AGI-2 training split only",
        "training_manifest_sha256": manifest.hexdigest(),
        "public_training_files": len(files),
        "eligible_tasks_minimum_teacher_support_3": eligible,
        "loo_folds": folds,
        "baseline_D4_answers": baseline_answers,
        "baseline_D4_exact": baseline_exact,
        "baseline_D4_wrong": baseline_wrong,
        "whole_translation_answers": whole_answers,
        "whole_translation_exact": whole_exact,
        "whole_translation_wrong": whole_wrong,
        "copy_translation_answers": copy_answers,
        "copy_translation_exact": copy_exact,
        "copy_translation_wrong": copy_wrong,
        "incremental_answers_over_D4_and_whole_translation": incremental,
        "incremental_exact": incremental_exact,
        "incremental_wrong": incremental_wrong,
        "conflicts_with_existing_answer": conflicts,
        "agreements_with_existing_answer": agreements,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "evaluation_solutions_read": False,
        "task_identifiers_or_grids_saved": False,
        "decision": "REVIEW_REQUIRED"
        if incremental_exact and not incremental_wrong and not conflicts
        else "REJECT_OR_REFINE",
    }
    Path(__file__).with_suffix(".json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
