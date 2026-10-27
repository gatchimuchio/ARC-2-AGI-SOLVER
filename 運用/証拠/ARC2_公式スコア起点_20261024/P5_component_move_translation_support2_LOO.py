"""Probe moving one complete foreground component by one fixed translation."""

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


def background(grid):
    counts = {
        color: sum(value == color for row in grid for value in row)
        for color in {value for row in grid for value in row}
    }
    return min(counts, key=lambda color: (-counts[color], color))


def foreground_components(grid):
    bg = background(grid)
    foreground = {
        (row, col): color
        for row, values in enumerate(grid)
        for col, color in enumerate(values)
        if color != bg
    }
    components = []
    unseen = set(foreground)
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        stack = [seed]
        component = {}
        while stack:
            cell = stack.pop()
            component[cell] = foreground[cell]
            row, col = cell
            for neighbor in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return foreground, components


def teacher_offsets(pair):
    source, target = pair.get("input"), pair.get("output")
    if not valid_grid(source) or not valid_grid(target):
        return set()
    if len(source) != len(target) or len(source[0]) != len(target[0]):
        return set()
    source_map, components = foreground_components(source)
    target_map = {
        (row, col): color
        for row, values in enumerate(target)
        for col, color in enumerate(values)
        if color != background(source)
    }
    if not source_map or not components:
        return set()
    added = {
        cell: color for cell, color in target_map.items() if source_map.get(cell) != color
    }
    if not added:
        return set()
    candidates = set()
    for component in components:
        removed = {
            cell for cell, color in component.items() if target_map.get(cell) != color
        }
        if not removed:
            continue
        possible_offsets = {
            (target[0] - source[0], target[1] - source[1])
            for source in removed
            for target, color in added.items()
            if component[source] == color
        }
        remaining = {cell: color for cell, color in source_map.items() if cell not in component}
        for dr, dc in possible_offsets:
            if (dr, dc) == (0, 0):
                continue
            shifted = {
                (row + dr, col + dc): color
                for (row, col), color in component.items()
            }
            height, width = len(source), len(source[0])
            if any(not (0 <= row < height and 0 <= col < width) for row, col in shifted):
                continue
            if any(cell in remaining for cell in shifted):
                continue
            if target_map == remaining | shifted:
                candidates.add((dr, dc))
    return candidates


def fit_offsets(teachers):
    if len(teachers) < 2:
        return set()
    inputs = [tuple(tuple(row) for row in pair["input"]) for pair in teachers]
    if len(set(inputs)) != len(inputs):
        return set()
    common = None
    for pair in teachers:
        candidates = teacher_offsets(pair)
        if not candidates:
            return set()
        common = candidates if common is None else common & candidates
        if not common:
            return set()
    return common or set()


def predict(grid, offsets):
    if not valid_grid(grid):
        return None
    source, components = foreground_components(grid)
    height, width = len(grid), len(grid[0])
    outputs = set()
    for dr, dc in offsets:
        for component in components:
            shifted = {}
            for (row, col), color in component.items():
                target = (row + dr, col + dc)
                if not (0 <= target[0] < height and 0 <= target[1] < width):
                    break
                if target in source and target not in component:
                    break
                shifted[target] = color
            else:
                out = [row[:] for row in grid]
                bg = background(grid)
                for row, col in component:
                    out[row][col] = bg
                for (row, col), color in shifted.items():
                    out[row][col] = color
                outputs.add(tuple(tuple(row) for row in out))
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


def self_check():
    teachers = [
        {"input": [[1, 0, 0, 0, 0, 0]], "output": [[0, 0, 1, 0, 0, 0]]},
        {"input": [[0, 1, 0, 0, 0, 0]], "output": [[0, 0, 0, 1, 0, 0]]},
        {"input": [[0, 0, 1, 0, 0, 0]], "output": [[0, 0, 0, 0, 1, 0]]},
    ]
    offsets = fit_offsets(teachers)
    if offsets != {(0, 2)} or predict(teachers[0]["input"], offsets) != teachers[0]["output"]:
        raise SystemExit("component move self-check failed")
    if fit_offsets(teachers + [teachers[0]]):
        raise SystemExit("duplicate-input component move self-check failed")
    ambiguous = [[1, 0, 0, 0, 1, 0, 0, 0, 0, 0]]
    if predict(ambiguous, offsets) is not None:
        raise SystemExit("ambiguous-component self-check failed")


def main():
    raw_d4 = subprocess.run(
        ["git", "show", f"{REFERENCE_COMMIT}:{D4_PATH}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if hashlib.sha256(raw_d4).hexdigest() != D4_SHA256:
        raise SystemExit("reference D4 source hash mismatch")
    d4_module = ModuleType("arc2_component_copy_translation_d4_reference")
    exec(compile(raw_d4, f"{REFERENCE_COMMIT}:{D4_PATH}", "exec"), d4_module.__dict__)
    d4_sha = hashlib.sha256(raw_d4).hexdigest()
    whole_sha = hashlib.sha256((ROOT / WHOLE_TRANSLATION_PATH).read_bytes()).hexdigest()
    self_check()

    manifest = hashlib.sha256()
    files = sorted(TRAINING_DIR.glob("*.json"))
    folds = eligible = unique_teacher_folds = 0
    baseline_answers = baseline_exact = baseline_wrong = 0
    whole_answers = whole_exact = whole_wrong = 0
    component_answers = component_exact = component_wrong = 0
    incremental = incremental_exact = incremental_wrong = conflicts = agreements = 0
    started = time.perf_counter()
    for path in files:
        raw = path.read_bytes()
        manifest.update(path.name.encode("utf-8") + b"\0" + hashlib.sha256(raw).digest())
        examples = json.loads(raw).get("train", [])
        if len(examples) < 3:
            continue
        eligible += 1
        for index, heldout in enumerate(examples):
            folds += 1
            teachers = [pair for i, pair in enumerate(examples) if i != index]
            teacher_inputs = [tuple(tuple(row) for row in pair["input"]) for pair in teachers]
            if len(teachers) >= 2 and len(set(teacher_inputs)) == len(teacher_inputs):
                unique_teacher_folds += 1
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
            candidate = predict(heldout["input"], fit_offsets(teachers))
            if candidate is None:
                continue
            component_answers += 1
            if candidate == heldout["output"]:
                component_exact += 1
            else:
                component_wrong += 1
            existing = [value for value in (base, whole) if value is not None]
            if not existing:
                incremental += 1
                if candidate == heldout["output"]:
                    incremental_exact += 1
                else:
                    incremental_wrong += 1
            elif all(value == candidate for value in existing):
                agreements += 1
            else:
                conflicts += 1

    result = {
        "schema": "arc2-p5-component-move-translation-support2-loo.v1",
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
        "eligible_tasks_minimum_teacher_support_2": eligible,
        "loo_folds": folds,
        "loo_folds_with_at_least_2_unique_teacher_inputs": unique_teacher_folds,
        "baseline_D4_answers": baseline_answers,
        "baseline_D4_exact": baseline_exact,
        "baseline_D4_wrong": baseline_wrong,
        "whole_translation_answers": whole_answers,
        "whole_translation_exact": whole_exact,
        "whole_translation_wrong": whole_wrong,
        "component_move_answers": component_answers,
        "component_move_exact": component_exact,
        "component_move_wrong": component_wrong,
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
