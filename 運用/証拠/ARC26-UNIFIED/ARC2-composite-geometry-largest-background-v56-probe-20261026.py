"""Probe composite geometry after switching its crop background to the largest 4-connected component."""
from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
MODULE_SOURCE = ROOT / "接続/ARC2/複合幾何変換候補.py"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _largest_component_background(grid):
    from collections import Counter

    height = len(grid)
    width = len(grid[0]) if height else 0
    counts = Counter(color for row in grid for color in row)
    largest = Counter()
    seen = set()
    for row in range(height):
        for column in range(width):
            color = grid[row][column]
            if (row, column) in seen:
                continue
            stack = [(row, column)]
            seen.add((row, column))
            size = 0
            while stack:
                current_row, current_column = stack.pop()
                size += 1
                for neighbor in ((current_row - 1, current_column), (current_row + 1, current_column),
                                 (current_row, current_column - 1), (current_row, current_column + 1)):
                    next_row, next_column = neighbor
                    if (0 <= next_row < height and 0 <= next_column < width
                            and neighbor not in seen and grid[next_row][next_column] == color):
                        seen.add(neighbor)
                        stack.append(neighbor)
            largest[color] = max(largest[color], size)
    return min(counts, key=lambda color: (-largest[color], -counts[color], color))


def _load_variant():
    sys.path.insert(0, str(ROOT))
    importlib.import_module("接続.ARC2")
    source = MODULE_SOURCE.read_text(encoding="utf-8")
    marker = "def _programs() -> tuple[Program, ...]:"
    if source.count(marker) != 1:
        raise RuntimeError("could not locate composite-geometry insertion point")
    source = source.replace(marker, """def _largest_component_background(grid: Grid) -> int:
    height, width = len(grid), len(grid[0])
    counts = Counter(color for row in grid for color in row)
    largest = Counter()
    visited: set[tuple[int, int]] = set()
    for row in range(height):
        for column in range(width):
            color = grid[row][column]
            if (row, column) in visited:
                continue
            pending = [(row, column)]
            visited.add((row, column))
            size = 0
            while pending:
                current_row, current_column = pending.pop()
                size += 1
                for next_cell in ((current_row - 1, current_column), (current_row + 1, current_column),
                                  (current_row, current_column - 1), (current_row, current_column + 1)):
                    next_row, next_column = next_cell
                    if (0 <= next_row < height and 0 <= next_column < width
                            and next_cell not in visited and grid[next_row][next_column] == color):
                        visited.add(next_cell)
                        pending.append(next_cell)
            largest[color] = max(largest[color], size)
    return min(counts, key=lambda color: (-largest[color], -counts[color], color))


""" + marker, 1)
    old = "background = min(counts, key=lambda color: (-counts[color], color))"
    if source.count(old) != 2:
        raise RuntimeError("unexpected composite-geometry background rule count")
    source = source.replace(old, "background = _largest_component_background(oriented)", 1)
    source = source.replace(old, "background = _largest_component_background(source)", 1)
    module_name = "接続.ARC2._arc2_composite_geometry_v56"
    spec = importlib.machinery.ModuleSpec(module_name, loader=None, origin=str(MODULE_SOURCE))
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    exec(compile(source, str(MODULE_SOURCE), "exec"), module.__dict__)
    return module


def _candidate(module, teachers, query):
    model = module.CompositeGeometryCandidate(teachers)
    prediction, _ = model.候補(query, {})
    return prediction if module.valid_grid(prediction) and prediction != query else None


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    variant = _load_variant()
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    challenge_proposals = challenge_tasks_with_candidate = 0
    for task in challenge.values():
        task_has_candidate = False
        for pair in task.get("test", []):
            has_candidate = _candidate(variant, task.get("train", []), pair["input"]) is not None
            task_has_candidate |= has_candidate
            challenge_proposals += has_candidate
        challenge_tasks_with_candidate += task_has_candidate
    report = {
        "schema": "arc2-composite-geometry-largest-background-v56-probe-v1",
        "background_policy": "color with the largest 4-connected component; ties break by total count then lowest color",
        "candidate_family": "exact composite geometry candidate with largest-component crop background during teacher fit and query inference",
        "loo_screening_performed": False,
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_tasks_with_candidate": challenge_tasks_with_candidate,
        "challenge_examples_with_candidate": challenge_proposals,
        "heldout_outputs_read": False,
        "challenge_targets_read": False,
        "per_task_ids_grids_or_candidates_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "composite_geometry_module": _sha(MODULE_SOURCE),
            "challenge_inputs": _sha(CHALLENGE),
            "v28_build_manifest": _sha(ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026/build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
