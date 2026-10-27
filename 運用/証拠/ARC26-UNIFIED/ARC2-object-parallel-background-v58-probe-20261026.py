"""Screen parallel background hypotheses for generic object-extraction candidates."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "入力/公式ソース/ARC-AGI-2/data/training"
CHALLENGE = ROOT / "入力/Kaggle/arc-agi_test_challenges.json"
OUTPUT = Path(__file__).with_suffix(".json")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _largest_component_background(grid):
    height, width = len(grid), len(grid[0])
    counts = Counter(color for row in grid for color in row)
    largest = Counter()
    seen = set()
    for row in range(height):
        for column in range(width):
            color = grid[row][column]
            if (row, column) in seen:
                continue
            pending = [(row, column)]
            seen.add((row, column))
            size = 0
            while pending:
                y, x = pending.pop()
                size += 1
                for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                    if (0 <= yy < height and 0 <= xx < width and (yy, xx) not in seen
                            and grid[yy][xx] == color):
                        seen.add((yy, xx))
                        pending.append((yy, xx))
            largest[color] = max(largest[color], size)
    return min(counts, key=lambda color: (-largest[color], -counts[color], color))


def _training_guided_background(teachers):
    votes = Counter()
    for pair in teachers:
        before = Counter(color for row in pair["input"] for color in row)
        after = Counter(color for row in pair["output"] for color in row)
        losses = {color: before[color] - after[color] for color in before}
        largest = max(losses.values(), default=0)
        winners = [color for color, loss in losses.items() if loss == largest]
        if largest > 0 and len(winners) == 1:
            votes[winners[0]] += 1
    top = max(votes.values(), default=0)
    winners = [color for color, count in votes.items() if count == top]
    selected = winners[0] if top >= 2 and len(winners) == 1 else None

    def choose(grid):
        counts = Counter(color for row in grid for color in row)
        if selected is not None and selected in counts:
            return selected
        return min(counts, key=lambda color: (-counts[color], color))
    return choose


def _parallel_candidates(module, teachers, query):
    backgrounds = (
        module._background,
        _largest_component_background,
        _training_guided_background(teachers),
    )
    family_methods = (
        ("object", "candidate"),
        ("outlier", "outlier_candidate"),
        ("palette", "palette_candidate"),
    )
    by_family = {family: [] for family, _ in family_methods}
    original_background = module._background
    try:
        for background in backgrounds:
            module._background = background
            model = module.ObjectExtractionCandidate(teachers)
            for family, method_name in family_methods:
                prediction, record = getattr(model, method_name)(query)
                if module._valid_grid(prediction) and prediction != query:
                    by_family[family].append((prediction, record))
    finally:
        module._background = original_background

    selected = []
    for family, rows in by_family.items():
        if not rows:
            continue
        ranked = sorted(rows, key=lambda row: (
            int(row[1].get("top_votes", 0)) / max(1, int(row[1].get("applicable_models", 0))),
            int(row[1].get("top_votes", 0)),
        ), reverse=True)
        best_score = (
            int(ranked[0][1].get("top_votes", 0)) / max(1, int(ranked[0][1].get("applicable_models", 0))),
            int(ranked[0][1].get("top_votes", 0)),
        )
        tied = [row for row in ranked if (
            int(row[1].get("top_votes", 0)) / max(1, int(row[1].get("applicable_models", 0))),
            int(row[1].get("top_votes", 0)),
        ) == best_score]
        if len({module._grid_key(row[0]) for row in tied}) == 1:
            selected.append((family, ranked[0][0], ranked[0][1]))

    if not selected:
        return None
    ranked_families = sorted(enumerate(selected), key=lambda item: (
        int(item[1][2].get("top_votes", 0)) / max(1, int(item[1][2].get("applicable_models", 0))),
        int(item[1][2].get("top_votes", 0)),
        -item[0],
    ), reverse=True)
    return ranked_families[0][1][1]


def main():
    if OUTPUT.exists():
        raise SystemExit(f"refusing to overwrite {OUTPUT}")
    sys.path.insert(0, str(ROOT))
    from 接続.ARC2 import 物体抽出候補 as module

    eligible = proposals = 0
    for path in sorted(SOURCE_ROOT.glob("*.json")):
        training = json.loads(path.read_text(encoding="utf-8")).get("train", [])
        if len(training) < 3:
            continue
        for held_index, held in enumerate(training):
            teachers = [pair for index, pair in enumerate(training) if index != held_index]
            eligible += 1
            proposals += _parallel_candidates(module, teachers, held["input"]) is not None

    challenge = json.loads(CHALLENGE.read_text(encoding="utf-8"))
    proposal_examples = proposal_tasks = 0
    for task in challenge.values():
        task_has_candidate = False
        for pair in task.get("test", []):
            has_candidate = _parallel_candidates(module, task.get("train", []), pair["input"]) is not None
            proposal_examples += has_candidate
            task_has_candidate |= has_candidate
        proposal_tasks += task_has_candidate

    report = {
        "schema": "arc2-object-parallel-background-v58-probe-v1",
        "policy": "evaluate modal, largest 4-connected component, and training removed-color plurality backgrounds in parallel; choose each object-family prediction by its own teacher-vote confidence, then apply the existing family priority",
        "loo_eligible_folds": eligible,
        "loo_candidate_proposal_folds": proposals,
        "challenge_tasks": len(challenge),
        "challenge_examples": sum(len(task.get("test", [])) for task in challenge.values()),
        "challenge_tasks_with_candidates": proposal_tasks,
        "challenge_examples_with_candidates": proposal_examples,
        "heldout_outputs_read": False,
        "challenge_targets_read": False,
        "per_task_ids_grids_or_candidates_saved": False,
        "official_kaggle_score": "UNKNOWN_NOT_SUBMITTED",
        "source_sha256": {
            "runner": _sha(Path(__file__)),
            "object_module": _sha(ROOT / "接続/ARC2/物体抽出候補.py"),
            "challenge_inputs": _sha(CHALLENGE),
            "v51_build_manifest": _sha(ROOT / "出力/Kaggle/arc2-codex-main-baseline-v1/v51-largest-component-background-20261026/build-manifest.json"),
        },
    }
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
