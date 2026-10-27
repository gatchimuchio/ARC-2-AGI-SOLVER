"""Screen a rotation/reflection-invariant orthogonal-neighborhood cell rule."""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _shape(grid):
    if not isinstance(grid, list) or not grid or not isinstance(grid[0], list) or not grid[0]:
        return None
    width = len(grid[0])
    if any(not isinstance(row, list) or len(row) != width for row in grid):
        return None
    return len(grid), width


def _context(grid, row, column):
    height, width = len(grid), len(grid[0])
    neighbors = tuple(
        grid[row + delta_row][column + delta_column]
        if 0 <= row + delta_row < height and 0 <= column + delta_column < width
        else -1
        for delta_row in (-1, 0, 1)
        for delta_column in (-1, 0, 1)
        if delta_row or delta_column
    )
    return grid[row][column], tuple(sorted(Counter(neighbors).items()))


def candidate(teachers, query, min_teacher_support=2):
    shape = _shape(query)
    if shape is None:
        return None, 0
    compatible = [
        pair for pair in teachers
        if _shape(pair.get("input")) == shape and _shape(pair.get("output")) == shape
    ]
    if not compatible:
        return None, 0
    output_colors = defaultdict(set)
    teacher_support = defaultdict(set)
    for teacher_index, pair in enumerate(compatible):
        seen = set()
        for row in range(shape[0]):
            for column in range(shape[1]):
                context = _context(pair["input"], row, column)
                output_colors[context].add(pair["output"][row][column])
                seen.add(context)
        for context in seen:
            teacher_support[context].add(teacher_index)
    mapping = {
        context: next(iter(colors))
        for context, colors in output_colors.items()
        if len(colors) == 1 and len(teacher_support[context]) >= min_teacher_support
    }
    prediction = [row[:] for row in query]
    changed = 0
    for row in range(shape[0]):
        for column in range(shape[1]):
            color = mapping.get(_context(query, row, column))
            if color is not None and color != query[row][column]:
                prediction[row][column] = color
                changed += 1
    return (prediction if changed else None), len(compatible)


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    eligible_folds = compatible_folds = proposals = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 3:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            eligible_folds += 1
            proposed, compatible = candidate(teachers, held["input"])
            compatible_folds += compatible > 0
            proposals += proposed is not None
    challenge_fit = challenge_proposals = challenge_tasks_with_proposal = 0
    for task in challenge.values():
        train = task.get("train", [])
        task_proposals = 0
        for pair in task.get("test", []):
            proposed, compatible = candidate(train, pair["input"])
            challenge_fit += compatible > 0
            challenge_proposals += proposed is not None
            task_proposals += proposed is not None
        challenge_tasks_with_proposal += task_proposals > 0
    report = {
        "schema": "arc2-8-neighborhood-multiset-context-v39-probe-v1",
        "candidate": {
            "context": "center color plus unordered multiset of all eight surrounding cells",
            "minimum_distinct_teacher_pair_support": 2,
            "uses_only_shape_compatible_teacher_pairs": True,
            "conflicting_context_outputs_are_held": True,
            "unknown_contexts_keep_input_color": True,
        },
        "loo_eligible_folds": eligible_folds,
        "loo_folds_with_compatible_teacher": compatible_folds,
        "loo_folds_with_candidate": proposals,
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_examples_with_compatible_teacher": challenge_fit,
        "challenge_examples_with_candidate": challenge_proposals,
        "challenge_tasks_with_candidate": challenge_tasks_with_proposal,
        "heldout_outputs_read": False,
        "challenge_targets_read": False,
        "per_task_ids_grids_or_candidates_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "challenge_inputs": _sha(CHALLENGE),
            "training_source_tree_manifest": hashlib.sha256(
                "\n".join(f"{p.name}:{_sha(p)}" for p in sorted(SOURCE_ROOT.glob("*.json"))).encode("utf-8")
            ).hexdigest(),
            "v28_build_manifest": _sha(ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v28-vote-ratio-second-20261026/build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
