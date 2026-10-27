"""Probe rigid translation of one color group on public-training LOO folds."""

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


def valid_grid(grid: object) -> bool:
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


def background(grid: list[list[int]]) -> int:
    counts = {
        color: sum(value == color for row in grid for value in row)
        for color in {value for row in grid for value in row}
    }
    return min(counts, key=lambda color: (-counts[color], color))


def apply_color_translation(
    grid: list[list[int]], color: int, dr: int, dc: int
) -> list[list[int]] | None:
    if not valid_grid(grid):
        return None
    bg = background(grid)
    if color == bg or not any(color == value for row in grid for value in row):
        return None
    height, width = len(grid), len(grid[0])
    output = [row[:] for row in grid]
    cells = [
        (row, column)
        for row, values in enumerate(grid)
        for column, value in enumerate(values)
        if value == color
    ]
    for row, column in cells:
        target_row, target_column = row + dr, column + dc
        if not (0 <= target_row < height and 0 <= target_column < width):
            return None
        if grid[target_row][target_column] not in (bg, color):
            return None
    for row, column in cells:
        output[row][column] = bg
    for row, column in cells:
        output[row + dr][column + dc] = color
    return output


def fit_color_translations(teachers: list[dict]) -> set[tuple[int, int, int]]:
    if len(teachers) < 3:
        return set()
    input_keys = [tuple(tuple(row) for row in pair["input"]) for pair in teachers]
    if len(set(input_keys)) != len(input_keys):
        return set()
    common: set[tuple[int, int, int]] | None = None
    for pair in teachers:
        source, target = pair.get("input"), pair.get("output")
        if not valid_grid(source) or not valid_grid(target):
            return set()
        if len(source) != len(target) or len(source[0]) != len(target[0]):
            return set()
        bg = background(source)
        candidates: set[tuple[int, int, int]] = set()
        for color in {value for row in source for value in row} - {bg}:
            source_cells = {
                (row, column)
                for row, values in enumerate(source)
                for column, value in enumerate(values)
                if value == color
            }
            target_cells = {
                (row, column)
                for row, values in enumerate(target)
                for column, value in enumerate(values)
                if value == color
            }
            if not source_cells or len(source_cells) != len(target_cells):
                continue
            dr = min(row for row, _ in target_cells) - min(
                row for row, _ in source_cells
            )
            dc = min(column for _, column in target_cells) - min(
                column for _, column in source_cells
            )
            if (dr, dc) == (0, 0):
                continue
            shifted = {
                (row + dr, column + dc) for row, column in source_cells
            }
            if shifted != target_cells:
                continue
            if any(
                source[row][column] != color
                and source[row][column] != bg
                and target[row][column] != source[row][column]
                for row in range(len(source))
                for column in range(len(source[0]))
            ):
                continue
            if any(
                target[row][column] not in (bg, color)
                and target[row][column] != source[row][column]
                for row in range(len(source))
                for column in range(len(source[0]))
            ):
                continue
            candidates.add((color, dr, dc))
        if common is None:
            common = candidates
        else:
            common.intersection_update(candidates)
        if not common:
            return set()
    return common or set()


def predict_color_translation(
    grid: list[list[int]], candidates: set[tuple[int, int, int]]
) -> list[list[int]] | None:
    outputs = {
        tuple(tuple(row) for row in output)
        for color, dr, dc in candidates
        if (output := apply_color_translation(grid, color, dr, dc)) is not None
    }
    if len(outputs) != 1:
        return None
    return [list(row) for row in next(iter(outputs))]


def self_check() -> None:
    teachers = [
        {"input": [[1, 0, 0, 2, 0]], "output": [[0, 1, 0, 2, 0]]},
        {"input": [[0, 0, 1, 0, 2]], "output": [[0, 0, 0, 1, 2]]},
        {"input": [[0, 1, 0, 0, 2]], "output": [[0, 0, 1, 0, 2]]},
    ]
    fitted = fit_color_translations(teachers)
    if fitted != {(1, 0, 1)}:
        raise SystemExit("color translation fit self-check failed")
    if predict_color_translation(teachers[0]["input"], fitted) != teachers[0]["output"]:
        raise SystemExit("color translation prediction self-check failed")
    bad = teachers + [{"input": [[1, 0, 0, 2, 0]], "output": [[0, 1, 0, 2, 0]]}]
    if fit_color_translations(bad):
        raise SystemExit("duplicate-input self-check failed")


def main() -> None:
    raw_d4 = subprocess.run(
        ["git", "show", f"{REFERENCE_COMMIT}:{D4_PATH}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if hashlib.sha256(raw_d4).hexdigest() != D4_SHA256:
        raise SystemExit("reference D4 source hash mismatch")
    d4_module = ModuleType("arc2_color_translation_d4_reference")
    exec(compile(raw_d4, f"{REFERENCE_COMMIT}:{D4_PATH}", "exec"), d4_module.__dict__)
    d4_sha = hashlib.sha256(raw_d4).hexdigest()
    whole_sha = hashlib.sha256((ROOT / WHOLE_TRANSLATION_PATH).read_bytes()).hexdigest()
    self_check()

    manifest = hashlib.sha256()
    files = sorted(TRAINING_DIR.glob("*.json"))
    folds = eligible = 0
    baseline_answers = baseline_exact = baseline_wrong = 0
    whole_answers = whole_exact = whole_wrong = 0
    color_answers = color_exact = color_wrong = 0
    incremental = incremental_exact = incremental_wrong = 0
    conflicts = agreements = 0
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
            color_fit = fit_color_translations(teachers)
            color = predict_color_translation(heldout["input"], color_fit)
            if color is None:
                continue
            color_answers += 1
            if color == heldout["output"]:
                color_exact += 1
            else:
                color_wrong += 1
            existing = [value for value in (base, whole) if value is not None]
            if not existing:
                incremental += 1
                if color == heldout["output"]:
                    incremental_exact += 1
                else:
                    incremental_wrong += 1
            elif all(value == color for value in existing):
                agreements += 1
            else:
                conflicts += 1

    result = {
        "schema": "arc2-p5-color-group-translation-loo.v1",
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
        "color_translation_answers": color_answers,
        "color_translation_exact": color_exact,
        "color_translation_wrong": color_wrong,
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
    report = Path(__file__).with_suffix(".json")
    report.write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
